"""Diagnostics support for Commute Tracker."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.commute_tracker.const import (
    CONF_API_KEY,
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_COMMUTE_ID,
    DOMAIN,
)
from custom_components.commute_tracker.coordinator import CommuteCoordinator

TO_REDACT: set[str] = {
    CONF_APP_ID,
    CONF_APP_KEY,
    CONF_API_KEY,
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return sanitised configuration and latest coordinator state for an entry."""
    merged_config: dict[str, Any] = {**entry.data, **entry.options}
    redacted_config = async_redact_data(merged_config, TO_REDACT)

    domain_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})
    coordinator = coordinators.get(entry.entry_id) or coordinators.get(
        str(merged_config.get(CONF_COMMUTE_ID))
    )

    state_payload: dict[str, Any] | None = None
    if coordinator is not None:
        state_payload = {
            "is_active": coordinator.is_active,
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                int(coordinator.update_interval.total_seconds())
                if coordinator.update_interval is not None
                else None
            ),
            "data": (
                asdict(coordinator.data) if coordinator.data is not None else None
            ),
        }

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "unique_id": entry.unique_id,
        },
        "config": redacted_config,
        "state": state_payload,
    }
