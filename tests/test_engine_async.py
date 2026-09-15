"""Unit tests for CommuteEngine asynchronous execution and provider coordination."""

from unittest.mock import AsyncMock

import pytest

from custom_components.commute_tracker.engine import CommuteEngine
from custom_components.commute_tracker.models import (
    CommuteConfig,
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
    UrgencyStage,
)
from custom_components.commute_tracker.providers.base import (
    TransitProvider,
    TransitProviderRegistry,
)


class MockSuccessProvider(TransitProvider):
    """Mock provider returning valid live route telemetry."""

    provider_id = "mock_success"
    supported_modes = {TransitMode.BUS, TransitMode.TRAIN}

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Return Good Service status."""
        return LineStatus(
            status_label="Good Service",
            status_colour="#00A859",
            status_icon="mdi:check-circle",
        )

    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Return valid predictions."""
        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=[
                DeparturePrediction(
                    vehicle_id=f"VEH_{route.route_id}",
                    destination="Central",
                    expected_time=None,
                    seconds_to_arrival=900,
                )
            ],
            line_status=await self.async_get_line_status(
                line_id=route.line, mode=route.mode
            ),
        )


class MockFailingProvider(TransitProvider):
    """Mock provider simulating API failures."""

    provider_id = "mock_failing"
    supported_modes = {TransitMode.BUS}

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Raise connection error."""
        msg = "Connection refused by transit authority"
        raise ConnectionError(msg)

    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Raise timeout error."""
        msg = "Gateway timed out"
        raise TimeoutError(msg)


@pytest.mark.asyncio
async def test_async_evaluate_commute_multi_route_coordination() -> None:
    """Verify async_evaluate_commute queries providers concurrently."""
    routes = [
        RouteConfig(
            route_id="bus_primary",
            mode=TransitMode.BUS,
            line="26",
            provider="mock_success",
            walk_seconds=180,
            prep_seconds=60,
            grace_seconds=120,
        ),
        RouteConfig(
            route_id="train_backup",
            mode=TransitMode.TRAIN,
            line="southeastern",
            provider="mock_success",
            walk_seconds=300,
            prep_seconds=60,
            grace_seconds=120,
        ),
    ]
    config = CommuteConfig(commute_id="daily_commute", routes=routes)

    registry = TransitProviderRegistry()
    registry.register(MockSuccessProvider)

    engine = CommuteEngine(config=config, registry=registry)
    commute_state = await engine.async_evaluate_commute()

    assert commute_state.commute_id == "daily_commute"
    assert len(commute_state.child_routes) == 2
    assert "bus_primary" in commute_state.child_routes
    assert "train_backup" in commute_state.child_routes

    bus_state = commute_state.child_routes["bus_primary"]
    assert bus_state.urgency_stage == UrgencyStage.RELAXED
    assert bus_state.vehicle_id == "VEH_bus_primary"

    assert commute_state.master_rollup.active_option in {"bus_primary", "train_backup"}


@pytest.mark.asyncio
async def test_async_evaluate_commute_error_isolation() -> None:
    """Verify provider failures are isolated per route."""
    routes = [
        RouteConfig(
            route_id="bus_ok",
            mode=TransitMode.BUS,
            line="26",
            provider="mock_success",
            walk_seconds=180,
            prep_seconds=60,
            grace_seconds=120,
        ),
        RouteConfig(
            route_id="bus_broken",
            mode=TransitMode.BUS,
            line="315",
            provider="mock_failing",
            walk_seconds=180,
            prep_seconds=60,
            grace_seconds=120,
        ),
    ]
    config = CommuteConfig(commute_id="resilient_commute", routes=routes)

    registry = TransitProviderRegistry()
    registry.register(MockSuccessProvider)
    registry.register(MockFailingProvider)

    engine = CommuteEngine(config=config, registry=registry)
    commute_state = await engine.async_evaluate_commute()

    assert len(commute_state.child_routes) == 2
    assert commute_state.child_routes["bus_ok"].urgency_stage == UrgencyStage.RELAXED
    broken_stage = commute_state.child_routes["bus_broken"].urgency_stage
    assert broken_stage == UrgencyStage.STANDBY
    assert commute_state.master_rollup.active_option == "bus_ok"


def test_commute_engine_session_propagation() -> None:
    """Verify custom session is propagated to TransitProviderRegistry."""
    mock_session = AsyncMock()
    config = CommuteConfig(commute_id="session_commute", routes=[])
    engine = CommuteEngine(config=config, session=mock_session)

    assert engine._registry._session is mock_session
