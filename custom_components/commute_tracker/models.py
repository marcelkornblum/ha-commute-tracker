"""Mode-agnostic transit domain models for the Commute Tracker integration."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from custom_components.commute_tracker.const import (
    DEFAULT_LINE_COLOUR,
    DEFAULT_LINE_ICON,
    DEFAULT_LINE_STATUS,
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


@dataclass(slots=True, frozen=True)
class LineStatus:
    """Normalised operational service status for a transit line."""

    status_label: str = DEFAULT_LINE_STATUS
    status_colour: str = DEFAULT_LINE_COLOUR
    status_icon: str = DEFAULT_LINE_ICON
    reason: str | None = None
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
class RouteConfig:
    """Normalised route configuration for a transit option within a commute."""

    route_id: str
    mode: TransitMode
    line: str
    provider: str = "tfl"
    walk_seconds: int | None = None
    prep_seconds: int | None = None
    grace_seconds: int | None = None
    boarding_stop: str | None = None
    destination_stop: str | None = None
    in_vehicle_duration_seconds: int | None = None
    alighting_walk_seconds: int | None = None
    target_arrival_time: str | None = None
    corridor_stops: list[str] = field(default_factory=list)

    @property
    def total_buffer_seconds(self) -> int:
        """Calculate combined walking and preparation buffer threshold."""
        return (self.walk_seconds or 0) + (self.prep_seconds or 0)


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
    corridor_progress_ratio: float = 0.0
    current_stop_location: str = ""
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
    target_arrival_time: str | None = None
    commute_title: str | None = None
    person_name: str | None = None

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
            walk_sec = r.get("walk_seconds")
            if (
                walk_sec is None
                and "walk_minutes" in r
                and r["walk_minutes"] is not None
            ):
                walk_sec = int(round(float(r["walk_minutes"]) * 60))

            prep_sec = r.get("prep_seconds")
            if (
                prep_sec is None
                and "prep_minutes" in r
                and r["prep_minutes"] is not None
            ):
                prep_sec = int(round(float(r["prep_minutes"]) * 60))

            grace_sec = r.get("grace_seconds")
            if (
                grace_sec is None
                and "grace_minutes" in r
                and r["grace_minutes"] is not None
            ):
                grace_sec = int(round(float(r["grace_minutes"]) * 60))

            routes.append(
                RouteConfig(
                    route_id=route_id,
                    mode=mode,
                    line=r["line"],
                    provider=r.get("provider", "tfl"),
                    walk_seconds=walk_sec,
                    prep_seconds=prep_sec,
                    grace_seconds=grace_sec,
                    boarding_stop=r.get("boarding_stop"),
                    destination_stop=r.get("destination_stop"),
                    in_vehicle_duration_seconds=r.get("in_vehicle_duration_seconds"),
                    alighting_walk_seconds=r.get("alighting_walk_seconds"),
                    target_arrival_time=r.get("target_arrival_time"),
                    corridor_stops=list(r.get("corridor_stops", [])),
                )
            )
        return cls(
            commute_id=data.get("commute_id", "commute"),
            routes=routes,
            target_arrival_time=data.get("target_arrival_time"),
            commute_title=data.get("commute_title"),
            person_name=data.get("person_name"),
        )
