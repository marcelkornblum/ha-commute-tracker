"""Base abstractions, caching layer, and dynamic registry for transit providers."""

import asyncio
import importlib
import pkgutil
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, ClassVar, TypeVar

from custom_components.commute_tracker.models import (
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)

T = TypeVar("T")


class DebouncedCache:
    """In-flight request coalescer and time-to-live cache."""

    def __init__(self, ttl_seconds: float = 20.0) -> None:
        """Initialise debounced cache.

        :param ttl_seconds: Time to live for cached responses in seconds.
        """
        self._ttl_seconds = ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}
        self._inflight: dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()

    async def async_get_or_set(
        self, key: str, fetch_callable: Callable[[], Awaitable[T]]
    ) -> T:
        """Retrieve existing cached value or execute fetcher with coalescing.

        :param key: Unique cache key identifying the resource.
        :param fetch_callable: Asynchronous callable returning the fresh value.
        :return: Cached or fetched value.
        """
        now = time.monotonic()

        # Check existing valid cache
        if key in self._cache:
            timestamp, cached_val = self._cache[key]
            if now - timestamp < self._ttl_seconds:
                return cached_val  # type: ignore[no-any-return]

        # Check or create in-flight future
        async with self._lock:
            # Re-check cache inside lock in case another task populated it
            if key in self._cache:
                timestamp, cached_val = self._cache[key]
                if now - timestamp < self._ttl_seconds:
                    return cached_val  # type: ignore[no-any-return]

            if key in self._inflight:
                future = self._inflight[key]
            else:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._inflight[key] = future
                # Schedule execution as separate task to allow parallel awaiters
                asyncio.create_task(
                    self._execute_fetch(
                        key=key,
                        future=future,
                        fetch_callable=fetch_callable,
                    )
                )

        result = await future
        return result  # type: ignore[no-any-return]

    async def _execute_fetch(
        self,
        key: str,
        future: asyncio.Future[Any],
        fetch_callable: Callable[[], Awaitable[T]],
    ) -> None:
        """Execute underlying fetcher and resolve in-flight future.

        :param key: Cache key.
        :param future: Pending future for concurrent callers.
        :param fetch_callable: Callable providing the data.
        """
        try:
            val = await fetch_callable()
            now = time.monotonic()
            self._cache[key] = (now, val)
            if not future.done():
                future.set_result(val)
        except BaseException as err:
            if not future.done():
                future.set_exception(err)
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    def invalidate(self, key: str) -> None:
        """Invalidate a specific cache key.

        :param key: Cache key to invalidate.
        """
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


class TransitProvider(ABC):
    """Abstract base class for all transit provider plugins."""

    provider_id: ClassVar[str]
    supported_modes: ClassVar[set[TransitMode]]

    def __init__(
        self,
        session: Any = None,
        cache: DebouncedCache | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialise provider with optional HTTP session and cache.

        :param session: Optional HTTP client session (e.g. aiohttp.ClientSession).
        :param cache: Optional shared debounced cache.
        :param kwargs: Additional provider-specific configuration.
        """
        self._session = session
        self._cache = cache or DebouncedCache()
        self._kwargs = kwargs

    @abstractmethod
    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Retrieve operational line status.

        :param line_id: Transit line identifier.
        :param mode: Transit mode of the line.
        :return: LineStatus instance.
        """

    @abstractmethod
    async def async_get_telemetry(
        self, route: RouteConfig, snapshot: dict[str, Any] | None = None
    ) -> RouteTelemetry:
        """Retrieve live telemetry and predictions for a configured route.

        :param route: Configured RouteConfig instance.
        :param snapshot: Optional offline snapshot payload for deterministic evaluation.
        :return: RouteTelemetry instance.
        """


class TransitProviderRegistry:
    """Dynamic discovery and lifecycle registry for transit providers."""

    def __init__(self, cache: DebouncedCache | None = None) -> None:
        """Initialise registry with shared caching layer.

        :param cache: Optional shared DebouncedCache instance.
        """
        self._providers: dict[str, type[TransitProvider]] = {}
        self._instances: dict[str, TransitProvider] = {}
        self._cache = cache or DebouncedCache()

    @property
    def registered_provider_ids(self) -> set[str]:
        """Return set of registered provider identifiers."""
        return set(self._providers.keys())

    def register(self, provider_cls: type[TransitProvider]) -> type[TransitProvider]:
        """Register a provider class with the registry.

        :param provider_cls: Subclass of TransitProvider.
        :return: The registered class.
        """
        if not hasattr(provider_cls, "provider_id") or not provider_cls.provider_id:
            msg = f"Provider class {provider_cls.__name__} missing provider_id"
            raise ValueError(msg)
        self._providers[provider_cls.provider_id] = provider_cls
        return provider_cls

    def get_provider(self, provider_id: str, **kwargs: Any) -> TransitProvider:
        """Retrieve or instantiate a provider by identifier.

        :param provider_id: Identifier of the provider (e.g. 'tfl').
        :param kwargs: Additional arguments passed to provider constructor.
        :return: Initialised TransitProvider instance.
        """
        if provider_id not in self._providers:
            raise KeyError(f"Unknown transit provider: {provider_id}")

        if provider_id not in self._instances:
            provider_cls = self._providers[provider_id]
            self._instances[provider_id] = provider_cls(cache=self._cache, **kwargs)

        return self._instances[provider_id]

    def discover_providers(self) -> None:
        """Dynamically discover and register providers located in this package."""
        package_dir = Path(__file__).parent
        package_name = "custom_components.commute_tracker.providers"

        for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
            if module_name in {"base", "__init__"}:
                continue
            full_module_name = f"{package_name}.{module_name}"
            module = importlib.import_module(full_module_name)
            for attribute_name in dir(module):
                attr = getattr(module, attribute_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, TransitProvider)
                    and attr is not TransitProvider
                    and hasattr(attr, "provider_id")
                    and attr.provider_id
                ):
                    self.register(attr)
