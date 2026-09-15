"""Commute Tracker custom component."""

import logging
from pathlib import Path
from typing import Any, cast

from homeassistant.components.frontend import (
    DATA_EXTRA_MODULE_URL,
    add_extra_js_url,
)
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from custom_components.commute_tracker.config_validation import (
    COMMUTE_TRACKER_SCHEMA,
    CONFIG_SCHEMA,
)
from custom_components.commute_tracker.const import (
    CARD_FILENAME,
    CONF_COMMUTES,
    CONF_PROVIDERS,
    DOMAIN,
    URL_BASE,
)
from custom_components.commute_tracker.coordinator import CommuteCoordinator
from custom_components.commute_tracker.engine import CommuteEngine
from custom_components.commute_tracker.models import CommuteConfig
from custom_components.commute_tracker.providers.base import (
    TransitProviderRegistry,
)

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CONFIG_SCHEMA",
    "async_register_frontend",
    "async_setup",
    "async_unload_entry",
]


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register custom Lovelace card static path and frontend script resource."""
    frontend_dir = Path(__file__).parent / "frontend"
    if not frontend_dir.exists():
        frontend_dir.mkdir(parents=True, exist_ok=True)

    if hasattr(hass, "http") and hass.http is not None:
        try:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        url_path=URL_BASE,
                        path=str(frontend_dir),
                        cache_headers=True,
                    )
                ]
            )
        except Exception as err:
            _LOGGER.debug(
                "Static path registration skipped or already registered: %s",
                err,
            )

    try:
        cast(dict[Any, Any], hass.data).setdefault(DATA_EXTRA_MODULE_URL, set())
        add_extra_js_url(hass, f"{URL_BASE}/{CARD_FILENAME}")
    except Exception as err:
        _LOGGER.debug("Frontend JS URL registration failed: %s", err)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Commute Tracker component."""
    hass.data.setdefault(DOMAIN, {})
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Any = None) -> bool:
    """Unload Commute Tracker coordinators and listeners."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})
    for coordinator in coordinators.values():
        coordinator.async_unload()
    return True
