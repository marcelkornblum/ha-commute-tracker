"""Tests for Commute Tracker diagnostics output and credential redaction."""

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commute_tracker.const import DOMAIN
from custom_components.commute_tracker.coordinator import CommuteCoordinator
from custom_components.commute_tracker.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteEngine,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    RouteConfig,
    TransitMode,
    UrgencyStage,
)


@pytest.mark.asyncio
async def test_diagnostics_redacts_credentials_and_includes_coordinator_state(
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
            "providers": {
                "tfl": {
                    "app_id": "secret-app-id",
                    "app_key": "secret-app-key",
                },
                "other": {
                    "api_key": "secret-api-key",
                    "token": "secret-token",
                },
            },
            "routes": [
                {
                    "id": "southern",
                    "provider": "tfl",
                    "mode": "train",
                    "line": "southern",
                    "boarding_stop": "910GWNORWOD",
                    "grace_seconds": 60,
                    "corridor_stop_lead_seconds": {
                        "910GSYDENHM": 600,
                        "910GWNORWOD": 0,
                    },
                }
            ],
        },
        options={},
    )
    entry.add_to_hass(hass)

    cfg = CommuteConfig(
        commute_id="school_run",
        commute_title="School Run",
        active_sensor="binary_sensor.school_active",
        routes=[
            RouteConfig(
                route_id="southern",
                mode=TransitMode.TRAIN,
                line="southern",
                boarding_stop="910GWNORWOD",
            )
        ],
    )
    coordinator = CommuteCoordinator(
        hass=hass,
        config=cfg,
        engine=CommuteEngine(config=cfg),
    )
    coordinator._is_active = True
    coordinator.update_interval = timedelta(seconds=30)
    coordinator.data = CommuteState(
        commute_id="school_run",
        master_rollup=MasterRollupState(
            active_option="southern",
            urgency_stage=UrgencyStage.PREPARE,
            expected_boarding_time="08:11",
            seconds_to_board=600,
            seconds_to_leave=180,
            route_label="Southern",
            destination="Victoria",
            is_active=True,
        ),
        child_routes={
            "southern": ChildRouteState(
                route_id="southern",
                mode="train",
                urgency_stage=UrgencyStage.PREPARE,
                route_label="Southern",
                destination="Victoria",
                is_active=True,
            )
        },
    )
    hass.data.setdefault(DOMAIN, {}).setdefault("coordinators", {})[entry.entry_id] = (
        coordinator
    )

    payload = await async_get_config_entry_diagnostics(hass=hass, entry=entry)

    assert payload["entry"]["entry_id"] == entry.entry_id
    assert payload["entry"]["title"] == "School Run"
    assert payload["entry"]["unique_id"] == "school_run"

    tfl_creds = payload["config"]["providers"]["tfl"]
    assert tfl_creds["app_id"] == "**REDACTED**"
    assert tfl_creds["app_key"] == "**REDACTED**"
    other_creds = payload["config"]["providers"]["other"]
    assert other_creds["api_key"] == "**REDACTED**"
    assert other_creds["token"] == "**REDACTED**"
    assert payload["config"]["routes"][0]["grace_seconds"] == 60
    assert payload["config"]["routes"][0]["corridor_stop_lead_seconds"] == {
        "910GSYDENHM": 600,
        "910GWNORWOD": 0,
    }

    assert payload["state"]["is_active"] is True
    assert payload["state"]["last_update_success"] is True
    assert payload["state"]["update_interval_seconds"] == 30
    assert payload["state"]["data"]["master_rollup"]["active_option"] == "southern"
    assert payload["state"]["data"]["master_rollup"]["urgency_stage"] == "prepare"
    assert "southern" in payload["state"]["data"]["child_routes"]


@pytest.mark.asyncio
async def test_diagnostics_returns_none_state_when_coordinator_missing(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unloaded Commute",
        unique_id="unloaded_commute",
        data={
            "id": "unloaded_commute",
            "name": "Unloaded Commute",
            "active_sensor": "binary_sensor.active",
            "routes": [],
        },
        options={},
    )
    entry.add_to_hass(hass)

    payload = await async_get_config_entry_diagnostics(hass=hass, entry=entry)

    assert payload["entry"]["entry_id"] == entry.entry_id
    assert payload["config"]["name"] == "Unloaded Commute"
    assert payload["state"] is None
