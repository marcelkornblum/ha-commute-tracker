"""Unit tests for TransitProvider, DebouncedCache, and registry."""

import asyncio
from typing import Any, ClassVar
from unittest.mock import AsyncMock

import pytest

from custom_components.commute_tracker.models import (
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import (
    DebouncedCache,
    ProviderValidationError,
    TransitProvider,
    TransitProviderRegistry,
)


class DummyProvider(TransitProvider):
    """Concrete mock provider for testing registration and caching."""

    provider_id = "dummy"
    supported_modes = {TransitMode.BUS, TransitMode.TRAIN}

    def __init__(self, **kwargs: Any) -> None:
        """Initialise dummy provider."""
        super().__init__(**kwargs)
        self.get_line_status_mock = AsyncMock(
            return_value=LineStatus(
                status_label="Good Service",
                status_color="#00A859",
                status_icon="mdi:check-circle",
            )
        )
        self.get_telemetry_mock = AsyncMock()

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Return mock line status."""
        return await self.get_line_status_mock(line_id, mode)  # type: ignore[no-any-return]

    async def async_get_telemetry(
        self, route: RouteConfig, snapshot: dict[str, Any] | None = None
    ) -> RouteTelemetry:
        """Return mock route telemetry."""
        return await self.get_telemetry_mock(route, snapshot)  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_debounced_cache_coalescing_and_ttl() -> None:
    """Verify concurrent requests for the same key are coalesced into one call."""
    cache = DebouncedCache(ttl_seconds=1.0)
    counter = 0

    async def _slow_fetch() -> str:
        nonlocal counter
        await asyncio.sleep(0.05)
        counter += 1
        return f"result_{counter}"

    # Fire 5 concurrent requests simultaneously with the same key
    results = await asyncio.gather(
        cache.async_get_or_set("key_1", _slow_fetch),
        cache.async_get_or_set("key_1", _slow_fetch),
        cache.async_get_or_set("key_1", _slow_fetch),
        cache.async_get_or_set("key_1", _slow_fetch),
        cache.async_get_or_set("key_1", _slow_fetch),
    )

    # All 5 calls must receive identical result and fetch must only run once
    assert list(results) == ["result_1"] * 5
    assert counter == 1

    # Immediate subsequent fetch must use TTL cache without re-invoking _slow_fetch
    immediate_result = await cache.async_get_or_set("key_1", _slow_fetch)
    assert immediate_result == "result_1"
    assert counter == 1

    # Invalidate cache key
    cache.invalidate("key_1")
    refetched_result = await cache.async_get_or_set("key_1", _slow_fetch)
    assert refetched_result == "result_2"
    assert counter == 2


def test_registry_registration_and_retrieval() -> None:
    """Verify registry accepts provider classes and instantiates them with caching."""
    registry = TransitProviderRegistry()
    registry.register(DummyProvider)

    assert "dummy" in registry.registered_provider_ids
    provider = registry.get_provider("dummy")
    assert isinstance(provider, DummyProvider)
    assert provider.provider_id == "dummy"
    assert provider.supported_modes == {TransitMode.BUS, TransitMode.TRAIN}

    # Getting provider again returns the same instance or shares the registry cache
    assert registry.get_provider("dummy") is provider


def test_registry_unknown_provider_raises() -> None:
    """Verify registry raises KeyError when querying unregistered provider."""
    registry = TransitProviderRegistry()
    with pytest.raises(KeyError, match="Unknown transit provider: nonexistent"):
        registry.get_provider("nonexistent")


def test_registry_dynamic_discovery() -> None:
    """Verify dynamic discovery registers providers from the providers directory."""
    registry = TransitProviderRegistry()
    registry.discover_providers()

    assert "tfl" in registry.registered_provider_ids
    assert "template" in registry.registered_provider_ids


def test_registry_validate_provider_valid() -> None:
    """Verify validate_provider succeeds on fully compliant provider classes."""
    TransitProviderRegistry.validate_provider(provider_cls=DummyProvider)
    assert TransitProviderRegistry.is_valid_provider(provider_cls=DummyProvider) is True


def test_registry_validate_provider_invalid_not_type() -> None:
    """Verify validate_provider rejects non-class arguments."""
    with pytest.raises(
        ProviderValidationError, match="Expected provider class to be a type"
    ):
        TransitProviderRegistry.validate_provider(
            provider_cls="not_a_class"  # type: ignore[arg-type]
        )


def test_registry_validate_provider_not_subclass() -> None:
    """Verify validate_provider rejects classes not inheriting TransitProvider."""

    class PlainClass:
        pass

    with pytest.raises(ProviderValidationError, match="must be a concrete subclass"):
        TransitProviderRegistry.validate_provider(provider_cls=PlainClass)


def test_registry_validate_provider_abstract_rejected() -> None:
    """Verify validate_provider rejects abstract classes with missing methods."""

    class IncompleteProvider(TransitProvider):
        provider_id = "incomplete"
        supported_modes = {TransitMode.BUS}

    with pytest.raises(ProviderValidationError, match="unimplemented abstract methods"):
        TransitProviderRegistry.validate_provider(provider_cls=IncompleteProvider)


def test_registry_validate_provider_missing_id() -> None:
    """Verify validate_provider rejects providers with blank provider_id."""

    class NoIdProvider(DummyProvider):
        provider_id = ""

    with pytest.raises(ProviderValidationError, match="non-empty string 'provider_id'"):
        TransitProviderRegistry.validate_provider(provider_cls=NoIdProvider)


def test_registry_validate_provider_invalid_modes() -> None:
    """Verify validate_provider rejects providers with invalid supported_modes."""

    class EmptyModesProvider(DummyProvider):
        provider_id = "empty_modes"
        supported_modes = set()

    with pytest.raises(
        ProviderValidationError, match="non-empty set for 'supported_modes'"
    ):
        TransitProviderRegistry.validate_provider(provider_cls=EmptyModesProvider)

    class InvalidModesProvider(DummyProvider):
        provider_id = "invalid_modes"
        supported_modes: ClassVar[set[Any]] = {"invalid_mode"}

    with pytest.raises(ProviderValidationError, match="must be TransitMode instances"):
        TransitProviderRegistry.validate_provider(provider_cls=InvalidModesProvider)


def test_registry_validate_provider_missing_callable() -> None:
    """Verify validate_provider rejects providers with non-callable attributes."""

    class NonCallableProvider(DummyProvider):
        provider_id = "non_callable"
        async_get_line_status = "not_callable"  # type: ignore[assignment]

    with pytest.raises(
        ProviderValidationError, match="missing required callable method"
    ):
        TransitProviderRegistry.validate_provider(provider_cls=NonCallableProvider)


def test_registry_is_valid_provider_boolean_response() -> None:
    """Verify is_valid_provider returns False without raising for bad providers."""

    class BadProvider:
        pass

    assert TransitProviderRegistry.is_valid_provider(provider_cls=BadProvider) is False


@pytest.mark.asyncio
async def test_transit_provider_base_hooks_raise_not_implemented() -> None:
    """Verify default implementations of hook methods raise NotImplementedError."""

    class MinimalProvider(TransitProvider):
        provider_id = "minimal"
        supported_modes = {TransitMode.BUS}

        async def async_get_telemetry(self, route: Any) -> Any:
            raise NotImplementedError

    provider = MinimalProvider()

    with pytest.raises(NotImplementedError):
        await provider.async_fetch_line_arrivals("26", TransitMode.BUS)

    with pytest.raises(NotImplementedError):
        await provider.async_fetch_stop_arrivals("490000001A")

    with pytest.raises(NotImplementedError):
        await provider.async_fetch_journey("ORIGIN", "DEST", TransitMode.BUS)

    with pytest.raises(NotImplementedError):
        await provider.async_fetch_line_status("26", TransitMode.BUS)

    with pytest.raises(NotImplementedError):
        await provider.async_fetch_route_sequence("26")

    with pytest.raises(NotImplementedError):
        await provider.async_fetch_timetable("26", "490000001A")

    with pytest.raises(NotImplementedError):
        provider.parse_route_sequences({})

    with pytest.raises(NotImplementedError):
        await provider.async_get_corridor_stops("26", "490000001A")

    with pytest.raises(NotImplementedError):
        provider.adapt_departures([], "490000001A")

    with pytest.raises(NotImplementedError):
        provider.adapt_journey([], "ORIGIN", "DEST")

    with pytest.raises(NotImplementedError):
        provider.adapt_stop_names([])
