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
            "name": "",
            "active_sensor": "binary_sensor.workday",
        },
    )
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] is not None
    assert "name" in result2["errors"]


@pytest.mark.asyncio
async def test_full_config_flow_single_route_with_corridor(hass: HomeAssistant) -> None:
    """Test complete flow: user -> route -> corridor -> entry created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Step 1: Commute Setup
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Work Commute",
            "active_sensor": "binary_sensor.workday",
            "poll_interval": 30,
            "target_destination_time": "09:00:00",
            "prep_seconds": 120,
            "rollup_strategy": "late_with_buffer",
            "route_late_buffer_seconds": 300,
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
            "provider": "mock_tfl",
            "mode": "bus",
            "line": "73",
            "name": "Bus 73",
            "boarding_stop": "Marble Arch",
            "boarding_walk_seconds": 300,
            "grace_seconds": 60,
            "add_another_route": False,
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
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["title"] == "Work Commute"
    assert result4["data"]["name"] == "Work Commute"
    assert result4["data"]["active_sensor"] == "binary_sensor.workday"
    assert len(result4["data"]["routes"]) == 1

    route = result4["data"]["routes"][0]
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
            "name": "Morning Commute",
            "active_sensor": "binary_sensor.workday",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "provider": "mock_tfl",
            "mode": "bus",
            "line": "invalid_line",
            "boarding_stop": "Marble Arch",
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
            "name": "Morning Commute",
            "active_sensor": "binary_sensor.workday",
        },
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "provider": "mock_tfl",
            "mode": "bus",
            "line": "73",
            "boarding_stop": "invalid_stop",
        },
    )
    assert result3["type"] == FlowResultType.FORM
    assert result3["step_id"] == "route"
    assert result3["errors"] is not None
    assert result3["errors"]["boarding_stop"] == "invalid_boarding_stop"


@pytest.mark.asyncio
async def test_multi_route_flow(hass: HomeAssistant) -> None:
    """Test configuring multiple routes with add_another_route=True."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "name": "Multi Route Commute",
            "active_sensor": "binary_sensor.workday",
        },
    )

    # Route 1 with add_another_route=True
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "provider": "mock_tfl",
            "mode": "bus",
            "line": "73",
            "boarding_stop": "Marble Arch",
            "add_another_route": True,
        },
    )
    assert result3["step_id"] == "corridor"

    # Confirm corridor for Route 1 -> loops back to route step
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            "corridor_stops": ["490000001A", "490000001C"],
        },
    )
    assert result4["type"] == FlowResultType.FORM
    assert result4["step_id"] == "route"

    # Route 2 with add_another_route=False
    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        user_input={
            "provider": "mock_tfl",
            "mode": "tube",
            "line": "victoria",
            "boarding_stop": "Victoria",
            "add_another_route": False,
        },
    )
    assert result5["step_id"] == "corridor"

    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        user_input={
            "corridor_stops": ["490000001A"],
        },
    )
    assert result6["type"] == FlowResultType.CREATE_ENTRY
    assert len(result6["data"]["routes"]) == 2


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
            "name": "Work Commute",
            "active_sensor": "binary_sensor.workday",
        },
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={
            "provider": "mock_tfl",
            "mode": "bus",
            "line": "73",
            "boarding_stop": "Marble Arch",
            "add_another_route": False,
        },
    )
    await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={"corridor_stops": ["490000001C"]},
    )

    # Attempt second entry with same name
    result_dup = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result_dup2 = await hass.config_entries.flow.async_configure(
        result_dup["flow_id"],
        user_input={
            "name": "Work Commute",
            "active_sensor": "binary_sensor.workday",
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
                "boarding_walk_seconds": 360,
                "prep_seconds": 180,
                "grace_seconds": 90,
                "route_late_buffer_seconds": 400,
                "target_destination_time": "08:45:00",
                "poll_interval": 45,
                "active_sensor": "binary_sensor.workday",
                "rollup_strategy": "soonest",
            },
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options["boarding_walk_seconds"] == 360
        assert entry.options["prep_seconds"] == 180
        assert entry.options["rollup_strategy"] == "soonest"
        mock_reload.assert_called_once_with(entry.entry_id)
