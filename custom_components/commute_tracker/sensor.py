"""Platform providing Master Rollup and Child Route commute sensors."""

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from custom_components.commute_tracker.const import (
    DEFAULT_BUS_COLOUR,
    DEFAULT_FERRY_COLOUR,
    DEFAULT_LINE_COLOUR,
    DEFAULT_LINE_ICON,
    DEFAULT_LINE_STATUS,
    DEFAULT_TRAIN_COLOUR,
    DEFAULT_TRAM_COLOUR,
    DEFAULT_TUBE_COLOUR,
    DOMAIN,
)
from custom_components.commute_tracker.coordinator import CommuteCoordinator
from custom_components.commute_tracker.engine import (
    ChildRouteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import RouteConfig, TransitMode

MODE_ICONS: dict[TransitMode, str] = {
    TransitMode.BUS: "mdi:bus",
    TransitMode.TRAIN: "mdi:train",
    TransitMode.TUBE: "mdi:subway-variant",
    TransitMode.TRAM: "mdi:tram",
    TransitMode.FERRY: "mdi:ferry",
}

MODE_COLOURS: dict[TransitMode, str] = {
    TransitMode.BUS: DEFAULT_BUS_COLOUR,
    TransitMode.TRAIN: DEFAULT_TRAIN_COLOUR,
    TransitMode.TUBE: DEFAULT_TUBE_COLOUR,
    TransitMode.TRAM: DEFAULT_TRAM_COLOUR,
    TransitMode.FERRY: DEFAULT_FERRY_COLOUR,
}


def derive_commute_unique_id(
    commute_title: str,
    explicit_id: str | None = None,
) -> str:
    """Generate master sensor unique_id with fallback to slugified name."""
    if explicit_id:
        return explicit_id
    return slugify(commute_title)


def derive_child_unique_id(
    commute_unique_id: str,
    route_id: str,
    explicit_id: str | None = None,
) -> str:
    """Generate child route sensor unique_id with fallback to composite key."""
    if explicit_id:
        return explicit_id
    return f"{commute_unique_id}_{route_id}"


def _format_display_commute_name(commute_title: str) -> str:
    """Format human-readable commute name, prefixing 'Commute ' if absent."""
    if commute_title.lower().startswith("commute"):
        return commute_title
    return f"Commute {commute_title}"


def _format_route_display(route_config: RouteConfig) -> str:
    """Format human-readable route suffix with mode and line identifier."""
    if route_config.name:
        return route_config.name
    mode_label = route_config.mode.value
    line_label = route_config.line
    if line_label.lower().startswith(mode_label):
        return line_label
    return f"{mode_label} {line_label}"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Commute Tracker sensor platform from discovered coordinators."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})

    entities: list[SensorEntity] = []
    for coordinator in coordinators.values():
        master_sensor = CommuteMasterRollupSensor(coordinator=coordinator)
        entities.append(master_sensor)
        for route_cfg in coordinator.commute_config.routes:
            child_sensor = CommuteChildRouteSensor(
                coordinator=coordinator,
                route_config=route_cfg,
            )
            entities.append(child_sensor)

    async_add_entities(entities)


class CommuteMasterRollupSensor(CoordinatorEntity[CommuteCoordinator], SensorEntity):
    """Master Rollup commute sensor arbitrating primary status and urgency."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:transit-connection-variant"

    def __init__(self, coordinator: CommuteCoordinator) -> None:
        """Initialise master rollup sensor."""
        super().__init__(coordinator=coordinator)
        cfg = coordinator.commute_config
        commute_title = cfg.commute_title or cfg.commute_id
        self._attr_name = _format_display_commute_name(commute_title=commute_title)
        self._attr_unique_id = derive_commute_unique_id(
            commute_title=commute_title,
            explicit_id=cfg.commute_id,
        )

    def _get_child_entity_ids(self) -> list[str]:
        """Compute expected child route entity IDs for dashboard navigation."""
        child_ids: list[str] = []
        for route in self.coordinator.commute_config.routes:
            route_display = _format_route_display(route_config=route)
            child_slug = slugify(f"{self._attr_name} {route_display}")
            child_ids.append(f"sensor.{child_slug}")
        return child_ids

    @property
    def native_value(self) -> str | None:
        """Return master rollup urgency stage or idle state."""
        if self.coordinator.data is None:
            return None
        master: MasterRollupState = self.coordinator.data.master_rollup
        if not self.coordinator.is_active or not master.is_active:
            return "idle"
        return master.urgency_stage.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return arbitrated commute attributes, timeliness, and pill tokens."""
        if self.coordinator.data is None:
            return {}
        master: MasterRollupState = self.coordinator.data.master_rollup
        cfg = self.coordinator.commute_config
        pill = master.pill_badge
        line_status = master.line_status

        active_route_cfg = next(
            (r for r in cfg.routes if r.route_id == master.active_option),
            None,
        )
        route_color = (
            (
                active_route_cfg.corridor_color
                or MODE_COLOURS.get(active_route_cfg.mode, DEFAULT_LINE_COLOUR)
            )
            if active_route_cfg
            else DEFAULT_LINE_COLOUR
        )

        attrs: dict[str, Any] = {
            "commute_id": cfg.commute_id,
            "commute_title": cfg.commute_title or cfg.commute_id,
            "active_option": master.active_option,
            "is_relevant": self.coordinator.is_active and master.is_active,
            "urgency_stage": master.urgency_stage.value,
            "expected_time": master.expected_time,
            "seconds_to_arrival": master.seconds_to_arrival,
            "minutes_to_arrival": master.minutes_to_arrival,
            "leave_in_seconds": master.leave_in_seconds,
            "leave_in_minutes": master.leave_in_minutes,
            "leave_by_time": master.leave_by_time,
            "route_label": master.route_label,
            "route_color": route_color,
            "corridor_color": route_color,
            "route_destination": master.route_destination,
            "strategy": (
                master.strategy.value
                if hasattr(master.strategy, "value")
                else str(master.strategy)
            ),
            "will_arrive_in_time": master.will_arrive_in_time,
            "target_slack_minutes": master.target_slack_minutes,
            "timeliness": master.timeliness,
            "estimated_transit_arrival": master.estimated_transit_arrival,
            "estimated_destination_arrival": master.estimated_destination_arrival,
            "next_summary": master.next_summary,
            "next_bus_summary": master.next_summary,
            "child_entities": self._get_child_entity_ids(),
            "options": [r.route_id for r in cfg.routes],
            "route_options": [r.route_id for r in cfg.routes],
        }

        if cfg.person_name:
            attrs["person_name"] = cfg.person_name
        if cfg.person_picture:
            attrs["person_picture"] = cfg.person_picture

        if line_status is not None:
            attrs["line_status"] = line_status.status_label
            attrs["line_status_color"] = line_status.status_colour
            attrs["line_status_icon"] = line_status.status_icon
            attrs["line_status_reason"] = line_status.reason
            attrs["is_delayed"] = line_status.is_delayed
            attrs["is_cancelled"] = line_status.is_cancelled
        else:
            attrs["line_status"] = DEFAULT_LINE_STATUS
            attrs["line_status_color"] = DEFAULT_LINE_COLOUR
            attrs["line_status_icon"] = DEFAULT_LINE_ICON

        if pill is not None:
            attrs["pill_label"] = pill.label
            attrs["pill_color"] = pill.color
            attrs["pill_bg"] = pill.bg
            attrs["pill_border"] = pill.border
        else:
            attrs["pill_label"] = "Standby"
            attrs["pill_color"] = "#8E8E93"
            attrs["pill_bg"] = "rgba(142,142,147,0.2)"
            attrs["pill_border"] = "#8E8E93"

        return attrs


class CommuteChildRouteSensor(CoordinatorEntity[CommuteCoordinator], SensorEntity):
    """Child route sensor exposing per-route metrics and corridor telemetry."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: CommuteCoordinator,
        route_config: RouteConfig,
    ) -> None:
        """Initialise child route sensor."""
        super().__init__(coordinator=coordinator)
        self.route_config = route_config
        cfg = coordinator.commute_config
        commute_title = cfg.commute_title or cfg.commute_id
        master_display_name = _format_display_commute_name(commute_title=commute_title)
        route_display = _format_route_display(route_config=route_config)
        self._attr_name = f"{master_display_name} {route_display}"
        self._attr_icon = MODE_ICONS.get(
            route_config.mode, "mdi:transit-connection-variant"
        )
        self._attr_unique_id = derive_child_unique_id(
            commute_unique_id=cfg.commute_id,
            route_id=route_config.route_id,
        )

    def _get_child_state(self) -> ChildRouteState | None:
        """Retrieve evaluated state for this route from coordinator payload."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.child_routes.get(self.route_config.route_id)

    @property
    def native_value(self) -> str | None:
        """Return child route urgency stage or idle state."""
        child = self._get_child_state()
        if child is None or not self.coordinator.is_active or not child.is_active:
            return "idle"
        return child.urgency_stage.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return route attributes, corridor progression, and leave countdowns."""
        child = self._get_child_state()
        if child is None:
            return {}
        cfg = self.coordinator.commute_config
        pill = child.pill_badge
        line_status = child.line_status

        route_col = (
            self.route_config.corridor_color
            or MODE_COLOURS.get(self.route_config.mode, DEFAULT_LINE_COLOUR)
        )

        attrs: dict[str, Any] = {
            "commute_id": cfg.commute_id,
            "route_id": self.route_config.route_id,
            "option_id": self.route_config.route_id,
            "mode": self.route_config.mode.value,
            "vehicle_type": self.route_config.mode.value,
            "line": self.route_config.line,
            "provider": self.route_config.provider,
            "route_label": child.route_label,
            "route_color": route_col,
            "route_destination": child.route_destination,
            "destination": child.route_destination,
            "is_relevant": self.coordinator.is_active and child.is_active,
            "urgency_stage": child.urgency_stage.value,
            "expected_time": child.scheduled_departure or "",
            "seconds_to_arrival": child.seconds_to_arrival,
            "minutes_to_arrival": child.minutes_to_arrival,
            "leave_in_seconds": child.leave_in_seconds,
            "leave_in_minutes": child.leave_in_minutes,
            "leave_by_time": child.leave_by_time or "",
            "vehicle_id": child.vehicle_id,
            "corridor_location": child.corridor_location,
            "corridor_progress": child.corridor_progress,
            "corridor_stops": child.corridor_stops,
            "corridor_color": route_col,
            "will_arrive_in_time": child.will_arrive_in_time,
            "target_slack_minutes": child.target_slack_minutes,
            "timeliness": child.timeliness,
            "estimated_transit_arrival": child.estimated_transit_arrival or "",
            "estimated_destination_arrival": (
                child.estimated_destination_arrival or ""
            ),
            "next_vehicle_id": child.next_vehicle_id,
            "next_seconds_to_arrival": child.next_seconds_to_arrival,
            "next_summary": child.next_summary,
        }

        if line_status is not None:
            attrs["line_status"] = line_status.status_label
            attrs["line_status_color"] = line_status.status_colour
            attrs["line_status_icon"] = line_status.status_icon
            attrs["line_status_reason"] = line_status.reason
            attrs["is_delayed"] = line_status.is_delayed
            attrs["is_cancelled"] = line_status.is_cancelled
        else:
            attrs["line_status"] = DEFAULT_LINE_STATUS
            attrs["line_status_color"] = DEFAULT_LINE_COLOUR
            attrs["line_status_icon"] = DEFAULT_LINE_ICON

        if pill is not None:
            attrs["pill_label"] = pill.label
            attrs["pill_color"] = pill.color
            attrs["pill_bg"] = pill.bg
            attrs["pill_border"] = pill.border
        else:
            attrs["pill_label"] = "Standby"
            attrs["pill_color"] = "#8E8E93"
            attrs["pill_bg"] = "rgba(142,142,147,0.2)"
            attrs["pill_border"] = "#8E8E93"

        return attrs
