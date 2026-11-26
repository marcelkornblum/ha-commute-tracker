"""Tests for Commute Tracker config flow and options flow."""

from collections.abc import Sequence
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commute_tracker.const import (
    CONF_TRANSIT_DURATION_SECONDS,
    DOMAIN,
)
from custom_components.commute_tracker.models import (
    CorridorStop,
    DeparturePrediction,
    LineStatus,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import TransitProvider


class MockTransitProvider(TransitProvider):
    """Mock transit provider for config flow testing."""

    provider_id = "mock_tfl"
    supported_modes = {TransitMode.BUS, TransitMode.TRAIN, TransitMode.TUBE}

    async def async_validate_line(self, line_id: str, mode: TransitMode) -> bool:
        return line_id != "invalid_line"

    async def async_validate_stop(
        self, line_id: str, stop_id_or_name: str, mode: TransitMode
    ) -> tuple[bool, str | None, str | None]:
        if stop_id_or_name == "invalid_stop":
            return False, None, None
        return True, "490000001C", "Marble Arch"

    async def async_get_corridor_stops(
        self,
        line_id: str,
        boarding_stop: str,
        mode: TransitMode = TransitMode.BUS,
        direction: str = "all",
        target_time_window_seconds: int | None = None,
        alighting_stop: str | None = None,
    ) -> list[CorridorStop]:
        return [
            CorridorStop(id="490000001A", name="Victoria", is_target=False),
            CorridorStop(id="490000001B", name="Hyde Park Corner", is_target=False),
            CorridorStop(id="490000001C", name="Marble Arch", is_target=True),
        ]

    async def async_resolve_stop_names(self, stop_ids: Sequence[str]) -> dict[str, str]:
        known = {"910GSYDENHM": "Sydenham", "STOP_MANUAL_1": "Manual Stop"}
        return {sid: known[sid] for sid in stop_ids if sid in known}

    async def async_get_telemetry(self, route: Any) -> Any:
        raise NotImplementedError


@pytest.fixture(autouse=True)
def mock_provider_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure registry has a mock provider for testing."""
    from custom_components.commute_tracker.providers.base import (
        TransitProviderRegistry,
    )

    orig_discover = TransitProviderRegistry.discover_providers

    def _mock_discover(self: TransitProviderRegistry) -> None:
        orig_discover(self)
        self.register(MockTransitProvider)

    monkeypatch.setattr(TransitProviderRegistry, "discover_providers", _mock_discover)


@pytest.mark.asyncio
async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test user step shows form initially."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_validation_missing_fields(hass: HomeAssistant) -> None:
    """Test user step fails with missing required fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] is not None
    assert "name" in result2["errors"]


@pytest.mark.asyncio
async def test_full_config_flow_single_route_with_corridor(hass: HomeAssistant) -> None:
    """Test full flow: user -> route -> corridor -> names -> finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1: Commute Setup
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Work Commute",
                "active_sensor": "binary_sensor.workday",
            },
            "destination_timings": {
                "target_destination_time": "09:00:00",
                "prep_seconds": {"minutes": 2},
            },
            "rollup_strategy_sec": {
                "rollup_strategy": "late_with_buffer",
                "route_late_buffer_seconds": {"minutes": 5},
            },
            "advanced_settings": {
                "poll_interval": {"seconds": 30},
            },
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "route"
    placeholders = result2.get("description_placeholders")
    assert placeholders is not None and "stop_guidance" in placeholders

    # Step 2: Route Setup
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
                "name": "Bus 73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 5},
                "grace_seconds": {"minutes": 1},
            },
        },
    )
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "corridor"

    # Step 3: Corridor Stop Confirmation
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            "corridor_stops": ["490000001A", "490000001B", "490000001C"],
        },
    )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "corridor_names"

    # Step 4: Corridor Stop Names
    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={"stop_display_names": {}},
    )
    assert result5["type"] == FlowResultType.FORM
    assert result5["step_id"] == "routes"

    # Step 5: Routes overview - finish
    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result6["type"] == FlowResultType.CREATE_ENTRY
    assert result6["title"] == "Work Commute"
    assert result6["data"]["name"] == "Work Commute"
    assert result6["data"]["active_sensor"] == "binary_sensor.workday"
    assert len(result6["data"]["routes"]) == 1

    route = result6["data"]["routes"][0]
    assert route["line"] == "73"
    assert route["boarding_stop"] == "490000001C"
    assert route["corridor_stops"] == [
        "490000001A",
        "490000001B",
        "490000001C",
    ]


@pytest.mark.asyncio
async def test_route_step_validation_invalid_line(hass: HomeAssistant) -> None:
    """Test route step validation rejects invalid line."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Morning Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "invalid_line",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
            },
        },
    )
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "route"
    assert result3["errors"] is not None
    assert result3["errors"]["line"] == "invalid_line"


