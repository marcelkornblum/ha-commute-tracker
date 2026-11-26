"""Integration tests for Commute Tracker lifecycle event platform and Blueprint."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import yaml  # type: ignore[import-untyped]
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commute_tracker.const import DOMAIN
from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteEngine,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.event import CommuteLifecycleEventEntity
from custom_components.commute_tracker.lifecycle import COMMUTE_EVENT_TYPES
from custom_components.commute_tracker.models import UrgencyStage


def _construct_input(loader: Any, node: Any) -> str:
    return f"!input:{loader.construct_scalar(node)}"


def _load_blueprint_yaml(path: Path) -> dict[str, Any]:
    loader_cls: Any = type("_BlueprintYamlLoader", (yaml.SafeLoader,), {})
    loader_cls.add_constructor("!input", _construct_input)
    loaded: dict[str, Any] = yaml.load(
        path.read_text(encoding="utf-8"),
        Loader=loader_cls,
    )
    return loaded


def _active_commute_state(
    *,
    urgency_stage: UrgencyStage,
    seconds_to_leave: int,
    expected_boarding_time: str = "08:11",
) -> CommuteState:
    return CommuteState(
        commute_id="kolya_school",
        master_rollup=MasterRollupState(
            active_option="southern",
            mode="train",
            urgency_stage=urgency_stage,
            leave_by_time="07:58",
            expected_boarding_time=expected_boarding_time,
            expected_destination_time="08:40",
            seconds_to_leave=seconds_to_leave,
            seconds_to_board=seconds_to_leave + 780,
            route_label="Southern",
            will_arrive_on_time=True,
            timeliness="on_time",
            amber_threshold_seconds=210,
            prepare_threshold_seconds=480,
            is_active=True,
        ),
        child_routes={
            "southern": ChildRouteState(
                route_id="southern",
                mode="train",
                urgency_stage=urgency_stage,
                is_active=True,
            )
        },
    )


@pytest.mark.asyncio
async def test_event_entity_registered_via_config_entry_emits_and_unloads(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(
        "person.kolya",
        "home",
        {"friendly_name": "Kolya"},
    )
    hass.states.async_set("binary_sensor.kolya_active", "off")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kolya School",
        unique_id="kolya_school",
        data={
            "id": "kolya_school",
            "name": "Kolya School",
            "person": "person.kolya",
            "active_sensor": "binary_sensor.kolya_active",
            "routes": [
                {
                    "id": "southern",
                    "mode": "train",
                    "line": "southern",
                    "boarding_stop": "910GWNORWOD",
                }
            ],
        },
        options={},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    event_state = hass.states.get("event.commute_kolya_school")
    assert event_state is not None
    assert event_state.attributes["event_types"] == COMMUTE_EVENT_TYPES
    assert event_state.attributes.get("event_type") is None

    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    assert CommuteLifecycleEventEntity is not None

    amber_state = _active_commute_state(
        urgency_stage=UrgencyStage.PREPARE,
        seconds_to_leave=120,
    )
    coordinator.engine.async_evaluate_commute = AsyncMock(return_value=amber_state)

    hass.states.async_set("binary_sensor.kolya_active", "on")
    await hass.async_block_till_done()

    amber_event_state = hass.states.get("event.commute_kolya_school")
    assert amber_event_state is not None
    assert amber_event_state.attributes["event_type"] == "amber_warning"
    assert amber_event_state.attributes["person_name"] == "Kolya"
    assert amber_event_state.attributes["mode"] == "train"
    assert amber_event_state.attributes["leave_in_minutes"] == 2
    assert (
        amber_event_state.attributes["default_message"]
        == "Kolya's train departs at 08:11, leave in 2 minutes."
    )
    first_ts = amber_event_state.state

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    after_dup_state = hass.states.get("event.commute_kolya_school")
    assert after_dup_state is not None
    assert after_dup_state.state == first_ts

    leave_state = _active_commute_state(
        urgency_stage=UrgencyStage.LEAVE_NOW,
        seconds_to_leave=0,
    )
    coordinator.engine.async_evaluate_commute = AsyncMock(return_value=leave_state)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    leave_event_state = hass.states.get("event.commute_kolya_school")
    assert leave_event_state is not None
    assert leave_event_state.attributes["event_type"] == "leave_now"
    assert (
        leave_event_state.attributes["default_message"]
        == "Kolya's train departs at 08:11, leave now!"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[DOMAIN]["coordinators"]


@pytest.mark.asyncio
async def test_event_entity_registered_via_yaml_setup(hass: HomeAssistant) -> None:
    raw_config = {
        DOMAIN: {
            "commutes": [
                {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.work_active",
                    "routes": [
                        {
                            "id": "bus_73",
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        }
                    ],
                }
            ]
        }
    }
    hass.states.async_set("binary_sensor.work_active", "off")

    with patch.object(CommuteEngine, "async_evaluate_commute", new_callable=AsyncMock):
        assert await async_setup_component(hass=hass, domain=DOMAIN, config=raw_config)
        await hass.async_block_till_done()

    event_states = [
        st
        for st in hass.states.async_all()
        if st.entity_id.startswith("event.commute_")
    ]
    assert [st.entity_id for st in event_states] == ["event.commute_work_commute"]

    for coordinator in hass.data[DOMAIN]["coordinators"].values():
        coordinator.async_unload()


def test_announcement_blueprint_yaml_is_valid() -> None:
    blueprint_path = (
        Path(__file__).parent.parent
        / "blueprints"
        / "automation"
        / "commute_tracker"
        / "commute_announcements.yaml"
    )
    assert blueprint_path.is_file()
    parsed = _load_blueprint_yaml(path=blueprint_path)
    bp = parsed["blueprint"]
    assert bp["domain"] == "automation"
    inputs = bp["input"]
    assert "commute_event_entity" in inputs
    assert inputs["event_types"]["default"] == [
        "amber_warning",
        "leave_now",
        "disrupted",
    ]
    assert "tts_entity" in inputs
    assert "media_player" in inputs
    assert "extra_actions" in inputs
