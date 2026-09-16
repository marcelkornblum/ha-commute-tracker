"""Integration test suite replaying 90 consecutive TfL time-series snapshots."""

import json
from pathlib import Path
from typing import Any

from scripts.analyze_telemetry import (
    SnapshotTelemetry,
    analyse_snapshots,
)


def test_manifest_integrity(
    series_manifest: dict[str, Any], time_series_dir: Path
) -> None:
    """Verify series manifest configuration, snapshot counts, and file existence."""
    assert series_manifest["iterations"] == 90
    assert series_manifest["interval_seconds"] == 30.0
    assert series_manifest["bus_line"] == "26"
    assert series_manifest["train_line"] == "southeastern"
    assert series_manifest["tube_line"] == "central"
    assert series_manifest["total_duration_seconds"] > 2700.0

    snapshots = series_manifest["snapshots"]
    assert len(snapshots) == 90

    for entry in snapshots:
        snapshot_file = time_series_dir / entry["relative_file"]
        assert snapshot_file.exists()
        assert entry["vehicle_count"] > 0


def test_all_snapshots_schema_completeness(time_series_dir: Path) -> None:
    """Verify all 90 snapshots adhere to schema and advance monotonically."""
    previous_elapsed = -1.0

    for index in range(1, 91):
        snapshot_file = time_series_dir / f"snapshot_{index:03d}.json"
        assert snapshot_file.exists()

        data: dict[str, Any] = json.loads(snapshot_file.read_text(encoding="utf-8"))
        assert data["snapshot_index"] == index
        assert data["elapsed_seconds"] > previous_elapsed
        previous_elapsed = data["elapsed_seconds"]

        bus_section = data["bus"]
        assert bus_section["line"] == "26"
        assert isinstance(bus_section["line_arrivals"], list)
        assert isinstance(bus_section["line_status"], list)
        assert isinstance(bus_section["discrete_stop_arrivals"], dict)
        assert "target_trafalgar_square" in bus_section["discrete_stop_arrivals"]

        train_section = data["train"]
        assert train_section["line"] == "southeastern"
        assert train_section["origin"] == "910GCHRX"
        assert train_section["destination"] == "910GLNDNBDC"
        assert isinstance(train_section["journey_results"], dict)
        assert "journeys" in train_section["journey_results"]
        assert isinstance(train_section["line_status"], list)

        tube_section = data["tube"]
        assert tube_section["line"] == "central"
        assert tube_section["origin"] == "940GZZLUTCR"
        assert tube_section["destination"] == "940GZZLULVT"
        assert isinstance(tube_section["line_arrivals"], list)
        assert isinstance(tube_section["line_status"], list)
        assert isinstance(tube_section["journey_results"], dict)
        assert isinstance(tube_section["discrete_stop_arrivals"], dict)
        assert "target_tottenham_court_road" in tube_section["discrete_stop_arrivals"]