@pytest.mark.asyncio
async def test_route_step_validation_invalid_boarding_stop(
    hass: HomeAssistant,
) -> None:
    """Test route step validation rejects invalid boarding stop."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Morning Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "invalid_stop",
            },
        },
    )
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "route"
    assert result3["errors"] is not None
    assert result3["errors"]["boarding_stop"] == "invalid_boarding_stop"


@pytest.mark.asyncio
async def test_multi_route_flow(hass: HomeAssistant) -> None:
    """Test configuring multiple routes with add_route action."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Multi Route Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )

    # Route 1
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
            },
        },
    )
    assert result3["step_id"] == "corridor"

    # Confirm corridor for Route 1
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            "corridor_stops": ["490000001A", "490000001C"],
        },
    )
    assert result4["step_id"] == "corridor_names"

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={"stop_display_names": {}},
    )
    assert result5["type"] == FlowResultType.FORM
    assert result5["step_id"] == "routes"

    # From routes step, select add_route
    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={"route_action": "add_route"},
    )
    assert result6["type"] == FlowResultType.FORM
    assert result6["step_id"] == "route"

    # Route 2
    result7 = await hass.config_entries.flow.async_configure(
        result6["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "tube",
                "line": "victoria",
            },
            "boarding_walk": {
                "boarding_stop": "Victoria",
            },
        },
    )
    assert result7["step_id"] == "corridor"

    # Confirm corridor for Route 2
    result8 = await hass.config_entries.flow.async_configure(
        result7["flow_id"],
        user_input={
            "corridor_stops": ["490000001A"],
        },
    )
    assert result8["step_id"] == "corridor_names"

    result9 = await hass.config_entries.flow.async_configure(
        result8["flow_id"],
        user_input={"stop_display_names": {}},
    )
    assert result9["step_id"] == "routes"

    # Finish from routes
    result10 = await hass.config_entries.flow.async_configure(
        result9["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result10["type"] == FlowResultType.CREATE_ENTRY
    assert len(result10["data"]["routes"]) == 2


@pytest.mark.asyncio
async def test_duplicate_unique_id_abort(hass: HomeAssistant) -> None:
    """Test config flow aborts when commute unique_id is already configured."""
    # First entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Work Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
            },
        },
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={"corridor_stops": ["490000001C"]},
    )
    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={"stop_display_names": {}},
    )
    await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={"route_action": "finish"},
    )

    # Attempt second entry with same name
    result_dup = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result_dup2 = await hass.config_entries.flow.async_configure(
        result_dup["flow_id"],
        user_input={
            "overview": {
                "name": "Work Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )
    assert result_dup2["type"] == FlowResultType.ABORT
    assert result_dup2["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow allows updating timing thresholds and reloads entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Work Commute",
        data={
            "id": "work_commute",
            "name": "Work Commute",
            "active_sensor": "binary_sensor.workday",
            "prep_seconds": 120,
            "boarding_walk_seconds": 300,
            "grace_seconds": 60,
            "route_late_buffer_seconds": 300,
            "routes": [
                {
                    "id": "bus_73",
                    "mode": "bus",
                    "line": "73",
                    "boarding_stop": "490000001C",
                }
            ],
        },
        unique_id="work_commute",
        options={},
    )
    entry.add_to_hass(hass)
    from custom_components.commute_tracker import async_update_options

    entry.add_update_listener(async_update_options)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == ["commute_settings", "routes"]

    result_form = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "commute_settings"},
    )
    assert result_form["type"] == FlowResultType.FORM
    assert result_form["step_id"] == "commute_settings"

    with (
        patch.object(
            hass.config_entries, "async_reload", new_callable=AsyncMock
        ) as mock_reload,
        patch.object(
            MockTransitProvider,
            "async_get_corridor_stops",
            new_callable=AsyncMock,
        ) as mock_discovery,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result_form["flow_id"],
            user_input={
                "overview": {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.workday",
                },
                "destination_timings": {
                    "prep_seconds": {"minutes": 3},
                    "target_destination_time": "08:45:00",
                },
                "rollup_strategy_sec": {
                    "rollup_strategy": "soonest",
                    "route_late_buffer_seconds": {"minutes": 6, "seconds": 40},
                },
                "advanced_settings": {
                    "poll_interval": {"seconds": 45},
                },
            },
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert entry.data["prep_seconds"] == 180
        assert entry.data["rollup_strategy"] == "soonest"
        assert entry.data["poll_interval"] == 45
        mock_discovery.assert_not_called()
        mock_reload.assert_called_once_with(entry.entry_id)


async def test_async_get_registry_uses_executor_job(hass: HomeAssistant) -> None:
    """Verify _async_get_registry executes discover_providers via executor."""
    from custom_components.commute_tracker.config_flow import CommuteTrackerConfigFlow

    flow = CommuteTrackerConfigFlow()
    flow.hass = hass

    # Ensure DOMAIN registry is not present
    hass.data.pop(DOMAIN, None)

    executor_jobs: list[Any] = []
    real_async_add_executor_job = hass.async_add_executor_job

    async def _capture_executor_job(target: Any, *args: Any) -> Any:
        executor_jobs.append(target)
        return await real_async_add_executor_job(target, *args)

    with patch.object(
        hass, "async_add_executor_job", side_effect=_capture_executor_job
    ):
        registry = await flow._async_get_registry()
        assert registry is not None

        assert any(
            getattr(job, "__name__", "") in {"discover_providers", "_mock_discover"}
            for job in executor_jobs
        )


@pytest.mark.asyncio
async def test_route_transit_duration_seconds_saved(hass: HomeAssistant) -> None:
    """Test transit_duration_seconds in alighting_walk section is saved onto route."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Work Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )
    assert result2["step_id"] == "route"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
                "name": "Bus 73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 5},
            },
            "alighting_walk": {
                "alighting_stop": "Oxford Circus",
                "transit_duration_seconds": {"minutes": 12},
                "alighting_walk_seconds": {"minutes": 3},
            },
        },
    )
    assert result3["step_id"] == "corridor"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            "corridor_stops": ["490000001C"],
        },
    )
    assert result4["step_id"] == "corridor_names"

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={"stop_display_names": {}},
    )
    assert result5["step_id"] == "routes"

    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result6["type"] == FlowResultType.CREATE_ENTRY
    routes = result6["data"]["routes"]
    assert len(routes) == 1
    assert routes[0][CONF_TRANSIT_DURATION_SECONDS] == 720
    assert routes[0]["alighting_stop"] == "Oxford Circus"
    assert routes[0]["alighting_walk_seconds"] == 180


@pytest.mark.asyncio
async def test_corridor_stops_ordering_with_extra_stops(hass: HomeAssistant) -> None:
    """Test corridor stops place extra upstream stops before target boarding stop."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Single Stop Commute",
                "active_sensor": "binary_sensor.workday",
            },
        },
    )

    with (
        patch.object(
            MockTransitProvider,
            "async_validate_stop",
            return_value=(True, "STOP_TARGET", "Target Station"),
        ),
        patch.object(
            MockTransitProvider,
            "async_get_corridor_stops",
            return_value=[
                CorridorStop(
                    id="STOP_TARGET",
                    name="Target Station",
                    is_target=True,
                )
            ],
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={
                "service_details": {
                    "provider": "mock_tfl",
                    "mode": "bus",
                    "line": "73",
                },
                "boarding_walk": {
                    "boarding_stop": "STOP_TARGET",
                },
            },
        )
        assert result3["step_id"] == "corridor"

        # Submit corridor with target stop selected and extra upstream calling points
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={
                "corridor_stops": ["STOP_TARGET"],
                "extra_stops": "STOP_UPSTREAM_1, STOP_UPSTREAM_2",
            },
        )
        assert result4["step_id"] == "corridor_names"

        result5 = await hass.config_entries.flow.async_configure(
            result4["flow_id"],
            user_input={"stop_display_names": {}},
        )
        assert result5["step_id"] == "routes"

        result6 = await hass.config_entries.flow.async_configure(
            result5["flow_id"],
            user_input={"route_action": "finish"},
        )
        assert result6["type"] == FlowResultType.CREATE_ENTRY
        saved_route = result6["data"]["routes"][0]
        # Target boarding stop must be at the very end of corridor_stops
        assert saved_route["corridor_stops"] == [
            "STOP_UPSTREAM_1",
            "STOP_UPSTREAM_2",
            "STOP_TARGET",
        ]
        assert saved_route["corridor_stops"] != [
            "STOP_TARGET",
            "STOP_UPSTREAM_1",
            "STOP_UPSTREAM_2",
        ]


