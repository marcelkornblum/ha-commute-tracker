"""Commute Tracker custom component."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Commute Tracker component."""
    hass.data.setdefault(DOMAIN, {})
    return True