def test_synchronised_initial_fixture_sets_consistency(
    nelson_commute_dir: Path, time_series_dir: Path
) -> None:
    """Verify Sets 1-6 are perfectly synchronised with snapshot 001."""
    snap1_file = time_series_dir / "snapshot_001.json"
    snap1 = json.loads(snap1_file.read_text(encoding="utf-8"))

    set1_target = (
        nelson_commute_dir / "set1_poc_bus_discrete" / "08_target_trafalgar_square.json"
    )
    assert set1_target.exists()
    set1_data = json.loads(set1_target.read_text(encoding="utf-8"))
    snap_target_bus = snap1["bus"]["discrete_stop_arrivals"]["target_trafalgar_square"]
    assert set1_data == snap_target_bus

    set2_journey = (
        nelson_commute_dir / "set2_poc_train_discrete" / "01_journey_results.json"
    )
    set4_journey = (
        nelson_commute_dir / "set4_consolidated_train" / "journey_results.json"
    )
    assert set2_journey.exists()
    assert set4_journey.exists()
    set2_data = json.loads(set2_journey.read_text(encoding="utf-8"))
    set4_data = json.loads(set4_journey.read_text(encoding="utf-8"))
    assert set2_data == snap1["train"]["journey_results"]
    assert set4_data == snap1["train"]["journey_results"]

    set3_arrivals = nelson_commute_dir / "set3_consolidated_bus" / "line_arrivals.json"
    assert set3_arrivals.exists()
    set3_data = json.loads(set3_arrivals.read_text(encoding="utf-8"))
    assert set3_data == snap1["bus"]["line_arrivals"]

    set5_journey = (
        nelson_commute_dir / "set5_poc_tube_discrete" / "15_journey_results.json"
    )
    set6_journey = (
        nelson_commute_dir / "set6_consolidated_tube" / "journey_results.json"
    )
    assert set5_journey.exists()
    assert set6_journey.exists()
    set5_data = json.loads(set5_journey.read_text(encoding="utf-8"))
    set6_data = json.loads(set6_journey.read_text(encoding="utf-8"))
    assert set5_data == snap1["tube"]["journey_results"]
    assert set6_data == snap1["tube"]["journey_results"]

    set6_arrivals = nelson_commute_dir / "set6_consolidated_tube" / "line_arrivals.json"
    assert set6_arrivals.exists()
    set6_arrivals_data = json.loads(set6_arrivals.read_text(encoding="utf-8"))
    assert set6_arrivals_data == snap1["tube"]["line_arrivals"]


def test_bus_fleet_tracking_and_handovers() -> None:
    """Verify bus vehicle tracking lifecycles and rollover handovers."""
    timeline, metadata = analyse_snapshots()
    assert len(timeline) == 90

    bus_lifecycles = metadata["bus_lifecycles"]
    assert len(bus_lifecycles) >= 6

    assert "SN16OJA" in bus_lifecycles
    lead_bus = bus_lifecycles["SN16OJA"]
    assert lead_bus["first_seen_snap"] == 1
    assert lead_bus["first_seen_tts"] == 326
    assert lead_bus["min_tts"] == 75
    assert lead_bus["last_seen_snap"] == 9

    assert "SN66WRP" in bus_lifecycles
    follow_bus = bus_lifecycles["SN66WRP"]
    assert follow_bus["first_seen_snap"] == 1
    assert follow_bus["last_seen_snap"] >= 20
    assert follow_bus["min_tts"] < follow_bus["first_seen_tts"]


def test_southeastern_rail_departures_progression() -> None:
    """Verify Southeastern rail timetable progressions and rolling forward schedules."""
    timeline, metadata = analyse_snapshots()
    departures = metadata["train_departures"]
    assert len(departures) >= 10

    departure_times = {item["departure"] for item in departures}
    assert "2026-09-14T14:01:00" in departure_times
    assert "2026-09-14T14:04:00" in departure_times
    assert "2026-09-14T14:55:00" in departure_times


def test_tube_central_line_progression() -> None:
    """Verify Central Line Underground train set progressions along the corridor."""
    timeline, metadata = analyse_snapshots()
    tube_lifecycles = metadata["tube_lifecycles"]
    assert len(tube_lifecycles) >= 15

    assert "012" in tube_lifecycles
    set_012 = tube_lifecycles["012"]
    assert set_012["first_seen_snap"] == 1
    assert set_012["last_loc"] == "At Platform"


def test_master_rollup_arbitration_simulation() -> None:
    """Verify commute arbitration arbitrates across all 3 route options."""
    timeline, _ = analyse_snapshots()
    assert len(timeline) == 90

    winning_routes: set[str] = {t.master_active_option for t in timeline}
    winning_stages: set[str] = {t.master_urgency_stage for t in timeline}

    assert "bus_26" in winning_routes
    assert "train_southeastern" in winning_routes
    assert "tube_central" in winning_routes

    assert "leave_now" in winning_stages
    assert "prepare" in winning_stages or "relaxed" in winning_stages

    snap_1: SnapshotTelemetry = timeline[0]
    assert snap_1.master_active_option == "bus_26"
    assert snap_1.master_urgency_stage == "leave_now"
