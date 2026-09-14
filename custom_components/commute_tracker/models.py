"""Mode-agnostic transit domain models for the Commute Tracker integration."""

from dataclasses import dataclass, field
from enum import StrEnum


class TransitMode(StrEnum):
    """Supported transit modes for routes and providers."""

    BUS = "bus"
    TRAIN = "train"
    TUBE = "tube"
    TRAM = "tram"
    FERRY = "ferry"


@dataclass(slots=True, frozen=True)
class LineStatus:
    """Normalised operational service status for a transit line."""

    status_label: str
    status_colour: str
    status_icon: str
    reason: str | None = None


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
    walk_seconds: int = 0
    prep_seconds: int = 0
    grace_seconds: int = 0
    boarding_stop: str | None = None
    destination_stop: str | None = None
    in_vehicle_duration_seconds: int | None = None
    alighting_walk_seconds: int | None = None
    direction: str | None = None
    corridor_stops: list[str] = field(default_factory=list)

    @property
    def total_buffer_seconds(self) -> int:
        """Calculate combined walking and preparation buffer threshold."""
        return self.walk_seconds + self.prep_seconds


@dataclass(slots=True, frozen=True)
class RouteTelemetry:
    """Aggregated live telemetry and predictions for a single route."""

    route_id: str
    line_id: str
    mode: TransitMode
    departures: list[DeparturePrediction] = field(default_factory=list)
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
