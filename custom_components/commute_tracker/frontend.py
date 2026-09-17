"""Frontend asset and Lovelace resource registration for Commute Tracker."""

import json
import logging
from pathlib import Path
from typing import Any, cast

from homeassistant.components.frontend import (
    DATA_EXTRA_MODULE_URL,
    add_extra_js_url,
)
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from custom_components.commute_tracker.const import (
    CARD_FILENAME,
    URL_BASE,
)

MODE_STORAGE = "storage"

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "async_register_frontend",
    "async_register_lovelace_resource",
    "async_unregister_frontend",
    "get_component_version",
]


def get_component_version() -> str:
    """Retrieve integration version string from manifest.json."""
    manifest_path = Path(__file__).parent / "manifest.json"
    if not manifest_path.exists():
        return "0.0.0"
    try:
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest_data: dict[str, Any] = json.load(manifest_file)
            return str(manifest_data.get("version", "0.0.0"))
    except Exception as err:
        _LOGGER.debug("Could not read integration manifest: %s", err)
        return "0.0.0"


async def _async_sync_storage_collection(
    resources: Any,
    versioned_url: str,
) -> None:
    """Synchronise resource within a ResourceStorageCollection."""
    if hasattr(resources, "loaded") and not resources.loaded:
        if hasattr(resources, "async_load"):
            try:
                await resources.async_load()
            except Exception as err:
                _LOGGER.debug("Failed to load Lovelace storage collection: %s", err)
                return

    if not hasattr(resources, "async_items"):
        return

    base_url = versioned_url.split("?")[0]
    existing_items: list[dict[str, Any]] = resources.async_items()

    matching_item: dict[str, Any] | None = None
    for item in existing_items:
        raw_url = str(item.get("url", ""))
        if raw_url.split("?")[0] == base_url:
            matching_item = item
            break

    if matching_item is None:
        if hasattr(resources, "async_create_item"):
            _LOGGER.debug("Registering Lovelace card resource: %s", versioned_url)
            await resources.async_create_item(
                {"res_type": "module", "url": versioned_url}
            )
        return

    if matching_item.get("url") != versioned_url and hasattr(
        resources, "async_update_item"
    ):
        _LOGGER.debug(
            "Updating Lovelace card resource %s to %s",
            matching_item.get("id"),
            versioned_url,
        )
        await resources.async_update_item(
            matching_item["id"],
            {"res_type": "module", "url": versioned_url},
        )


async def _async_sync_legacy_lovelace(
    lovelace_data: Any,
    versioned_url: str,
) -> None:
    """Synchronise resource with legacy or mock Lovelace interfaces."""
    base_url = versioned_url.split("?")[0]
    try:
        existing: list[dict[str, Any]] = await lovelace_data.async_get_resources()
        if not any(str(r.get("url", "")).split("?")[0] == base_url for r in existing):
            await lovelace_data.async_create_resource(
                {"res_type": "module", "url": versioned_url}
            )
    except Exception as err:
        _LOGGER.debug("Legacy Lovelace resource registration failed: %s", err)


async def async_register_lovelace_resource(
    hass: HomeAssistant,
    versioned_url: str,
) -> None:
    """Register or update custom card Lovelace storage resource."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if not lovelace_data:
            return

        resource_mode = getattr(
            lovelace_data,
            "resource_mode",
            getattr(lovelace_data, "mode", None),
        )
        if resource_mode and resource_mode != MODE_STORAGE:
            _LOGGER.debug(
                "Lovelace is in %s mode; skipping storage resource registration",
                resource_mode,
            )
            return

        resources = getattr(lovelace_data, "resources", None)
        if resources is not None:
            await _async_sync_storage_collection(
                resources=resources,
                versioned_url=versioned_url,
            )
            return

        if hasattr(lovelace_data, "async_get_resources") and hasattr(
            lovelace_data, "async_create_resource"
        ):
            await _async_sync_legacy_lovelace(
                lovelace_data=lovelace_data,
                versioned_url=versioned_url,
            )
    except Exception as err:
        _LOGGER.debug("Lovelace resource auto-registration encountered error: %s", err)


async def async_unregister_frontend(hass: HomeAssistant) -> None:
    """Remove Lovelace card module resource on unload."""
    try:
        lovelace_data = hass.data.get("lovelace")
        if not lovelace_data:
            return

        resources = getattr(lovelace_data, "resources", None)
        if (
            resources is None
            or not hasattr(resources, "async_items")
            or not hasattr(resources, "async_delete_item")
        ):
            return

        card_base_url = f"{URL_BASE}/{CARD_FILENAME}"
        for item in resources.async_items():
            if str(item.get("url", "")).split("?")[0] == card_base_url:
                await resources.async_delete_item(item["id"])
    except Exception as err:
        _LOGGER.debug("Failed to unregister Lovelace resource: %s", err)


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register custom Lovelace card static path, script URL, and storage resource."""
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
                        cache_headers=False,
                    )
                ]
            )
        except Exception as err:
            _LOGGER.debug(
                "Static path registration skipped or already registered: %s",
                err,
            )

    version = get_component_version()
    card_url = f"{URL_BASE}/{CARD_FILENAME}"
    versioned_url = f"{card_url}?v={version}"

    try:
        cast(dict[Any, Any], hass.data).setdefault(DATA_EXTRA_MODULE_URL, set())
        add_extra_js_url(hass, versioned_url)
    except Exception as err:
        _LOGGER.debug("Frontend JS URL registration failed: %s", err)

    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    if not hass.is_running:

        async def _on_started(_event: Any) -> None:
            await async_register_lovelace_resource(
                hass=hass,
                versioned_url=versioned_url,
            )

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)
