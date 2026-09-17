"""Platform providing Master Rollup and Child Route commute sensors."""

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from custom_components.commute_tracker.const import (
    CONF_COMMUTE_ID,
    DEFAULT_BUS_COLOR,
    DEFAULT_FERRY_COLOR,
    DEFAULT_LINE_COLOR,
    DEFAULT_LINE_ICON,
    DEFAULT_LINE_STATUS,
    DEFAULT_TRAIN_COLOR,
    DEFAULT_TRAM_COLOR,
    DEFAULT_TUBE_COLOR,
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

MODE_COLORS: dict[TransitMode, str] = {
    TransitMode.BUS: DEFAULT_BUS_COLOR,
    TransitMode.TRAIN: DEFAULT_TRAIN_COLOR,
    TransitMode.TUBE: DEFAULT_TUBE_COLOR,
    TransitMode.TRAM: DEFAULT_TRAM_COLOR,
    TransitMode.FERRY: DEFAULT_FERRY_COLOR,
}


def derive_commute_unique_id(
    commute_title: str,
    explicit_id: str | None = None,
    staging_mode: bool = False,
) -> str:
    """Generate master sensor unique_id with fallback to slugified name."""
    base = explicit_id if explicit_id else slugify(commute_title)
    if staging_mode and not base.endswith("_staging"):
        return f"{base}_staging"
    return base


def derive_child_unique_id(
    commute_unique_id: str,
    route_id: str,
    explicit_id: str | None = None,
    staging_mode: bool = False,
) -> str:
    """Generate child route sensor unique_id with fallback to composite key."""
    if explicit_id:
        base = explicit_id
    else:
        clean_commute_uid = commute_unique_id.removesuffix("_staging")
        base = f"{clean_commute_uid}_{route_id}"
    if staging_mode and not base.endswith("_staging"):
        return f"{base}_staging"
    return base


def _format_display_commute_name(
    commute_title: str,
    staging_mode: bool = False,
) -> str:
    """Format human-readable commute name, prefixing 'Commute ' if absent."""
    base = (
        commute_title
        if commute_title.lower().startswith("commute")
        else f"Commute {commute_title}"
    )
    if staging_mode and not base.lower().endswith("staging"):
        return f"{base} Staging"
    return base


def _format_child_display_name(
    master_display_name: str,
    route_display: str,
    staging_mode: bool = False,
) -> str:
    """Format human-readable child route name with optional staging suffix."""
    base = f"{master_display_name} {route_display}"
    if staging_mode and not base.lower().endswith("staging"):
        return f"{base} Staging"
    return base


def _format_route_display(route_config: RouteConfig) -> str:
    """Format human-readable route suffix with mode and line identifier."""
    if route_config.name:
        return route_config.name
    mode_label = route_config.mode.value
    line_label = route_config.line
    if line_label.lower().startswith(mode_label):
        return line_label
    return f"{mode_label} {line_label}"


def _create_commute_sensors(coordinator: CommuteCoordinator) -> list[SensorEntity]:
    """Create master rollup sensor and child route sensors for a coordinator."""
    sensors: list[SensorEntity] = [CommuteMasterRollupSensor(coordinator=coordinator)]
    for route_cfg in coordinator.commute_config.routes:
        sensors.append(
            CommuteChildRouteSensor(
                coordinator=coordinator,
                route_config=route_cfg,
            )
        )
    return sensors


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
        entities.extend(_create_commute_sensors(coordinator=coordinator))

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Commute Tracker sensors from a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators: dict[str, CommuteCoordinator] = domain_data.get("coordinators", {})
    coordinator = coordinators.get(entry.entry_id) or coordinators.get(
        str(entry.data.get(CONF_COMMUTE_ID))
    )
    if coordinator is None:
        return

    async_add_entities(_create_commute_sensors(coordinator=coordinator))


class CommuteMasterRollupSensor(CoordinatorEntity[CommuteCoordinator], SensorEntity):
    """Master Rollup commute sensor arbitrating primary status and urgency."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:transit-connection-variant"

    def __init__(self, coordinator: CommuteCoordinator) -> None:
        """Initialise master rollup sensor."""
        super().__init__(coordinator=coordinator)
        cfg = coordinator.commute_config
        commute_title = cfg.commute_title or cfg.commute_id
        self._attr_name = _format_display_commute_name(
            commute_title=commute_title,
            staging_mode=cfg.staging_mode,
        )
        self._attr_unique_id = derive_commute_unique_id(
            commute_title=commute_title,
            explicit_id=cfg.commute_id,
            staging_mode=cfg.staging_mode,
        )

    def _get_child_entity_ids(self) -> list[str]:
        """Compute expected child route entity IDs for dashboard navigation."""
        cfg = self.coordinator.commute_config
        commute_title = cfg.commute_title or cfg.commute_id
        base_master_name = _format_display_commute_name(
            commute_title=commute_title,
            staging_mode=False,
        )
        child_ids: list[str] = []
        for route in cfg.routes:
            route_display = _format_route_display(route_config=route)
            child_name = _format_child_display_name(
                master_display_name=base_master_name,
                route_display=route_display,
                staging_mode=cfg.staging_mode,
            )
            child_slug = slugify(child_name)
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
                active_route_cfg.route_color
                or MODE_COLORS.get(active_route_cfg.mode, DEFAULT_LINE_COLOR)
            )
            if active_route_cfg
            else DEFAULT_LINE_COLOR
        )

        attrs: dict[str, Any] = {
            "commute_id": cfg.commute_id,
            "commute_title": cfg.commute_title or cfg.commute_id,
            "active_option": master.active_option,
            "is_relevant": self.coordinator.is_active and master.is_active,
            "urgency_stage": master.urgency_stage.value,
            "leave_by_time": master.leave_by_time,
            "expected_boarding_time": master.expected_boarding_time,
            "expected_destination_time": master.expected_destination_time,
            "seconds_to_leave": master.seconds_to_leave,
            "seconds_to_board": master.seconds_to_board,
            "expected_destination_margin_seconds": (
                master.expected_destination_margin_seconds
            ),
            "route_label": master.route_label,
            "route_color": route_color,
            "destination": master.destination,
            "will_arrive_on_time": master.will_arrive_on_time,
            "timeliness": master.timeliness,
            "strategy": (
                master.strategy.value
                if hasattr(master.strategy, "value")
                else str(master.strategy)
            ),
            "line_status_label": (
                line_status.status_label
                if line_status is not None
                else DEFAULT_LINE_STATUS
            ),
            "line_status_detail": (
                line_status.detail if line_status is not None else None
            ),
            "line_status_color": (
                line_status.status_color
                if line_status is not None
                else DEFAULT_LINE_COLOR
            ),
            "line_status_icon": (
                line_status.status_icon
                if line_status is not None
                else DEFAULT_LINE_ICON
            ),
            "is_delayed": line_status.is_delayed if line_status is not None else False,
            "is_cancelled": (
                line_status.is_cancelled if line_status is not None else False
            ),
            "pill_label": pill.label if pill is not None else "Standby",
            "pill_color": pill.color if pill is not None else "#8E8E93",
            "pill_bg": pill.bg if pill is not None else "rgba(142,142,147,0.2)",
            "pill_border": pill.border if pill is not None else "#8E8E93",
            "next_summary": master.next_summary,
            "options": [r.route_id for r in cfg.routes],
            "child_entities": self._get_child_entity_ids(),
        }

        if cfg.person_name:
            attrs["person_name"] = cfg.person_name
        if cfg.person_picture:
            attrs["person_picture"] = cfg.person_picture

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
        base_master_name = _format_display_commute_name(
            commute_title=commute_title,
            staging_mode=False,
        )
        route_display = _format_route_display(route_config=route_config)
        self._attr_name = _format_child_display_name(
            master_display_name=base_master_name,
            route_display=route_display,
            staging_mode=cfg.staging_mode,
        )
        self._attr_icon = MODE_ICONS.get(
            route_config.mode, "mdi:transit-connection-variant"
        )
        self._attr_unique_id = derive_child_unique_id(
            commute_unique_id=cfg.commute_id,
            route_id=route_config.route_id,
            staging_mode=cfg.staging_mode,
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

        route_col = self.route_config.route_color or MODE_COLORS.get(
            self.route_config.mode, DEFAULT_LINE_COLOR
        )
        direction_val = (
            self.route_config.direction.value
            if hasattr(self.route_config.direction, "value")
            else str(self.route_config.direction)
        )

        attrs: dict[str, Any] = {
            "commute_id": cfg.commute_id,
            "route_id": self.route_config.route_id,
            "mode": self.route_config.mode.value,
            "line": self.route_config.line,
            "provider": self.route_config.provider,
            "direction": direction_val,
            "route_label": child.route_label,
            "route_color": route_col,
            "destination": child.destination,
            "is_relevant": self.coordinator.is_active and child.is_active,
            "urgency_stage": child.urgency_stage.value,
            "leave_by_time": child.leave_by_time,
            "expected_boarding_time": child.expected_boarding_time,
            "expected_alighting_time": child.expected_alighting_time,
            "expected_destination_time": child.expected_destination_time,
            "seconds_to_leave": child.seconds_to_leave,
            "seconds_to_board": child.seconds_to_board,
            "expected_destination_margin_seconds": (
                child.expected_destination_margin_seconds
            ),
            "will_arrive_on_time": child.will_arrive_on_time,
            "timeliness": child.timeliness,
            "vehicle_id": child.vehicle_id,
            "corridor_location": child.corridor_location,
            "corridor_progress": child.corridor_progress,
            "corridor_stops": child.corridor_stops,
            "next_vehicle_id": child.next_vehicle_id,
            "seconds_to_next_board": child.seconds_to_next_board,
            "next_summary": child.next_summary,
            "line_status_label": (
                line_status.status_label
                if line_status is not None
                else DEFAULT_LINE_STATUS
            ),
            "line_status_detail": (
                line_status.detail if line_status is not None else None
            ),
            "line_status_color": (
                line_status.status_color
                if line_status is not None
                else DEFAULT_LINE_COLOR
            ),
            "line_status_icon": (
                line_status.status_icon
                if line_status is not None
                else DEFAULT_LINE_ICON
            ),
            "is_delayed": line_status.is_delayed if line_status is not None else False,
            "is_cancelled": (
                line_status.is_cancelled if line_status is not None else False
            ),
            "pill_label": pill.label if pill is not None else "Standby",
            "pill_color": pill.color if pill is not None else "#8E8E93",
            "pill_bg": pill.bg if pill is not None else "rgba(142,142,147,0.2)",
            "pill_border": pill.border if pill is not None else "#8E8E93",
        }

        return attrs
