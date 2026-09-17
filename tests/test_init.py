"""Tests for component setup, configuration ingestion, and frontend registration."""

from typing import Any, cast
from unittest.mock import AsyncMock, patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant

from custom_components.commute_tracker import (
    async_register_frontend,
    async_setup,
    async_unload_entry,
)
from custom_components.commute_tracker.const import (
    CARD_FILENAME,
    DOMAIN,
    URL_BASE,
)
from custom_components.commute_tracker.coordinator import CommuteCoordinator


async def test_async_setup_empty_config(hass: HomeAssistant) -> None:
    """Test component setup with empty configuration."""
    result = await async_setup(hass, {})
    assert result is True
    assert DOMAIN in hass.data
    card_url = f"{URL_BASE}/{CARD_FILENAME}"
    extra_urls = cast(Any, hass.data.get(DATA_EXTRA_MODULE_URL, set()))
    assert any(str(url).startswith(card_url) for url in extra_urls)


async def test_async_setup_with_commutes_and_providers(hass: HomeAssistant) -> None:
    """Test component setup with valid commutes and provider configurations."""
    raw_config = {
        DOMAIN: {
            "providers": {
                "tfl": {
                    "app_id": "test_id",
                    "app_key": "test_key",
                }
            },
            "commutes": [
                {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.work_commute_active",
                    "routes": [
                        {
                            "id": "bus_73",
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        }
                    ],
                }
            ],
        }
    }

    with patch.object(
        CommuteCoordinator, "async_setup", new_callable=AsyncMock
    ) as mock_coord_setup:
        result = await async_setup(hass, raw_config)
        assert result is True
        assert DOMAIN in hass.data
        assert "coordinators" in hass.data[DOMAIN]
        assert "work_commute" in hass.data[DOMAIN]["coordinators"]
        coordinator = hass.data[DOMAIN]["coordinators"]["work_commute"]
        assert isinstance(coordinator, CommuteCoordinator)
        assert coordinator.commute_config.commute_id == "work_commute"
        mock_coord_setup.assert_called_once()

    card_url = f"{URL_BASE}/{CARD_FILENAME}"
    extra_urls = cast(Any, hass.data[DATA_EXTRA_MODULE_URL])
    assert any(str(url).startswith(card_url) for url in extra_urls)


async def test_async_register_frontend_creates_dir(
    hass: HomeAssistant,
) -> None:
    """Verify frontend auto-registration ensures target frontend directory exists."""
    await async_register_frontend(hass)
    card_url = f"{URL_BASE}/{CARD_FILENAME}"
    extra_urls = cast(Any, hass.data[DATA_EXTRA_MODULE_URL])
    assert any(str(url).startswith(card_url) for url in extra_urls)


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Verify async_unload_entry invokes unload on all active coordinators."""
    raw_config = {
        DOMAIN: {
            "commutes": [
                {
                    "name": "Work",
                    "active_sensor": "binary_sensor.work_active",
                    "routes": [
                        {
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        }
                    ],
                }
            ]
        }
    }
    with patch.object(CommuteCoordinator, "async_setup", new_callable=AsyncMock):
        await async_setup(hass, raw_config)

    coordinator = hass.data[DOMAIN]["coordinators"]["work"]
    with patch.object(coordinator, "async_unload") as mock_unload:
        result = await async_unload_entry(hass)
        assert result is True
        mock_unload.assert_called_once()


async def test_async_setup_with_root_level_cascading(
    hass: HomeAssistant,
) -> None:
    """Verify async_setup propagates root-level defaults to CommuteConfig and routes."""
    raw_config = {
        DOMAIN: {
            "rollup_strategy": "soonest",
            "route_late_buffer_seconds": 180,
            "prep_seconds": 210,
            "boarding_walk_seconds": 330,
            "poll_interval": 45,
            "grace_seconds": 75,
            "commutes": [
                {
                    "name": "Work Commute",
                    "active_sensor": "binary_sensor.work_active",
                    "routes": [
                        {
                            "mode": "bus",
                            "line": "73",
                            "boarding_stop": "490013766F",
                        }
                    ],
                }
            ],
        }
    }
    with patch.object(CommuteCoordinator, "async_setup", new_callable=AsyncMock):
        result = await async_setup(hass, raw_config)
        assert result is True

    coordinator = hass.data[DOMAIN]["coordinators"]["work_commute"]
    commute_cfg = coordinator.commute_config
    assert commute_cfg.rollup_strategy.value == "soonest"
    assert commute_cfg.route_late_buffer_seconds == 180
    assert commute_cfg.prep_seconds == 210
    assert commute_cfg.boarding_walk_seconds == 330
    assert commute_cfg.poll_interval == 45
    assert commute_cfg.grace_seconds == 75

    route_cfg = commute_cfg.routes[0]
    assert route_cfg.prep_seconds == 210
    assert route_cfg.boarding_walk_seconds == 330