@pytest.mark.asyncio
async def test_options_flow_edit_route_transit_duration(hass: HomeAssistant) -> None:
    """Test options flow route edit retains and updates transit duration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Office Commute",
        data={
            "id": "office_commute",
            "name": "Office Commute",
            "active_sensor": "binary_sensor.workday",
            "routes": [
                {
                    "id": "bus_73",
                    "provider": "mock_tfl",
                    "mode": "bus",
                    "line": "73",
                    "boarding_stop": "490000001C",
                    "alighting_stop": "490000001D",
                    "transit_duration_seconds": 600,
                    "boarding_walk_seconds": 240,
                    "alighting_walk_seconds": 120,
                    "corridor_stops": ["490000001A", "490000001C"],
                }
            ],
        },
        unique_id="office_commute",
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "routes"},
    )
    assert result2["step_id"] == "routes"

    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"route_action": "edit_route_0"},
    )
    assert result3["type"] == FlowResultType.MENU
    assert result3["step_id"] == "route_menu"

    result3b = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={"next_step_id": "route"},
    )
    assert result3b["step_id"] == "route"

    with (
        patch.object(
            MockTransitProvider, "async_validate_line", new_callable=AsyncMock
        ) as mock_val_line,
        patch.object(
            MockTransitProvider, "async_validate_stop", new_callable=AsyncMock
        ) as mock_val_stop,
        patch.object(
            MockTransitProvider, "async_get_corridor_stops", new_callable=AsyncMock
        ) as mock_corridor,
    ):
        result4 = await hass.config_entries.options.async_configure(
            result3b["flow_id"],
            user_input={
                "service_details": {
                    "provider": "mock_tfl",
                    "mode": "bus",
                    "line": "73",
                },
                "boarding_walk": {
                    "boarding_stop": "490000001C",
                    "boarding_walk_seconds": {"minutes": 4},
                },
                "alighting_walk": {
                    "alighting_stop": "490000001D",
                    "transit_duration_seconds": {"minutes": 15},
                    "alighting_walk_seconds": {"minutes": 2},
                },
            },
        )
        assert result4["step_id"] == "routes"
        mock_val_line.assert_not_called()
        mock_val_stop.assert_not_called()
        mock_corridor.assert_not_called()

    result5 = await hass.config_entries.options.async_configure(
        result4["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result5["type"] == FlowResultType.CREATE_ENTRY
    updated_route = entry.data["routes"][0]
    assert updated_route[CONF_TRANSIT_DURATION_SECONDS] == 900
    assert updated_route["corridor_stops"] == ["490000001A", "490000001C"]


@pytest.mark.asyncio
async def test_options_flow_retains_extra_stops_route_name_and_grace_fraction(
    hass: HomeAssistant,
) -> None:
    """Verify editing a route retains extra_stops, route name, and None grace."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Office Commute",
        data={
            "id": "office_commute",
            "name": "Office Commute",
            "active_sensor": "binary_sensor.workday",
            "routes": [
                {
                    "id": "bus_73",
                    "name": "Morning 73",
                    "provider": "mock_tfl",
                    "mode": "bus",
                    "line": "73",
                    "boarding_stop": "490000001C",
                    "alighting_stop": "490000001D",
                    "boarding_walk_seconds": 400,
                    "corridor_stops": [
                        "STOP_MANUAL_1",
                        "490000001A",
                        "490000001C",
                    ],
                    "corridor_stop_names": {
                        "STOP_MANUAL_1": "Manual Stop",
                        "490000001A": "Victoria",
                        "490000001C": "Marble Arch",
                    },
                    "corridor_hidden_labels": ["490000001A"],
                }
            ],
        },
        unique_id="office_commute",
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "routes"},
    )
    result3 = await hass.config_entries.options.async_configure(
        result2["flow_id"],
        user_input={"route_action": "edit_route_0"},
    )
    assert result3["step_id"] == "route_menu"
    result3b = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        user_input={"next_step_id": "route"},
    )
    assert result3b["step_id"] == "route"

    with patch.object(
        MockTransitProvider,
        "async_get_corridor_stops",
        wraps=MockTransitProvider().async_get_corridor_stops,
    ) as mock_get_corridor:
        result4 = await hass.config_entries.options.async_configure(
            result3b["flow_id"],
            user_input={
                "service_details": {
                    "provider": "mock_tfl",
                    "mode": "bus",
                    "line": "73",
                },
                "boarding_walk": {
                    "boarding_stop": "Marble Arch",
                    "boarding_walk_seconds": {"minutes": 6, "seconds": 40},
                },
                "alighting_walk": {
                    "alighting_stop": "490000001D",
                },
            },
        )
        assert result4["step_id"] == "corridor"
        mock_get_corridor.assert_called_once()
        assert mock_get_corridor.call_args.kwargs.get("alighting_stop") == "490000001D"

    # Submit corridor step keeping the previously added STOP_MANUAL_1
    result5 = await hass.config_entries.options.async_configure(
        result4["flow_id"],
        user_input={
            "corridor_stops": [
                "STOP_MANUAL_1",
                "490000001A",
                "490000001C",
            ]
        },
    )
    assert result5["step_id"] == "corridor_names"

    result6 = await hass.config_entries.options.async_configure(
        result5["flow_id"],
        user_input={
            "stop_display_names": {
                "name_stop_manual_1": "Manual Stop",
                "name_490000001a": "Victoria",
                "name_490000001c": "Marble Arch",
            },
            "hide_schematic_labels": ["490000001A"],
        },
    )
    assert result6["step_id"] == "routes"

    result7 = await hass.config_entries.options.async_configure(
        result6["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result7["type"] == FlowResultType.CREATE_ENTRY
    updated_route = entry.data["routes"][0]
    assert updated_route.get("name") == "Morning 73"
    assert updated_route.get("grace_seconds") is None
    assert updated_route["corridor_stops"] == [
        "STOP_MANUAL_1",
        "490000001A",
        "490000001C",
    ]
    assert updated_route["corridor_stop_names"]["490000001A"] == "Victoria"
    assert updated_route["corridor_hidden_labels"] == ["490000001A"]


@pytest.mark.asyncio
async def test_config_flow_persists_thresholds_and_stop_lead_times(
    hass: HomeAssistant,
) -> None:
    """Verify config flow saves prepare/amber thresholds and per-stop lead times."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Threshold Test",
                "active_sensor": "binary_sensor.school_active",
            },
            "destination_timings": {
                "prep_seconds": {"minutes": 2},
                "prepare_threshold_seconds": {"minutes": 9},
                "amber_threshold_seconds": {"minutes": 3},
            },
        },
    )
    assert result2["step_id"] == "route"

    result4 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "train",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 6, "seconds": 40},
            },
        },
    )
    assert result4["step_id"] == "corridor"

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={
            "corridor_stops": ["490000001A", "490000001B", "490000001C"],
        },
    )
    assert result5["step_id"] == "corridor_names"

    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={
            "stop_display_names": {
                "name_490000001a": "Victoria",
                "name_490000001b": "Hyde Park",
                "name_490000001c": "Marble Arch",
            },
            "stop_lead_times": {
                "lead_490000001a": {"minutes": 15},
                "lead_490000001b": {"minutes": 5},
            },
        },
    )
    assert result6["step_id"] == "routes"

    result7 = await hass.config_entries.flow.async_configure(
        result6["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result7["type"] == FlowResultType.CREATE_ENTRY
    assert result7["data"]["prepare_threshold_seconds"] == 540
    assert result7["data"]["amber_threshold_seconds"] == 180
    assert result7["data"]["routes"][0]["corridor_stop_lead_seconds"] == {
        "490000001A": 900,
        "490000001B": 300,
        "490000001C": 0,
    }


@pytest.mark.asyncio
async def test_config_flow_rejects_non_monotonic_lead_times(
    hass: HomeAssistant,
) -> None:
    """Verify corridor_names rejects non-decreasing per-stop lead times."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Invalid Leads Test",
                "active_sensor": "binary_sensor.school_active",
            },
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "train",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 6, "seconds": 40},
            },
        },
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            "corridor_stops": ["490000001A", "490000001B", "490000001C"],
        },
    )
    assert result4["step_id"] == "corridor_names"

    result_err = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={
            "stop_display_names": {
                "name_490000001a": "Victoria",
                "name_490000001b": "Hyde Park",
                "name_490000001c": "Marble Arch",
            },
            "stop_lead_times": {
                "lead_490000001a": {"minutes": 5},
                "lead_490000001b": {"minutes": 6, "seconds": 40},
            },
        },
    )
    assert result_err["step_id"] == "corridor_names"
    assert result_err["errors"] == {"base": "invalid_lead_times"}


