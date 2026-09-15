"""Base abstractions, caching layer, and dynamic registry for transit providers."""

import asyncio
import importlib
import inspect
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

        if key in self._cache:
            timestamp, cached_val = self._cache[key]
            if now - timestamp < self._ttl_seconds:
                return cached_val  # type: ignore[no-any-return]

        async with self._lock:
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
    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Retrieve live telemetry and predictions for a configured route.

        :param route: Configured RouteConfig instance.
        :return: RouteTelemetry instance.
        """

    def extract_telemetry_from_snapshot(
        self, route: RouteConfig, snapshot: dict[str, Any]
    ) -> RouteTelemetry:
        """Extract route telemetry from an offline snapshot dictionary.

        :param route: Configured RouteConfig instance.
        :param snapshot: Offline snapshot payload dictionary.
        :return: Normalised RouteTelemetry instance.
        """
        raise NotImplementedError(
            f"Provider {self.provider_id} does not support snapshot extraction"
        )


class ProviderValidationError(TypeError):
    """Raised when a transit provider class fails contract validation."""


class TransitProviderRegistry:
    """Dynamic discovery and lifecycle registry for transit providers."""

    def __init__(
        self,
        cache: DebouncedCache | None = None,
        session: Any = None,
    ) -> None:
        """Initialise registry with shared caching layer and optional HTTP session.

        :param cache: Optional shared DebouncedCache instance.
        :param session: Optional shared HTTP client session.
        """
        self._providers: dict[str, type[TransitProvider]] = {}
        self._instances: dict[str, TransitProvider] = {}
        self._cache = cache or DebouncedCache()
        self._session = session

    @property
    def registered_provider_ids(self) -> set[str]:
        """Return set of registered provider identifiers."""
        return set(self._providers.keys())

    @classmethod
    def validate_provider(cls, provider_cls: type[Any]) -> None:
        """Validate whether a provider class satisfies the plugin contract.

        Checks:
        1. Subclass of TransitProvider and not TransitProvider itself.
        2. Non-abstract concrete implementation.
        3. Non-empty string provider_id.
        4. Non-empty set of TransitMode instances for supported_modes.
        5. Required callable methods present:
           - async_get_line_status
           - async_get_telemetry
           - extract_telemetry_from_snapshot

        :param provider_cls: Class to inspect and validate.
        :raises ProviderValidationError: If any contract requirement is violated.
        """
        if not isinstance(provider_cls, type):
            msg = (
                f"Expected provider class to be a type, got "
                f"{type(provider_cls).__name__}"
            )
            raise ProviderValidationError(msg)

        if (
            not issubclass(provider_cls, TransitProvider)
            or provider_cls is TransitProvider
        ):
            msg = (
                f"{provider_cls.__name__} must be a concrete subclass of "
                f"TransitProvider"
            )
            raise ProviderValidationError(msg)

        if inspect.isabstract(provider_cls):
            abstract_methods = ", ".join(
                sorted(getattr(provider_cls, "__abstractmethods__", set()))
            )
            msg = (
                f"{provider_cls.__name__} has unimplemented abstract methods: "
                f"{abstract_methods}"
            )
            raise ProviderValidationError(msg)

        provider_id = getattr(provider_cls, "provider_id", None)
        if not isinstance(provider_id, str) or not provider_id.strip():
            msg = (
                f"{provider_cls.__name__} must define a non-empty string 'provider_id'"
            )
            raise ProviderValidationError(msg)

        supported_modes = getattr(provider_cls, "supported_modes", None)
        if not isinstance(supported_modes, (set, frozenset)) or not supported_modes:
            msg = (
                f"{provider_cls.__name__} must define a non-empty set for "
                f"'supported_modes'"
            )
            raise ProviderValidationError(msg)

        if not all(isinstance(m, TransitMode) for m in supported_modes):
            msg = (
                f"All members of {provider_cls.__name__}.supported_modes "
                f"must be TransitMode instances"
            )
            raise ProviderValidationError(msg)

        for method_name in (
            "async_get_line_status",
            "async_get_telemetry",
        ):
            method = getattr(provider_cls, method_name, None)
            if not callable(method):
                msg = (
                    f"{provider_cls.__name__} missing required callable method "
                    f"'{method_name}'"
                )
                raise ProviderValidationError(msg)

    @classmethod
    def is_valid_provider(cls, provider_cls: type[Any]) -> bool:
        """Check if a provider class satisfies contract without raising errors.

        :param provider_cls: Class to inspect.
        :return: True if valid, False otherwise.
        """
        try:
            cls.validate_provider(provider_cls=provider_cls)
            return True
        except ProviderValidationError:
            return False

    def register(self, provider_cls: type[TransitProvider]) -> type[TransitProvider]:
        """Register a provider class with the registry.

        :param provider_cls: Subclass of TransitProvider.
        :return: The registered class.
        :raises ProviderValidationError: If the provider fails contract validation.
        """
        self.validate_provider(provider_cls=provider_cls)
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
            init_kwargs = dict(kwargs)
            if "session" not in init_kwargs and self._session is not None:
                init_kwargs["session"] = self._session
            self._instances[provider_id] = provider_cls(
                cache=self._cache, **init_kwargs
            )

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
                    and self.is_valid_provider(provider_cls=attr)
                ):
                    self.register(provider_cls=attr)
