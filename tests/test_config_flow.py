"""Tests for Commute Tracker config flow and options flow."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commute_tracker.const import (
    DOMAIN,
)
from custom_components.commute_tracker.models import (
    CorridorStop,
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
    ) -> list[CorridorStop]:
        return [
            CorridorStop(id="490000001A", name="Victoria", is_target=False),
            CorridorStop(id="490000001B", name="Hyde Park Corner", is_target=False),
            CorridorStop(id="490000001C", name="Marble Arch", is_target=True),
        ]

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
                "prep_seconds": 120,
            },
            "rollup_strategy_sec": {
                "rollup_strategy": "late_with_buffer",
                "route_late_buffer_seconds": 300,
            },
            "advanced_settings": {
                "poll_interval": 30,
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
                "boarding_walk_seconds": 300,
                "grace_seconds": 60,
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

    # Initialize options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    # Submit updated options
    with patch.object(
        hass.config_entries, "async_reload", new_callable=AsyncMock
    ) as mock_reload:
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "overview": {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.workday",
                },
                "destination_timings": {
                    "prep_seconds": 180,
                    "target_destination_time": "08:45:00",
                },
                "rollup_strategy_sec": {
                    "rollup_strategy": "soonest",
                    "route_late_buffer_seconds": 400,
                },
                "advanced_settings": {
                    "poll_interval": 45,
                },
            },
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "routes"

        result3 = await hass.config_entries.options.async_configure(
            result2["flow_id"],
            user_input={"route_action": "finish"},
        )
        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert entry.data["prep_seconds"] == 180
        assert entry.data["rollup_strategy"] == "soonest"
        assert entry.data["poll_interval"] == 45
        mock_reload.assert_called_once_with(entry.entry_id)