@pytest.mark.asyncio
async def test_config_flow_persists_destination_and_hidden_labels(
    hass: HomeAssistant,
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "School Run",
                "active_sensor": "binary_sensor.school_active",
            },
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "train",
                "line": "southern",
                "destination": "Victoria",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 5},
            },
        },
    )
    assert result3["step_id"] == "corridor"

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            "corridor_stops": ["490000001A", "490000001C"],
            "extra_stops": "910GSYDENHM",
        },
    )
    assert result4["step_id"] == "corridor_names"

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={
            "stop_display_names": {},
            "hide_schematic_labels": ["910GSYDENHM"],
        },
    )
    assert result5["step_id"] == "routes"

    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert result6["type"] == FlowResultType.CREATE_ENTRY
    route = result6["data"]["routes"][0]
    assert route["destination"] == "Victoria"
    assert route["corridor_stop_names"]["910GSYDENHM"] == "Sydenham"
    assert route["corridor_hidden_labels"] == ["910GSYDENHM"]


@pytest.mark.asyncio
async def test_options_flow_route_menu_direct_corridor_and_names_paths(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="School Run",
        unique_id="school_run",
        data={
            "id": "school_run",
            "name": "School Run",
            "active_sensor": "binary_sensor.school_active",
            "routes": [
                {
                    "id": "southern",
                    "name": "Southern",
                    "provider": "mock_tfl",
                    "mode": "train",
                    "line": "southern",
                    "boarding_stop": "490000001C",
                    "corridor_stops": ["490000001A", "490000001B", "490000001C"],
                    "corridor_stop_names": {
                        "490000001A": "Victoria",
                        "490000001B": "Hyde Park",
                        "490000001C": "Marble Arch",
                    },
                }
            ],
        },
        options={},
    )
    entry.add_to_hass(hass)

    init_res = await hass.config_entries.options.async_init(entry.entry_id)
    routes_res = await hass.config_entries.options.async_configure(
        init_res["flow_id"], user_input={"next_step_id": "routes"}
    )
    menu_res = await hass.config_entries.options.async_configure(
        routes_res["flow_id"], user_input={"route_action": "edit_route_0"}
    )
    assert menu_res["step_id"] == "route_menu"

    with patch.object(
        MockTransitProvider, "async_get_corridor_stops", new_callable=AsyncMock
    ) as mock_discovery:
        names_res = await hass.config_entries.options.async_configure(
            menu_res["flow_id"], user_input={"next_step_id": "edit_corridor_names"}
        )
        assert names_res["step_id"] == "corridor_names"
        mock_discovery.assert_not_called()

    after_names = await hass.config_entries.options.async_configure(
        names_res["flow_id"],
        user_input={
            "stop_display_names": {
                "name_490000001a": "Victoria",
                "name_490000001b": "Hyde Park",
                "name_490000001c": "Marble Arch",
            },
            "hide_schematic_labels": ["490000001B"],
            "stop_lead_times": {
                "lead_490000001a": {"minutes": 10},
                "lead_490000001b": {"minutes": 5},
            },
        },
    )
    assert after_names["step_id"] == "routes"

    menu_res2 = await hass.config_entries.options.async_configure(
        after_names["flow_id"], user_input={"route_action": "edit_route_0"}
    )
    corridor_res = await hass.config_entries.options.async_configure(
        menu_res2["flow_id"], user_input={"next_step_id": "edit_corridor"}
    )
    assert corridor_res["step_id"] == "corridor"

    names_res2 = await hass.config_entries.options.async_configure(
        corridor_res["flow_id"],
        user_input={"corridor_stops": ["490000001A", "490000001C"]},
    )
    assert names_res2["step_id"] == "corridor_names"

    after_corridor = await hass.config_entries.options.async_configure(
        names_res2["flow_id"],
        user_input={"stop_display_names": {}},
    )
    assert after_corridor["step_id"] == "routes"

    done = await hass.config_entries.options.async_configure(
        after_corridor["flow_id"], user_input={"route_action": "finish"}
    )
    assert done["type"] == FlowResultType.CREATE_ENTRY
    saved_route = entry.data["routes"][0]
    assert saved_route["corridor_stops"] == ["490000001A", "490000001C"]
    assert saved_route["corridor_stop_lead_seconds"] == {
        "490000001A": 600,
        "490000001C": 0,
    }


