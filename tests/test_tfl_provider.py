"""Unit tests for the TfLTransitProvider against static JSON fixtures."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from custom_components.commute_tracker.models import (
    RouteConfig,
    TransitMode,
)
from custom_components.commute_tracker.providers.tfl import TfLTransitProvider


@pytest.fixture
def tfl_provider() -> TfLTransitProvider:
    """Return an instantiated TfLTransitProvider."""
    return TfLTransitProvider()


def test_tfl_provider_metadata(tfl_provider: TfLTransitProvider) -> None:
    """Verify TfL provider metadata and supported modes."""
    assert tfl_provider.provider_id == "tfl"
    assert TransitMode.BUS in tfl_provider.supported_modes
    assert TransitMode.TRAIN in tfl_provider.supported_modes
    assert TransitMode.TUBE in tfl_provider.supported_modes
    assert TransitMode.TRAM in tfl_provider.supported_modes


def test_parse_bus_line_status(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify parsing TfL bus line status from fixture."""
    status_path = nelson_commute_dir / "set3_consolidated_bus" / "line_status.json"
    status_json = json.loads(status_path.read_text(encoding="utf-8"))

    line_status = tfl_provider.parse_line_status(payload=status_json)
    assert line_status.status_label == "Special Service"
    assert "STRAND, WC2" in (line_status.reason or "")
    assert line_status.status_colour != ""
    assert line_status.status_icon.startswith("mdi:")


def test_parse_bus_line_arrivals(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify parsing consolidated bus line arrivals targeting Trafalgar Square."""
    arrivals_path = nelson_commute_dir / "set3_consolidated_bus" / "line_arrivals.json"
    arrivals_json = json.loads(arrivals_path.read_text(encoding="utf-8"))

    target_stop = "490013766F"  # Trafalgar Square
    predictions = tfl_provider.parse_bus_arrivals(
        payload=arrivals_json,
        target_stop=target_stop,
    )

    assert len(predictions) > 0
    # Predictions should be sorted ascending by seconds_to_arrival
    assert predictions[0].seconds_to_arrival <= predictions[-1].seconds_to_arrival
    # Each prediction should have vehicle_id, destination, platform_or_bay
    assert predictions[0].vehicle_id is not None
    assert predictions[0].platform_or_bay == "F"
    assert predictions[0].is_realtime is True


def test_parse_rail_journey_results(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify parsing rail journey results from Charing Cross to London Bridge."""
    rail_path = nelson_commute_dir / "set4_consolidated_train" / "journey_results.json"
    rail_json = json.loads(rail_path.read_text(encoding="utf-8"))

    predictions = tfl_provider.parse_rail_journey_results(
        payload=rail_json,
        from_station="910GCHRX",
        to_station="910GLNDNBDC",
        reference_time_iso="2026-09-14T13:54:57Z",
    )

    assert len(predictions) > 0
    # Predictions should be sorted by departure time / seconds_to_arrival
    assert predictions[0].expected_time is not None
    destination = predictions[0].destination
    assert "London Bridge" in destination or "Dartford" in destination


def test_parse_tube_line_arrivals(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify parsing tube line arrivals targeting Tottenham Court Road."""
    tube_path = nelson_commute_dir / "set6_consolidated_tube" / "line_arrivals.json"
    tube_json = json.loads(tube_path.read_text(encoding="utf-8"))

    target_stop = "940GZZLUTCR"  # Tottenham Court Road
    predictions = tfl_provider.parse_tube_arrivals(
        payload=tube_json,
        target_stop=target_stop,
        direction="inbound",
    )

    assert len(predictions) > 0
    assert predictions[0].seconds_to_arrival <= predictions[-1].seconds_to_arrival
    assert predictions[0].vehicle_id is not None


def test_calculate_bus_corridor_progress(tfl_provider: TfLTransitProvider) -> None:
    """Verify calculating progress ratio along corridor stops."""
    corridor = [
        "490000248H",  # Victoria
        "490014496N",  # Westminster Cathedral
        "490003384SA",  # Westminster City Hall
        "490010260SC",  # St James's Park
        "490014495R",  # Westminster Abbey
        "490015048A",  # Westminster
        "490008376N",  # Horse Guards
        "490013766F",  # Trafalgar Square (Target)
    ]
    # Current location matches Horse Guards (index 6 out of 7 steps)
    ratio, label = tfl_provider.calculate_corridor_progress(
        current_naptan="490008376N",
        corridor_stops=corridor,
        stop_names={"490008376N": "Horse Guards"},
    )
    assert 0.8 < ratio < 0.95
    assert label == "Horse Guards"


def test_tfl_provider_telemetry_from_snapshot(
    tfl_provider: TfLTransitProvider,
    snapshot_loader: Callable[[int], dict[str, Any]],
) -> None:
    """Verify converting snapshot 001 into RouteTelemetry for all 3 routes."""
    snapshot = snapshot_loader(1)

    bus_route = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        provider="tfl",
        walk_seconds=240,
        prep_seconds=120,
        grace_seconds=180,
        boarding_stop="490013766F",
        destination_stop="490005524F",
        corridor_stops=[
            "490000248H",
            "490014496N",
            "490003384SA",
            "490010260SC",
            "490014495R",
            "490015048A",
            "490008376N",
            "490013766F",
        ],
    )

    telemetry = tfl_provider.extract_telemetry_from_snapshot(
        route=bus_route,
        snapshot=snapshot,
    )
    assert telemetry.route_id == "bus_26"
    assert telemetry.mode == TransitMode.BUS
    assert telemetry.active_vehicle_id == "SN16OJA"
    assert len(telemetry.departures) > 0
    assert telemetry.lead_departure is not None
    assert telemetry.lead_departure.seconds_to_arrival == 326
    assert telemetry.line_status is not None
