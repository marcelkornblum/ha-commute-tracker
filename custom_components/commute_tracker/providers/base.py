"""Base abstractions, caching layer, and dynamic registry for transit providers."""

import asyncio
import importlib
import inspect
import logging
import pkgutil
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, ClassVar, TypeVar

import aiohttp

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)

_LOGGER = logging.getLogger(__name__)

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


UNKNOWN_LINE_STATUS = LineStatus()


class TransitProvider(ABC):
    """Abstract base class and Adaptor for all transit provider plugins."""

    provider_id: ClassVar[str]
    supported_modes: ClassVar[set[TransitMode]]
    base_url: ClassVar[str] = ""

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

    def get_default_headers(self) -> dict[str, str]:
        """Return default HTTP headers for API requests.

        :return: Dictionary of headers including User-Agent and Accept.
        """
        return {
            "User-Agent": "HomeAssistant-CommuteTracker/1.0",
            "Accept": "application/json",
        }

    def get_default_params(self) -> dict[str, Any]:
        """Return default query parameters to attach to API requests.

        Inspects constructor kwargs for standard credential keys
        (``app_id``, ``app_key``, ``api_key``, ``token``).

        :return: Dictionary of query parameters.
        """
        params: dict[str, Any] = {}
        for key in ("app_id", "app_key", "api_key", "token"):
            val = self._kwargs.get(key)
            if val is not None:
                params[key] = val
        return params

    async def async_fetch_json(
        self,
        endpoint_or_url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Fetch and decode JSON payload with session pooling and header/param hooks.

        :param endpoint_or_url: Relative API path or full HTTP(S) URL.
        :param params: Optional request query parameters.
        :param headers: Optional request HTTP headers.
        :return: Decoded JSON response (dict or list).
        :raises aiohttp.ClientResponseError: If the remote server returns an HTTP error.
        """
        if endpoint_or_url.startswith(("http://", "https://")):
            url = endpoint_or_url
        else:
            base = self.base_url.rstrip("/")
            endpoint = endpoint_or_url.lstrip("/")
            url = f"{base}/{endpoint}"

        merged_headers = {**self.get_default_headers(), **(headers or {})}
        merged_params = {**self.get_default_params(), **(params or {})}
        request_params = merged_params if merged_params else None

        if self._session is not None:
            async with self._session.get(
                url, headers=merged_headers, params=request_params
            ) as response:
                response.raise_for_status()
                return await response.json()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=merged_headers, params=request_params
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def async_cached_fetch(
        self,
        cache_key: str,
        fetch_callable: Callable[[], Awaitable[T]],
    ) -> T:
        """Fetch with in-flight debouncing and TTL caching.

        :param cache_key: Unique cache identifier.
        :param fetch_callable: Asynchronous fetcher invoked on cache miss.
        :return: Result from cache or fetcher.
        """
        return await self._cache.async_get_or_set(
            key=cache_key, fetch_callable=fetch_callable
        )

    def clean_stop_name(self, raw_name: str) -> str:
        """Normalise verbose station names into clean display labels.

        :param raw_name: Raw station name string from transit API.
        :return: Cleaned stop name label.
        """
        return raw_name.strip()

    def adapt_line_status(
        self, raw_payload: Any, mode: TransitMode = TransitMode.BUS
    ) -> LineStatus:
        """Adapt raw vendor status payload into normalised LineStatus.

        Default implementation returns UNKNOWN_LINE_STATUS. Providers should
        override this to map authority-specific disruption models.

        :param raw_payload: Raw line status response from API.
        :param mode: Transit mode.
        :return: Normalised LineStatus instance.
        """
        return UNKNOWN_LINE_STATUS

    def adapt_departures(
        self,
        raw_payload: Any,
        target_stop: str,
        line_id: str | None = None,
    ) -> list[DeparturePrediction]:
        """Adapt raw vendor arrival/departure payload into sorted DeparturePredictions.

        :param raw_payload: Raw departures payload from API.
        :param target_stop: Target boarding stop identifier.
        :param line_id: Optional line identifier filter.
        :return: Sorted list of DeparturePrediction instances.
        """
        return []

    def adapt_journey(
        self,
        raw_payload: Any,
        origin: str,
        destination: str,
        reference_time_iso: str | None = None,
    ) -> list[DeparturePrediction]:
        """Adapt raw vendor journey/itinerary payload into sorted DeparturePredictions.

        :param raw_payload: Raw journey results payload from API.
        :param origin: Origin stop identifier.
        :param destination: Destination stop identifier.
        :param reference_time_iso: Optional reference snapshot timestamp.
        :return: Ordered list of DeparturePrediction instances.
        """
        return []

    def adapt_stop_names(self, raw_payload: Any) -> dict[str, str]:
        """Extract mapping of stop identifier to clean station name.

        :param raw_payload: Raw arrivals payload from API.
        :return: Mapping of stop ID to cleaned station name label.
        """
        return {}

    def build_route_telemetry(
        self,
        route: RouteConfig,
        departures: list[DeparturePrediction],
        line_status: LineStatus | None = None,
        corridor_departures: dict[str, list[DeparturePrediction]] | None = None,
        stop_names: dict[str, str] | None = None,
        active_vehicle_id: str | None = None,
    ) -> RouteTelemetry:
        """Assemble normalised RouteTelemetry domain model.

        :param route: Configured RouteConfig instance.
        :param departures: Ordered departure predictions for target boarding stop.
        :param line_status: Operational line health status.
        :param corridor_departures: Map of stop identifier to arrivals along corridor.
        :param stop_names: Map of stop identifiers to friendly labels.
        :param active_vehicle_id: Explicit lead vehicle identifier if known.
        :return: Normalised RouteTelemetry instance.
        """
        lead_vid = (
            active_vehicle_id
            if active_vehicle_id is not None
            else (departures[0].vehicle_id if departures else None)
        )
        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=departures,
            corridor_departures=corridor_departures or {},
            stop_names=stop_names or {},
            active_vehicle_id=lead_vid,
            line_status=line_status or UNKNOWN_LINE_STATUS,
        )

    async def async_fetch_line_arrivals(self, line_id: str, mode: TransitMode) -> Any:
        """Fetch arrival predictions across an entire line (batch mode).

        Override this hook if the transit authority API supports querying all
        active arrivals along a route in a single call (e.g. TfL Line Arrivals).

        :param line_id: Transit line identifier.
        :param mode: Transit mode.
        :return: Raw API payload.
        """
        return None

    async def async_fetch_stop_arrivals(
        self,
        stop_id: str,
        line_id: str | None = None,
        mode: TransitMode = TransitMode.BUS,
    ) -> Any:
        """Fetch arrival predictions for a specific stop/station.

        Override this hook if the transit authority API is stop-centric
        (e.g. SIRI StopMonitoring, GTFS-RT per stop, TfL StopPoint).

        :param stop_id: Stop identifier or NaPTAN.
        :param line_id: Optional line filter.
        :param mode: Transit mode.
        :return: Raw API payload.
        """
        return None

    async def async_fetch_journey(
        self, origin: str, destination: str, mode: TransitMode
    ) -> Any:
        """Fetch point-to-point journey/itinerary plans.

        Override this hook for scheduled rail or journey planner endpoints
        (e.g. National Rail, Deutsche Bahn Hafas).

        :param origin: Departure station code.
        :param destination: Arrival station code.
        :param mode: Transit mode.
        :return: Raw API payload.
        """
        return None

    async def async_fetch_line_status(self, line_id: str, mode: TransitMode) -> Any:
        """Fetch raw operational line status from provider API.

        Override this hook if the provider exposes an endpoint for line disruptions
        or operational status (e.g. TfL Line Status).

        :param line_id: Transit line identifier.
        :param mode: Transit mode.
        :return: Raw API payload.
        """
        return None

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Retrieve operational line status with debounced caching.

        Calls ``async_fetch_line_status`` and adapts via ``adapt_line_status``.
        If fetch fails or returns None, defaults to ``UNKNOWN_LINE_STATUS``.

        :param line_id: Transit line identifier.
        :param mode: Transit mode of the line.
        :return: Normalised LineStatus instance.
        """
        cache_key = f"{self.provider_id}_status_{line_id}"

        async def _fetch() -> LineStatus:
            try:
                raw = await self.async_fetch_line_status(line_id=line_id, mode=mode)
                if raw is None:
                    return UNKNOWN_LINE_STATUS
                return self.adapt_line_status(raw_payload=raw, mode=mode)
            except Exception as err:
                _LOGGER.warning(
                    "Failed to fetch line status for %s:%s: %s",
                    self.provider_id,
                    line_id,
                    err,
                )
                return UNKNOWN_LINE_STATUS

        return await self.async_cached_fetch(cache_key=cache_key, fetch_callable=_fetch)

    @abstractmethod
    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Retrieve live telemetry and predictions for a configured route.

        :param route: Configured RouteConfig instance.
        :return: RouteTelemetry instance.
        """


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
