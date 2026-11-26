"""Platform providing native Home Assistant commute lifecycle event entities."""

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.commute_tracker.const import CONF_COMMUTE_ID, DOMAIN
from custom_components.commute_tracker.coordinator import CommuteCoordinator
from custom_components.commute_tracker.lifecycle import COMMUTE_EVENT_TYPES
from custom_components.commute_tracker.sensor import (
    derive_commute_unique_id,
    format_display_commute_name,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Commute Tracker event entities from YAML-configured coordinators."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})
    entities = [
        CommuteLifecycleEventEntity(coordinator=coordinator)
        for coordinator in coordinators.values()
    ]
    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Commute Tracker lifecycle event entity from a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})
    coordinator = coordinators.get(entry.entry_id) or coordinators.get(
        str(entry.data.get(CONF_COMMUTE_ID))
    )
    if coordinator is None:
        return

    async_add_entities([CommuteLifecycleEventEntity(coordinator=coordinator)])


class CommuteLifecycleEventEntity(CoordinatorEntity[CommuteCoordinator], EventEntity):
    """Native event entity emitting debounced commute lifecycle transitions."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:bell-ring-outline"
    _attr_translation_key = "commute_lifecycle"
    _attr_event_types = COMMUTE_EVENT_TYPES

    def __init__(self, coordinator: CommuteCoordinator) -> None:
        """Initialise lifecycle event entity for a commute coordinator."""
        super().__init__(coordinator=coordinator)
        cfg = coordinator.commute_config
        commute_title = cfg.commute_title or cfg.commute_id
        self._attr_name = format_display_commute_name(
            commute_title=commute_title,
            staging_mode=cfg.staging_mode,
        )
        self._attr_unique_id = derive_commute_unique_id(
            commute_title=commute_title,
            explicit_id=cfg.commute_id,
            staging_mode=cfg.staging_mode,
        )
        self._last_event_seq: int = 0

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates and flush any startup wake events."""
        await super().async_added_to_hass()
        self._emit_pending_events()

    @callback
    def _emit_pending_events(self) -> None:
        """Trigger Home Assistant event emissions for unread lifecycle events."""
        new_seq, pending = self.coordinator.get_events_since(
            last_seq=self._last_event_seq
        )
        self._last_event_seq = new_seq
        for lifecycle_event in pending:
            self._trigger_event(
                lifecycle_event.event_type.value,
                lifecycle_event.data,
            )
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Emit newly recorded commute lifecycle events on coordinator updates."""
        self._emit_pending_events()
