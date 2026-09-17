"""Commute Tracker custom component."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from custom_components.commute_tracker.config_validation import (
    COMMUTE_TRACKER_SCHEMA,
    CONFIG_SCHEMA,
)
from custom_components.commute_tracker.const import (
    CONF_COMMUTES,
    CONF_PROVIDERS,
    DOMAIN,
)
from custom_components.commute_tracker.coordinator import CommuteCoordinator
from custom_components.commute_tracker.engine import CommuteEngine
from custom_components.commute_tracker.frontend import (
    async_register_frontend,
    async_unregister_frontend,
)
from custom_components.commute_tracker.models import CommuteConfig
from custom_components.commute_tracker.providers.base import (
    TransitProviderRegistry,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

__all__ = [
    "CONFIG_SCHEMA",
    "async_register_frontend",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "async_unregister_frontend",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Commute Tracker component."""
    hass.data.setdefault(DOMAIN, {})
    hass.config.components.add(DOMAIN)
    await async_register_frontend(hass=hass)

    if DOMAIN not in config:
        return True

    commute_tracker_conf: dict[str, Any] = COMMUTE_TRACKER_SCHEMA(config[DOMAIN])
    providers_conf: dict[str, Any] = commute_tracker_conf.get(CONF_PROVIDERS, {})

    session = async_get_clientsession(hass)
    registry = TransitProviderRegistry(session=session)
    registry.discover_providers()

    for provider_id, p_conf in providers_conf.items():
        if provider_id in registry.registered_provider_ids and isinstance(p_conf, dict):
            registry.get_provider(provider_id=provider_id, **p_conf)

    hass.data[DOMAIN]["registry"] = registry
    coordinators: dict[str, CommuteCoordinator] = {}

    for commute_raw in commute_tracker_conf.get(CONF_COMMUTES, []):
        commute_cfg = CommuteConfig.from_dict(data=commute_raw)
        engine = CommuteEngine(
            config=commute_cfg,
            registry=registry,
            session=session,
        )
        coordinator = CommuteCoordinator(
            hass=hass,
            config=commute_cfg,
            engine=engine,
        )
        await coordinator.async_setup()
        coordinators[commute_cfg.commute_id] = coordinator

    hass.data[DOMAIN]["coordinators"] = coordinators
    await async_load_platform(
        hass,
        Platform.SENSOR,
        DOMAIN,
        {},
        config,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Commute Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await async_register_frontend(hass=hass)

    registry = hass.data[DOMAIN].get("registry")
    session = async_get_clientsession(hass)
    if registry is None:
        registry = TransitProviderRegistry(session=session)
        registry.discover_providers()
        hass.data[DOMAIN]["registry"] = registry

    merged_data: dict[str, Any] = {**entry.data, **entry.options}
    providers_conf: dict[str, Any] = merged_data.get(CONF_PROVIDERS, {})
    for provider_id, p_conf in providers_conf.items():
        if provider_id in registry.registered_provider_ids and isinstance(p_conf, dict):
            registry.get_provider(provider_id=provider_id, **p_conf)

    commute_cfg = CommuteConfig.from_dict(data=merged_data)
    engine = CommuteEngine(
        config=commute_cfg,
        registry=registry,
        session=session,
    )
    coordinator = CommuteCoordinator(
        hass=hass,
        config=commute_cfg,
        engine=engine,
    )
    await coordinator.async_setup()

    coordinators: dict[str, CommuteCoordinator] = hass.data[DOMAIN].setdefault(
        "coordinators", {}
    )
    coordinators[entry.entry_id] = coordinator
    coordinators[commute_cfg.commute_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry | None = None
) -> bool:
    """Unload Commute Tracker coordinators and listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})

    if entry is not None:
        unload_ok = await hass.config_entries.async_forward_entry_unload(
            entry, Platform.SENSOR
        )
        if unload_ok:
            coordinator = coordinators.pop(entry.entry_id, None)
            if coordinator is not None:
                coordinator.async_unload()
                coordinators.pop(coordinator.commute_config.commute_id, None)
            return True
        return False

    for coordinator in list(coordinators.values()):
        coordinator.async_unload()
    coordinators.clear()
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload commute tracker entry on options update."""
    await hass.config_entries.async_reload(entry.entry_id)
