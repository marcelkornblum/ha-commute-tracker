"""Unit tests for TransitProvider, DebouncedCache, and registry."""

import asyncio
from typing import Any
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
                status_colour="#00A859",
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

    # The dynamic discovery must find tfl and template providers
    assert "tfl" in registry.registered_provider_ids
    assert "template" in registry.registered_provider_ids