@pytest.mark.asyncio
async def test_config_flow_grace_fraction_and_mutual_grace_validation(
    hass: HomeAssistant,
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    err_commute = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Grace Test",
                "active_sensor": "binary_sensor.school_active",
            },
            "advanced_settings": {
                "grace_seconds": {"minutes": 1},
                "grace_fraction": 0.2,
            },
        },
    )
    assert err_commute["step_id"] == "user"
    assert err_commute["errors"] == {"base": "mutual_grace"}

    ok_commute = await hass.config_entries.flow.async_configure(
        err_commute["flow_id"],
        user_input={
            "overview": {
                "name": "Grace Test",
                "active_sensor": "binary_sensor.school_active",
            },
            "advanced_settings": {
                "grace_fraction": 0.2,
            },
        },
    )
    assert ok_commute["step_id"] == "route"

    err_route = await hass.config_entries.flow.async_configure(
        ok_commute["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 5},
                "grace_seconds": {"seconds": 45},
                "grace_fraction": 0.15,
            },
        },
    )
    assert err_route["step_id"] == "route"
    assert err_route["errors"] == {"base": "mutual_grace"}

    ok_route = await hass.config_entries.flow.async_configure(
        err_route["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "bus",
                "line": "73",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 5},
                "grace_fraction": 0.15,
            },
        },
    )
    assert ok_route["step_id"] == "corridor"

    step_names = await hass.config_entries.flow.async_configure(
        ok_route["flow_id"],
        user_input={"corridor_stops": ["490000001C"]},
    )
    step_routes = await hass.config_entries.flow.async_configure(
        step_names["flow_id"],
        user_input={"stop_display_names": {}},
    )
    created = await hass.config_entries.flow.async_configure(
        step_routes["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert created["type"] == FlowResultType.CREATE_ENTRY
    assert created["data"]["grace_fraction"] == 0.2
    assert "grace_seconds" not in created["data"]
    assert created["data"]["routes"][0]["grace_fraction"] == 0.15
    assert "grace_seconds" not in created["data"]["routes"][0]


@pytest.mark.asyncio
async def test_config_flow_sub_minute_duration_selector_round_trip(
    hass: HomeAssistant,
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    step_route = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "overview": {
                "name": "Sub-Minute Test",
                "active_sensor": "binary_sensor.school_active",
            },
            "destination_timings": {
                "prep_seconds": {"minutes": 2, "seconds": 15},
                "prepare_threshold_seconds": {"minutes": 8},
                "amber_threshold_seconds": {"minutes": 3, "seconds": 30},
            },
            "advanced_settings": {
                "poll_interval": {"seconds": 30},
            },
        },
    )
    assert step_route["step_id"] == "route"

    step_corridor = await hass.config_entries.flow.async_configure(
        step_route["flow_id"],
        user_input={
            "service_details": {
                "provider": "mock_tfl",
                "mode": "train",
                "line": "southern",
            },
            "boarding_walk": {
                "boarding_stop": "Marble Arch",
                "boarding_walk_seconds": {"minutes": 13},
                "grace_seconds": {"minutes": 2, "seconds": 15},
            },
            "alighting_walk": {
                "transit_duration_seconds": {"minutes": 29},
                "alighting_walk_seconds": {"minutes": 4, "seconds": 30},
            },
        },
    )
    step_names = await hass.config_entries.flow.async_configure(
        step_corridor["flow_id"],
        user_input={"corridor_stops": ["490000001A", "490000001C"]},
    )
    step_routes = await hass.config_entries.flow.async_configure(
        step_names["flow_id"],
        user_input={
            "stop_display_names": {},
            "stop_lead_times": {
                "lead_490000001a": {"minutes": 25},
            },
        },
    )
    created = await hass.config_entries.flow.async_configure(
        step_routes["flow_id"],
        user_input={"route_action": "finish"},
    )
    assert created["type"] == FlowResultType.CREATE_ENTRY
    assert created["data"]["prep_seconds"] == 135
    assert created["data"]["prepare_threshold_seconds"] == 480
    assert created["data"]["amber_threshold_seconds"] == 210
    route = created["data"]["routes"][0]
    assert route["boarding_walk_seconds"] == 780
    assert route["grace_seconds"] == 135
    assert route["transit_duration_seconds"] == 1740
    assert route["alighting_walk_seconds"] == 270
    assert route["corridor_stop_lead_seconds"] == {
        "490000001A": 1500,
        "490000001C": 0,
    }


@pytest.mark.asyncio
async def test_options_flow_test_route_live_standby_and_error_previews(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="School Run",
        unique_id="school_run",
        data={
            "id": "school_run",
            "name": "School Run",
            "active_sensor": "binary_sensor.school_active",
            "routes": [
                {
                    "id": "southern",
                    "name": "Southern",
                    "provider": "mock_tfl",
                    "mode": "train",
                    "line": "southern",
                    "boarding_stop": "490000001C",
                    "alighting_stop": "490000001D",
                    "boarding_walk_seconds": 300,
                    "transit_duration_seconds": 900,
                    "corridor_stops": ["490000001A", "490000001C"],
                    "corridor_stop_names": {
                        "490000001A": "Victoria",
                        "490000001C": "Marble Arch",
                    },
                }
            ],
        },
        options={},
    )
    entry.add_to_hass(hass)

    init_res = await hass.config_entries.options.async_init(entry.entry_id)
    routes_res = await hass.config_entries.options.async_configure(
        init_res["flow_id"], user_input={"next_step_id": "routes"}
    )
    menu_res = await hass.config_entries.options.async_configure(
        routes_res["flow_id"], user_input={"route_action": "edit_route_0"}
    )
    assert menu_res["step_id"] == "route_menu"
    assert "test_route" in menu_res["menu_options"]

    live_telemetry = RouteTelemetry(
        route_id="southern",
        line_id="southern",
        mode=TransitMode.TRAIN,
        departures=[
            DeparturePrediction(
                vehicle_id="TR1",
                destination="Victoria",
                expected_time="2026-09-14T08:11:00Z",
                seconds_to_arrival=600,
                duration_seconds=900,
            )
        ],
        line_status=LineStatus(status_label="Good Service"),
    )
    with patch.object(
        MockTransitProvider,
        "async_get_telemetry",
        new_callable=AsyncMock,
        return_value=live_telemetry,
    ):
        preview_res = await hass.config_entries.options.async_configure(
            menu_res["flow_id"], user_input={"next_step_id": "test_route"}
        )
    assert preview_res["type"] == FlowResultType.FORM
    assert preview_res["step_id"] == "test_route"
    preview_placeholders = preview_res["description_placeholders"]
    assert preview_placeholders is not None
    summary = preview_placeholders["preview_summary"]
    assert "Good Service" in summary
    assert "Victoria" in summary
    assert "2" in summary

    back_menu = await hass.config_entries.options.async_configure(
        preview_res["flow_id"], user_input={}
    )
    assert back_menu["type"] == FlowResultType.MENU
    assert back_menu["step_id"] == "route_menu"

    empty_telemetry = RouteTelemetry(
        route_id="southern",
        line_id="southern",
        mode=TransitMode.TRAIN,
        departures=[],
        line_status=LineStatus(status_label="Good Service"),
    )
    with patch.object(
        MockTransitProvider,
        "async_get_telemetry",
        new_callable=AsyncMock,
        return_value=empty_telemetry,
    ):
        standby_res = await hass.config_entries.options.async_configure(
            back_menu["flow_id"], user_input={"next_step_id": "test_route"}
        )
    standby_placeholders = standby_res["description_placeholders"]
    assert standby_placeholders is not None
    assert "Standby" in standby_placeholders["preview_summary"]

    back_menu2 = await hass.config_entries.options.async_configure(
        standby_res["flow_id"], user_input={}
    )
    with patch.object(
        MockTransitProvider,
        "async_get_telemetry",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Upstream timeout"),
    ):
        err_res = await hass.config_entries.options.async_configure(
            back_menu2["flow_id"], user_input={"next_step_id": "test_route"}
        )
    assert err_res["step_id"] == "test_route"
    err_placeholders = err_res["description_placeholders"]
    assert err_placeholders is not None
    assert "Standby" in err_placeholders["preview_summary"]


@pytest.mark.asyncio
async def test_config_flow_disambiguates_stops_and_resolves_extra_stop_names(
    hass: HomeAssistant,
) -> None:
    async def _mock_search_stops(
        self: Any,
        query: str,
        line_id: str | None = None,
        mode: TransitMode | None = None,
    ) -> list[CorridorStop]:
        q = query.strip().lower()
        if q == "norwood":
            return [
                CorridorStop(id="910GWNORWOD", name="West Norwood"),
                CorridorStop(id="910GNORWDJ", name="Norwood Junction"),
            ]
        if q == "balham":
            return [
                CorridorStop(id="910GBALHAM", name="Balham"),
                CorridorStop(id="940GZZLUBLM", name="Balham Underground"),
            ]
        if q == "sydenham":
            return [CorridorStop(id="910GSYDENHM", name="Sydenham")]
        return []

    async def _mock_corridor_leads(
        self: Any,
        line_id: str,
        corridor_stops: list[str],
        boarding_stop: str | None = None,
    ) -> dict[str, int]:
        return {"910GSYDENHM": 600, "910GWNORWOD": 0}

    with (
        patch.object(MockTransitProvider, "async_search_stops", _mock_search_stops),
        patch.object(
            MockTransitProvider,
            "async_get_corridor_stops",
            new_callable=AsyncMock,
            return_value=[
                CorridorStop(id="910GWNORWOD", name="West Norwood", is_target=True)
            ],
        ),
        patch.object(
            MockTransitProvider,
            "async_get_corridor_lead_times",
            _mock_corridor_leads,
        ),
    ):
        init_res = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        route_step = await hass.config_entries.flow.async_configure(
            init_res["flow_id"],
            user_input={
                "overview": {
                    "name": "Rail Search Test",
                    "active_sensor": "binary_sensor.school_active",
                }
            },
        )
        assert route_step["step_id"] == "route"

        pick_step = await hass.config_entries.flow.async_configure(
            route_step["flow_id"],
            user_input={
                "service_details": {
                    "provider": "mock_tfl",
                    "mode": "train",
                    "line": "southern",
                },
                "boarding_walk": {
                    "boarding_stop": "Norwood",
                    "boarding_walk_seconds": {"minutes": 10},
                },
                "alighting_walk": {
                    "alighting_stop": "Balham",
                },
            },
        )
        assert pick_step["type"] == FlowResultType.FORM
        assert pick_step["step_id"] == "select_stops"

        corridor_step = await hass.config_entries.flow.async_configure(
            pick_step["flow_id"],
            user_input={
                "boarding_stop": "910GWNORWOD",
                "alighting_stop": "910GBALHAM",
            },
        )
        assert corridor_step["step_id"] == "corridor"

        names_step = await hass.config_entries.flow.async_configure(
            corridor_step["flow_id"],
            user_input={
                "corridor_stops": ["910GWNORWOD"],
                "extra_stops": "Sydenham",
            },
        )
        assert names_step["step_id"] == "corridor_names"

        routes_step = await hass.config_entries.flow.async_configure(
            names_step["flow_id"],
            user_input={"stop_display_names": {}},
        )
        assert routes_step["step_id"] == "routes"

        created = await hass.config_entries.flow.async_configure(
            routes_step["flow_id"],
            user_input={"route_action": "finish"},
        )
        assert created["type"] == FlowResultType.CREATE_ENTRY
        route = created["data"]["routes"][0]
        assert route["boarding_stop"] == "910GWNORWOD"
        assert route["alighting_stop"] == "910GBALHAM"
        assert route["corridor_stops"] == ["910GSYDENHM", "910GWNORWOD"]
        assert route["corridor_stop_names"]["910GSYDENHM"] == "Sydenham"
        assert route["corridor_stop_lead_seconds"] == {
            "910GSYDENHM": 600,
            "910GWNORWOD": 0,
        }
