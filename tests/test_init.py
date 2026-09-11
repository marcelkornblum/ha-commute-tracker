"""Tests for component setup."""

from homeassistant.core import HomeAssistant

from custom_components.commute_tracker import async_setup
from custom_components.commute_tracker.const import DOMAIN


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test initial component setup."""
    result = await async_setup(hass, {})
    assert result is True
    assert DOMAIN in hass.data
