"""Home Assistant response action and Assist LLM API for Commute Tracker."""

import functools
from dataclasses import dataclass
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import llm
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonObjectType

from custom_components.commute_tracker.const import DOMAIN
from custom_components.commute_tracker.coordinator import (
    CommuteCoordinator,
    create_idle_commute_state,
)
from custom_components.commute_tracker.status import build_commute_status

SERVICE_GET_STATUS = "get_status"
LLM_TOOL_GET_STATUS = "get_commute_status"

_SERVICE_GET_STATUS_SCHEMA = vol.Schema(
    {
        vol.Optional("commute_id"): str,
        vol.Optional("entity_id"): str,
        vol.Optional("force_refresh", default=False): bool,
    }
)


def _iter_unique_coordinators(hass: HomeAssistant) -> list[CommuteCoordinator]:
    """Return deduplicated CommuteCoordinator instances registered in hass.data."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators_map: dict[str, CommuteCoordinator] = domain_data.get(
        "coordinators", {}
    )
    seen: set[int] = set()
    unique: list[CommuteCoordinator] = []
    for coordinator in coordinators_map.values():
        key = id(coordinator)
        if key not in seen:
            seen.add(key)
            unique.append(coordinator)
    return unique


def _resolve_commute_id_from_entity(hass: HomeAssistant, entity_id: str) -> str | None:
    """Resolve commute_id from a Home Assistant sensor entity's state attributes."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    commute_id = state.attributes.get("commute_id")
    if isinstance(commute_id, str) and commute_id.strip():
        return commute_id.strip()
    return None


def _select_coordinators(
    hass: HomeAssistant,
    commute_id: str | None = None,
    entity_id: str | None = None,
) -> list[CommuteCoordinator]:
    """Select target coordinators matching optional commute_id or entity_id filter."""
    coordinators = _iter_unique_coordinators(hass=hass)
    target_commute_id = commute_id.strip() if commute_id else None

    if entity_id:
        resolved = _resolve_commute_id_from_entity(hass=hass, entity_id=entity_id)
        if resolved is None:
            raise ServiceValidationError(
                f"Entity '{entity_id}' is not an active Commute Tracker sensor."
            )
        target_commute_id = resolved

    if not target_commute_id:
        return coordinators

    matched = [
        coord
        for coord in coordinators
        if coord.commute_config.commute_id == target_commute_id
    ]
    if not matched:
        raise ServiceValidationError(
            f"No configured commute found with id '{target_commute_id}'."
        )
    return matched


async def async_collect_commute_statuses(
    hass: HomeAssistant,
    *,
    commute_id: str | None = None,
    entity_id: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Build status payloads for matching commutes with optional one-shot live fetch."""
    coordinators = _select_coordinators(
        hass=hass,
        commute_id=commute_id,
        entity_id=entity_id,
    )
    commutes: list[dict[str, Any]] = []
    for coordinator in coordinators:
        person_name, _ = coordinator.resolve_person_profile()
        if force_refresh:
            state = await coordinator.engine.async_evaluate_commute(
                reference_time=dt_util.now()
            )
        else:
            state = coordinator.data or create_idle_commute_state(
                config=coordinator.commute_config
            )
        commutes.append(
            build_commute_status(
                state=state,
                config=coordinator.commute_config,
                is_active=coordinator.is_active,
                person_name=person_name,
                live_override=force_refresh,
            )
        )
    return {"commutes": commutes}


async def _async_handle_get_status(
    hass: HomeAssistant,
    call: ServiceCall,
) -> ServiceResponse:
    """Handle commute_tracker.get_status service calls."""
    return await async_collect_commute_statuses(
        hass=hass,
        commute_id=call.data.get("commute_id"),
        entity_id=call.data.get("entity_id"),
        force_refresh=bool(call.data.get("force_refresh", False)),
    )


class GetCommuteStatusTool(llm.Tool):
    """Assist LLM tool returning structured commute status and natural summary."""

    name = LLM_TOOL_GET_STATUS
    description = (
        "Get live or cached transit commute status, recommended departure time, "
        "vehicle corridor location, line disruptions, and per-route comparison. "
        "Set force_refresh to true to fetch live departures outside the active window."
    )
    parameters = vol.Schema(
        {
            vol.Optional("commute_id"): str,
            vol.Optional("force_refresh", default=False): bool,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Execute commute status lookup for an Assist LLM conversation."""
        try:
            return await async_collect_commute_statuses(
                hass=hass,
                commute_id=tool_input.tool_args.get("commute_id"),
                force_refresh=bool(tool_input.tool_args.get("force_refresh", False)),
            )
        except ServiceValidationError as err:
            return {"error": str(err)}


@dataclass(slots=True, kw_only=True)
class CommuteTrackerLLMAPI(llm.API):
    """Home Assistant LLM API exposing Commute Tracker transit status tools."""

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return an APIInstance exposing the commute status tool."""
        return llm.APIInstance(
            api=self,
            api_prompt=(
                "Use get_commute_status to answer questions about when to leave, "
                "which bus or train to take, vehicle locations, and expected arrival "
                "times."
            ),
            llm_context=llm_context,
            tools=[GetCommuteStatusTool()],
        )


def async_register_assist(hass: HomeAssistant) -> None:
    """Register commute_tracker.get_status service and native Assist LLM API."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not hass.services.has_service(DOMAIN, SERVICE_GET_STATUS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_STATUS,
            functools.partial(_async_handle_get_status, hass),
            schema=_SERVICE_GET_STATUS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    if "llm_api_unreg" not in domain_data:
        api = CommuteTrackerLLMAPI(
            hass=hass,
            id=DOMAIN,
            name="Commute Tracker",
        )
        domain_data["llm_api_unreg"] = llm.async_register_api(hass, api)


def async_unregister_assist(hass: HomeAssistant) -> None:
    """Unregister commute_tracker.get_status service and native Assist LLM API."""
    domain_data = hass.data.get(DOMAIN, {})
    unreg = domain_data.pop("llm_api_unreg", None)
    if callable(unreg):
        unreg()

    if hass.services.has_service(DOMAIN, SERVICE_GET_STATUS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_STATUS)
