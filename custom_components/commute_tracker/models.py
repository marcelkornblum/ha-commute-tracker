"""Mode-agnostic transit domain models for the Commute Tracker integration."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from custom_components.commute_tracker.const import (
    DEFAULT_LINE_COLOR,
    DEFAULT_LINE_ICON,
    DEFAULT_LINE_STATUS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    DEFAULT_STAGING_MODE,
)


class TransitMode(StrEnum):
    """Supported transit modes for routes and providers."""

    BUS = "bus"
    TRAIN = "train"
    TUBE = "tube"
    TRAM = "tram"
    FERRY = "ferry"


class UrgencyStage(StrEnum):
    """Lifecycle urgency stages for commute departures."""

    STANDBY = "standby"
    RELAXED = "relaxed"
    PREPARE = "prepare"
    LEAVE_NOW = "leave_now"


class RollupStrategy(StrEnum):
    """Arbitration strategies for Master Rollup route selection."""

    SOONEST = "soonest"
    LATEST = "latest"
    LATE_WITH_BUFFER = "late_with_buffer"


class RouteDirection(StrEnum):
    """Direction of travel relative to home."""

    FROM_HOME = "from_home"
    TO_HOME = "to_home"


@dataclass(slots=True, frozen=True)
class PillBadge:
    """Styling and text tokens for Lovelace card pill badge."""

    label: str
    color: str
    bg: str
    border: str


@dataclass(slots=True, frozen=True)
class LineStatus:
    """Normalised operational service status for a transit line."""

    status_label: str = DEFAULT_LINE_STATUS
    status_color: str = DEFAULT_LINE_COLOR
    status_icon: str = DEFAULT_LINE_ICON
    detail: str | None = None
    is_delayed: bool = False
    is_cancelled: bool = False


@dataclass(slots=True, frozen=True)
class DeparturePrediction:
    """Individual vehicle departure or arrival prediction."""

    vehicle_id: str | None = None
    destination: str = ""
    expected_time: str | None = None
    seconds_to_arrival: int = 0
    platform_or_bay: str | None = None
    is_realtime: bool = True
    location: str = ""


@dataclass(slots=True, frozen=True)
class CorridorStop:
    """Normalised stop point along a transit corridor."""

    id: str
    name: str
    is_target: bool = False
    scheduled_lead_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "is_target": self.is_target,
            "scheduled_lead_seconds": self.scheduled_lead_seconds,
        }

    def __getitem__(self, key: str) -> Any:
        """Allow subscript access for backwards compatibility."""
        return getattr(self, key)


@dataclass(slots=True, frozen=True)
class RouteConfig:
    """Normalised route configuration for a transit option within a commute."""

    route_id: str
    mode: TransitMode
    line: str
    provider: str = "tfl"
    direction: RouteDirection = RouteDirection.FROM_HOME
    route_color: str | None = None
    boarding_stop: str | None = None
    alighting_stop: str | None = None
    destination: str | None = None
    boarding_walk_seconds: int | None = None
    prep_seconds: int | None = None
    grace_seconds: int | None = None
    grace_fraction: float | None = None
    transit_duration_seconds: int | None = None
    alighting_walk_seconds: int | None = None
    corridor_stops: list[str] = field(default_factory=list)
    corridor_stop_names: dict[str, str] = field(default_factory=dict)
    name: str | None = None

    @property
    def total_buffer_seconds(self) -> int:
        """Calculate combined walking and preparation buffer threshold."""
        return (self.boarding_walk_seconds or 0) + (self.prep_seconds or 0)


@dataclass(slots=True, frozen=True)
class RouteTelemetry:
    """Aggregated live telemetry and predictions for a single route."""

    route_id: str
    line_id: str
    mode: TransitMode
    departures: list[DeparturePrediction] = field(default_factory=list)
    corridor_departures: dict[str, list[DeparturePrediction]] = field(
        default_factory=dict
    )
    stop_names: dict[str, str] = field(default_factory=dict)
    active_vehicle_id: str | None = None
    line_status: LineStatus | None = None

    @property
    def lead_departure(self) -> DeparturePrediction | None:
        """Return the closest or earliest upcoming departure prediction."""
        if not self.departures:
            return None
        return self.departures[0]


@dataclass(slots=True, frozen=True)
class CommuteConfig:
    """Strongly-typed configuration for an entire commute."""

    commute_id: str
    routes: list[RouteConfig]
    active_sensor: str | None = None
    target_destination_time: str | None = None
    commute_title: str | None = None
    person: str | None = None
    person_name: str | None = None
    person_picture: str | None = None
    destination: str | None = None
    grace_seconds: int | None = None
    grace_fraction: float | None = None
    rollup_strategy: RollupStrategy = RollupStrategy.LATE_WITH_BUFFER
    route_late_buffer_seconds: int = DEFAULT_ROUTE_LATE_BUFFER_SECONDS
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS
    prep_seconds: int | None = None
    boarding_walk_seconds: int | None = None
    staging_mode: bool = DEFAULT_STAGING_MODE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommuteConfig":
        """Construct strongly-typed CommuteConfig from raw dictionary.

        :param data: Configuration dictionary.
        :return: CommuteConfig instance.
        """
        routes: list[RouteConfig] = []
        for r in data.get("routes", []):
            route_id = r.get("id") or r.get("route_id", "")
            mode = TransitMode(r["mode"])
            dir_raw = r.get("direction", RouteDirection.FROM_HOME.value)
            try:
                direction = RouteDirection(dir_raw)
            except ValueError:
                direction = RouteDirection.FROM_HOME

            walk_sec = (
                int(r["boarding_walk_seconds"])
                if r.get("boarding_walk_seconds") is not None
                else None
            )
            prep_sec = (
                int(r["prep_seconds"]) if r.get("prep_seconds") is not None else None
            )
            grace_sec = (
                int(r["grace_seconds"]) if r.get("grace_seconds") is not None else None
            )
            grace_frac = (
                float(r["grace_fraction"])
                if r.get("grace_fraction") is not None
                else None
            )
            transit_dur = (
                int(r["transit_duration_seconds"])
                if r.get("transit_duration_seconds") is not None
                else None
            )
            alight_walk = (
                int(r["alighting_walk_seconds"])
                if r.get("alighting_walk_seconds") is not None
                else None
            )

            routes.append(
                RouteConfig(
                    route_id=route_id,
                    mode=mode,
                    line=r["line"],
                    provider=r.get("provider", "tfl"),
                    direction=direction,
                    route_color=r.get("route_color"),
                    boarding_stop=r.get("boarding_stop"),
                    alighting_stop=r.get("alighting_stop"),
                    destination=r.get("destination"),
                    boarding_walk_seconds=walk_sec,
                    prep_seconds=prep_sec,
                    grace_seconds=grace_sec,
                    grace_fraction=grace_frac,
                    transit_duration_seconds=transit_dur,
                    alighting_walk_seconds=alight_walk,
                    corridor_stops=list(r.get("corridor_stops", [])),
                    corridor_stop_names=dict(r.get("corridor_stop_names", {})),
                    name=r.get("name"),
                )
            )

        grace_sec = (
            int(data["grace_seconds"])
            if data.get("grace_seconds") is not None
            else None
        )
        grace_frac = (
            float(data["grace_fraction"])
            if data.get("grace_fraction") is not None
            else None
        )

        strategy_raw = data.get("rollup_strategy", "late_with_buffer")
        try:
            strategy = RollupStrategy(strategy_raw)
        except ValueError:
            strategy = RollupStrategy.LATE_WITH_BUFFER

        route_late_buf = data.get("route_late_buffer_seconds")
        if route_late_buf is not None:
            route_late_buf = int(route_late_buf)
        else:
            route_late_buf = DEFAULT_ROUTE_LATE_BUFFER_SECONDS

        commute_id = data.get("id") or data.get("commute_id", "commute")
        title = data.get("name") or data.get("commute_title")
        active_sensor = data.get("active_sensor")
        poll_interval = int(data.get("poll_interval", DEFAULT_POLL_INTERVAL_SECONDS))
        person_picture = data.get("person_picture")
        prep_sec = (
            int(data["prep_seconds"]) if data.get("prep_seconds") is not None else None
        )
        boarding_walk_sec = (
            int(data["boarding_walk_seconds"])
            if data.get("boarding_walk_seconds") is not None
            else None
        )
        staging_mode = bool(data.get("staging_mode", DEFAULT_STAGING_MODE))

        return cls(
            commute_id=commute_id,
            routes=routes,
            active_sensor=active_sensor,
            target_destination_time=data.get("target_destination_time"),
            commute_title=title,
            person=data.get("person"),
            person_name=data.get("person_name"),
            person_picture=person_picture,
            destination=data.get("destination"),
            grace_seconds=grace_sec,
            grace_fraction=grace_frac,
            rollup_strategy=strategy,
            route_late_buffer_seconds=route_late_buf,
            poll_interval=poll_interval,
            prep_seconds=prep_sec,
            boarding_walk_seconds=boarding_walk_sec,
            staging_mode=staging_mode,
        )
