"""Tests for frontend registration, static caching, and Lovelace storage."""

from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.http.server import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from custom_components.commute_tracker.const import (
    CARD_FILENAME,
    URL_BASE,
)
from custom_components.commute_tracker.frontend import (
    async_register_frontend,
    async_register_lovelace_resource,
    async_unregister_frontend,
    get_component_version,
)


def test_get_component_version_reads_manifest() -> None:
    """Ensure get_component_version extracts version from manifest.json."""
    version = get_component_version()
    assert version != "0.0.0"
    assert len(version.split(".")) >= 3


def test_get_component_version_missing_manifest() -> None:
    """Ensure get_component_version falls back to default if manifest is missing."""
    with patch.object(Path, "exists", return_value=False):
        assert get_component_version() == "0.0.0"


def test_get_component_version_corrupt_manifest(tmp_path: Path) -> None:
    """Ensure get_component_version handles corrupt manifest gracefully."""
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text("invalid json{{{", encoding="utf-8")
    with patch("custom_components.commute_tracker.frontend.Path") as mock_path_cls:
        mock_path_cls.return_value.parent.__truediv__.return_value = bad_manifest
        assert get_component_version() == "0.0.0"


async def test_async_register_frontend_registers_static_path_without_cache(
    hass: HomeAssistant,
) -> None:
    """Verify static path is registered with cache_headers=False."""
    registered_configs: list[StaticPathConfig] = []

    async def mock_register(configs: list[StaticPathConfig]) -> None:
        registered_configs.extend(configs)

    hass.http = MagicMock()
    hass.http.async_register_static_paths = mock_register

    await async_register_frontend(hass=hass)

    assert len(registered_configs) == 1
    config = registered_configs[0]
    assert config.url_path == URL_BASE
    assert config.cache_headers is False


async def test_async_register_frontend_registers_versioned_extra_js(
    hass: HomeAssistant,
) -> None:
    """Verify add_extra_js_url registers versioned script URL."""
    await async_register_frontend(hass=hass)
    version = get_component_version()
    expected_url = f"{URL_BASE}/{CARD_FILENAME}?v={version}"
    extra_urls = cast(
        set[str],
        cast(dict[Any, Any], hass.data).get(DATA_EXTRA_MODULE_URL, set()),
    )
    assert expected_url in extra_urls


async def test_async_register_lovelace_resource_creates_item_in_storage(
    hass: HomeAssistant,
) -> None:
    """Verify Lovelace storage collection creates resource when not present."""
    mock_resources = MagicMock()
    mock_resources.loaded = True
    mock_resources.async_items.return_value = []
    mock_resources.async_create_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    versioned_url = f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0"
    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    mock_resources.async_create_item.assert_awaited_once_with(
        {"res_type": "module", "url": versioned_url}
    )


async def test_async_register_lovelace_resource_updates_item_on_version_bump(
    hass: HomeAssistant,
) -> None:
    """Verify Lovelace storage collection updates resource when version changes."""
    mock_resources = MagicMock()
    mock_resources.loaded = True
    mock_resources.async_items.return_value = [
        {
            "id": "existing_res_id",
            "type": "module",
            "url": f"{URL_BASE}/{CARD_FILENAME}?v=0.0.9",
        }
    ]
    mock_resources.async_update_item = AsyncMock()
    mock_resources.async_create_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    versioned_url = f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0"
    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    mock_resources.async_update_item.assert_awaited_once_with(
        "existing_res_id",
        {"res_type": "module", "url": versioned_url},
    )
    mock_resources.async_create_item.assert_not_called()


async def test_async_register_lovelace_resource_noop_when_version_matches(
    hass: HomeAssistant,
) -> None:
    """Verify Lovelace storage collection does not mutate when resource is identical."""
    versioned_url = f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0"
    mock_resources = MagicMock()
    mock_resources.loaded = True
    mock_resources.async_items.return_value = [
        {
            "id": "current_res_id",
            "type": "module",
            "url": versioned_url,
        }
    ]
    mock_resources.async_update_item = AsyncMock()
    mock_resources.async_create_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    mock_resources.async_update_item.assert_not_called()
    mock_resources.async_create_item.assert_not_called()


async def test_async_register_lovelace_resource_loads_if_not_loaded(
    hass: HomeAssistant,
) -> None:
    """Verify Lovelace storage collection calls async_load when loaded is False."""
    mock_resources = MagicMock()
    mock_resources.loaded = False
    mock_resources.async_load = AsyncMock()
    mock_resources.async_items.return_value = []
    mock_resources.async_create_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    versioned_url = f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0"
    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    mock_resources.async_load.assert_awaited_once()
    mock_resources.async_create_item.assert_awaited_once()


async def test_async_register_lovelace_resource_skips_yaml_mode(
    hass: HomeAssistant,
) -> None:
    """Verify Lovelace resource registration is skipped in YAML mode."""
    mock_resources = MagicMock()
    mock_resources.async_create_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "yaml"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    versioned_url = f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0"
    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    mock_resources.async_create_item.assert_not_called()


async def test_async_register_lovelace_resource_legacy_interface(
    hass: HomeAssistant,
) -> None:
    """Verify fallback for legacy or mock Lovelace data interface."""
    mock_lovelace = MagicMock()
    del mock_lovelace.resources
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.async_get_resources = AsyncMock(return_value=[])
    mock_lovelace.async_create_resource = AsyncMock()
    hass.data["lovelace"] = mock_lovelace

    versioned_url = f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0"
    await async_register_lovelace_resource(hass=hass, versioned_url=versioned_url)

    mock_lovelace.async_create_resource.assert_awaited_once_with(
        {"res_type": "module", "url": versioned_url}
    )


async def test_async_register_frontend_schedules_listener_when_not_running(
    hass: HomeAssistant,
) -> None:
    """Verify startup listener is scheduled if Home Assistant is not running."""
    hass.is_running = False
    mock_resources = MagicMock()
    mock_resources.loaded = True
    mock_resources.async_items.return_value = []
    mock_resources.async_create_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    await async_register_frontend(hass=hass)
    mock_resources.async_create_item.reset_mock()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    mock_resources.async_create_item.assert_awaited_once()


async def test_async_unregister_frontend_removes_resource(
    hass: HomeAssistant,
) -> None:
    """Verify unregister deletes card resource from storage collection."""
    mock_resources = MagicMock()
    mock_resources.async_items.return_value = [
        {
            "id": "target_id",
            "url": f"{URL_BASE}/{CARD_FILENAME}?v=0.1.0",
        },
        {
            "id": "other_id",
            "url": "/local/other-card.js",
        },
    ]
    mock_resources.async_delete_item = AsyncMock()

    mock_lovelace = MagicMock()
    mock_lovelace.resource_mode = "storage"
    mock_lovelace.resources = mock_resources
    hass.data["lovelace"] = mock_lovelace

    await async_unregister_frontend(hass=hass)

    mock_resources.async_delete_item.assert_awaited_once_with("target_id")


async def test_async_register_frontend_exception_resilience(
    hass: HomeAssistant,
) -> None:
    """Verify frontend registration handles exceptions without crashing."""
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock(
        side_effect=RuntimeError("Disk failure")
    )
    hass.data["lovelace"] = MagicMock(side_effect=Exception("Lovelace crash"))

    await async_register_frontend(hass=hass)
