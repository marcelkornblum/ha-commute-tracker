"""Unit tests for commute tracker mode-agnostic domain models."""

from dataclasses import FrozenInstanceError

import pytest

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)


def test_transit_mode_enum_members() -> None:
    """Verify TransitMode enum contains all core transit modes."""
    assert TransitMode.BUS.value == "bus"
    assert TransitMode.TRAIN.value == "train"
    assert TransitMode.TUBE.value == "tube"
    assert TransitMode.TRAM.value == "tram"
    assert TransitMode.FERRY.value == "ferry"
    assert str(TransitMode.BUS) == "bus"


def test_line_status_immutability_and_attributes() -> None:
    """Verify LineStatus dataclass is frozen and has expected attributes."""
    status = LineStatus(
        status_label="Good Service",
        status_colour="#00A859",
        status_icon="mdi:check-circle",
        reason=None,
    )
    assert status.status_label == "Good Service"
    assert status.status_colour == "#00A859"
    assert status.status_icon == "mdi:check-circle"
    assert status.reason is None

    with pytest.raises(FrozenInstanceError):
        # Mutating frozen dataclass must raise
        status.status_label = "Minor Delays"  # type: ignore[misc]


def test_departure_prediction_attributes() -> None:
    """Verify DeparturePrediction represents a single vehicle arrival."""
    prediction = DeparturePrediction(
        vehicle_id="SN16OJA",
        destination="Hackney Central",
        expected_time="2026-09-14T14:00:26Z",
        seconds_to_arrival=326,
        platform_or_bay="F",
        is_realtime=True,
        location="Approaching Whitehall",
    )
    assert prediction.vehicle_id == "SN16OJA"
    assert prediction.destination == "Hackney Central"
    assert prediction.expected_time == "2026-09-14T14:00:26Z"
    assert prediction.seconds_to_arrival == 326
    assert prediction.platform_or_bay == "F"
    assert prediction.is_realtime is True
    assert prediction.location == "Approaching Whitehall"

    with pytest.raises(FrozenInstanceError):
        prediction.seconds_to_arrival = 100  # type: ignore[misc]


def test_route_config_attributes() -> None:
    """Verify RouteConfig stores route identification and threshold parameters."""
    config = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        provider="tfl",
        walk_seconds=240,
        prep_seconds=120,
        grace_seconds=180,
        boarding_stop="490013766F",
        destination_stop="490005524F",
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        direction="outbound",
        corridor_stops=["490000248H", "490014496N", "490013766F"],
    )
    assert config.route_id == "bus_26"
    assert config.mode == TransitMode.BUS
    assert config.provider == "tfl"
    assert config.corridor_stops == ["490000248H", "490014496N", "490013766F"]
    assert config.total_buffer_seconds == 360  # walk + prep


def test_route_telemetry_aggregation() -> None:
    """Verify RouteTelemetry collates departures and corridor progress."""
    dep1 = DeparturePrediction(
        vehicle_id="SN16OJA",
        destination="Hackney Central",
        expected_time="2026-09-14T14:00:26Z",
        seconds_to_arrival=326,
    )
    dep2 = DeparturePrediction(
        vehicle_id="SN66WRP",
        destination="Hackney Central",
        expected_time="2026-09-14T14:07:00Z",
        seconds_to_arrival=720,
    )
    status = LineStatus(
        status_label="Good Service",
        status_colour="#00A859",
        status_icon="mdi:check-circle",
    )
    telemetry = RouteTelemetry(
        route_id="bus_26",
        line_id="26",
        mode=TransitMode.BUS,
        departures=[dep1, dep2],
        active_vehicle_id="SN16OJA",
        corridor_progress_ratio=0.85,
        current_stop_location="Horse Guards",
        line_status=status,
    )
    assert telemetry.route_id == "bus_26"
    assert len(telemetry.departures) == 2
    assert telemetry.lead_departure == dep1
    assert telemetry.active_vehicle_id == "SN16OJA"
    assert telemetry.corridor_progress_ratio == 0.85
    assert telemetry.current_stop_location == "Horse Guards"
    assert telemetry.line_status == status
