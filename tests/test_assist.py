"""Integration tests for commute_tracker.get_status service and Assist LLM API."""

from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
import yaml  # type: ignore[import-untyped]
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import llm
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.commute_tracker.const import DOMAIN
from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    LineStatus,
    PillBadge,
    UrgencyStage,
)


def _sample_active_state(commute_id: str = "kolya_school") -> CommuteState:
    return CommuteState(
        commute_id=commute_id,
        master_rollup=MasterRollupState(
            active_option="southern",
            urgency_stage=UrgencyStage.PREPARE,
            mode="train",
            leave_by_time="08:16",
            expected_boarding_time="08:32",
            expected_destination_time="08:45",
            seconds_to_leave=180,
            seconds_to_board=1140,
            route_label="Southern",
            destination="Victoria",
            will_arrive_on_time=True,
            timeliness="early",
            line_status=LineStatus(status_label="Good Service"),
            next_summary="Next at 08:47 (in 15m)",
            pill_badge=PillBadge(
                label="👟 Leave in 3m",
                color="#FF9800",
                bg="rgba(255, 152, 0, 0.15)",
                border="#FF9800",
            ),
            is_active=True,
        ),
        child_routes={
            "southern": ChildRouteState(
                route_id="southern",
                mode="train",
                urgency_stage=UrgencyStage.PREPARE,
                leave_by_time="08:16",
                expected_boarding_time="08:32",
                expected_destination_time="08:45",
                seconds_to_leave=180,
                seconds_to_board=1140,
                will_arrive_on_time=True,
                timeliness="early",
                corridor_location="between Forest Hill and Sydenham",
                corridor_progress=0.65,
                next_summary="Next at 08:47 (in 15m)",
                line_status=LineStatus(status_label="Good Service"),
                route_label="Southern",
                destination="Victoria",
                is_active=True,
            )
        },
    )


async def _setup_entry(
    hass: HomeAssistant,
    *,
    commute_id: str = "kolya_school",
    name: str = "Kolya School",
    active_state: str = "off",
) -> MockConfigEntry:
    hass.states.async_set("person.kolya", "home", {"friendly_name": "Kolya"})
    hass.states.async_set(f"binary_sensor.{commute_id}_active", active_state)

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        unique_id=commute_id,
        data={
            "id": commute_id,
            "name": name,
            "person": "person.kolya",
            "destination": "School",
            "target_destination_time": "08:50",
            "active_sensor": f"binary_sensor.{commute_id}_active",
            "routes": [
                {
                    "id": "southern",
                    "mode": "train",
                    "line": "southern",
                    "boarding_stop": "910GWNORWOD",
                    "destination": "Victoria",
                }
            ],
        },
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.asyncio
async def test_get_status_service_returns_deduplicated_commutes_and_filters(
    hass: HomeAssistant,
) -> None:
    entry = await _setup_entry(hass=hass, active_state="off")
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    coordinator.engine.async_evaluate_commute = AsyncMock(
        return_value=_sample_active_state()
    )

    hass.states.async_set("binary_sensor.kolya_school_active", "on")
    await hass.async_block_till_done()

    all_resp = cast(
        dict[str, Any],
        await hass.services.async_call(
            DOMAIN,
            "get_status",
            {},
            blocking=True,
            return_response=True,
        ),
    )
    assert len(all_resp["commutes"]) == 1
    assert all_resp["commutes"][0]["commute_id"] == "kolya_school"
    assert all_resp["commutes"][0]["recommended"]["route_label"] == "Southern"

    by_id = cast(
        dict[str, Any],
        await hass.services.async_call(
            DOMAIN,
            "get_status",
            {"commute_id": "kolya_school"},
            blocking=True,
            return_response=True,
        ),
    )
    assert len(by_id["commutes"]) == 1
    assert by_id["commutes"][0]["commute_id"] == "kolya_school"

    by_entity = cast(
        dict[str, Any],
        await hass.services.async_call(
            DOMAIN,
            "get_status",
            {"entity_id": "sensor.commute_kolya_school"},
            blocking=True,
            return_response=True,
        ),
    )
    assert len(by_entity["commutes"]) == 1
    assert by_entity["commutes"][0]["commute_id"] == "kolya_school"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_status",
            {"commute_id": "nonexistent"},
            blocking=True,
            return_response=True,
        )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_get_status_force_refresh_fetches_live_without_waking_coordinator(
    hass: HomeAssistant,
) -> None:
    entry = await _setup_entry(hass=hass, active_state="off")
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    coordinator.engine.async_evaluate_commute = AsyncMock(
        return_value=_sample_active_state()
    )

    idle_resp = cast(
        dict[str, Any],
        await hass.services.async_call(
            DOMAIN,
            "get_status",
            {"commute_id": "kolya_school"},
            blocking=True,
            return_response=True,
        ),
    )
    assert idle_resp["commutes"][0]["is_active"] is False
    assert idle_resp["commutes"][0]["is_relevant"] is False
    assert idle_resp["commutes"][0]["recommended"] is None

    live_resp = cast(
        dict[str, Any],
        await hass.services.async_call(
            DOMAIN,
            "get_status",
            {"commute_id": "kolya_school", "force_refresh": True},
            blocking=True,
            return_response=True,
        ),
    )
    assert live_resp["commutes"][0]["is_active"] is False
    assert live_resp["commutes"][0]["is_relevant"] is True
    assert live_resp["commutes"][0]["recommended"]["expected_boarding_time"] == "08:32"
    assert coordinator.is_active is False
    assert coordinator.get_events_since(last_seq=0) == (0, [])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_llm_api_registered_invokable_and_unregistered_on_unload(
    hass: HomeAssistant,
) -> None:
    entry = await _setup_entry(hass=hass, active_state="off")
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    coordinator.engine.async_evaluate_commute = AsyncMock(
        return_value=_sample_active_state()
    )

    llm_context = llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant="conversation",
        device_id=None,
    )
    api_instance = await llm.async_get_api(hass, DOMAIN, llm_context)
    assert [tool.name for tool in api_instance.tools] == ["get_commute_status"]
    tool = api_instance.tools[0]

    result = cast(
        dict[str, Any],
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="get_commute_status",
                tool_args={"commute_id": "kolya_school", "force_refresh": True},
            ),
            llm_context,
        ),
    )
    assert result["commutes"][0]["commute_id"] == "kolya_school"
    assert result["commutes"][0]["recommended"]["route_label"] == "Southern"

    err_result = cast(
        dict[str, Any],
        await tool.async_call(
            hass,
            llm.ToolInput(
                tool_name="get_commute_status",
                tool_args={"commute_id": "does_not_exist"},
            ),
            llm_context,
        ),
    )
    assert "error" in err_result

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN not in {api.id for api in llm.async_get_apis(hass)}


def test_services_yaml_documents_get_status() -> None:
    services_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "commute_tracker"
        / "services.yaml"
    )
    assert services_path.is_file()
    parsed: dict[str, Any] = yaml.safe_load(services_path.read_text(encoding="utf-8"))
    assert "get_status" in parsed
    fields = parsed["get_status"]["fields"]
    assert "commute_id" in fields
    assert "entity_id" in fields
    assert "force_refresh" in fields
