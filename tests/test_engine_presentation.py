"""Unit tests for pure Python presentation, timing, and contract attribute synthesis."""

from datetime import datetime

from custom_components.commute_tracker.engine import CommuteEngine
from custom_components.commute_tracker.models import (
    CommuteConfig,
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
    UrgencyStage,
)
from custom_components.commute_tracker.timeliness import (
    calculate_journey_arrival_times,
    calculate_leave_by_time,
    calculate_pill_badge,
    format_next_summary,
)


def test_calculate_leave_by_time() -> None:
    """Verify leave_by_time calculates formatted clock time from countdown."""
    ref_dt = datetime(2026, 9, 14, 14, 0, 0)
    leave_120 = calculate_leave_by_time(leave_in_seconds=120, reference_time=ref_dt)
    assert leave_120 == "14:02"
    leave_neg60 = calculate_leave_by_time(leave_in_seconds=-60, reference_time=ref_dt)
    assert leave_neg60 == "13:59"


def test_calculate_journey_arrival_times() -> None:
    """Verify transit and destination arrival times are calculated correctly."""
    ref_dt = datetime(2026, 9, 14, 14, 0, 0)
    transit_time, dest_time = calculate_journey_arrival_times(
        boarding_arrival_seconds=300,
        in_vehicle_duration_seconds=1200,
        alighting_walk_seconds=600,
        reference_time=ref_dt,
    )
    assert transit_time == "14:25"
    assert dest_time == "14:35"


def test_format_next_summary() -> None:
    """Verify next_summary generates expected formatted strings."""
    ref_dt = datetime(2026, 9, 14, 14, 0, 0)
    assert format_next_summary(next_seconds_to_arrival=None) == "None scheduled"

    summary = format_next_summary(
        next_seconds_to_arrival=720,
        next_expected_time="2026-09-14T14:12:00Z",
        reference_time=ref_dt,
    )
    assert summary == "Next at 14:12 (in 12m)"

    summary_no_expected = format_next_summary(
        next_seconds_to_arrival=600,
        reference_time=ref_dt,
    )
    assert summary_no_expected == "Next at 14:10 (in 10m)"


def test_calculate_pill_badge() -> None:
    """Verify pill badge text and styling tokens across urgency stages."""
    standby = calculate_pill_badge(urgency_stage=UrgencyStage.STANDBY)
    assert standby.label == "Standby"
    assert standby.color == "#8E8E93"

    relaxed = calculate_pill_badge(
        urgency_stage=UrgencyStage.RELAXED,
        leave_in_seconds=600,
    )
    assert relaxed.label == "Leave in 10m"
    assert relaxed.color == "#4CAF50"

    prepare = calculate_pill_badge(
        urgency_stage=UrgencyStage.PREPARE,
        leave_in_seconds=240,
    )
    assert prepare.label == "Prepare (4m)"
    assert prepare.color == "#FF9800"

    leave_now = calculate_pill_badge(
        urgency_stage=UrgencyStage.LEAVE_NOW,
        leave_in_seconds=-30,
    )
    assert leave_now.label == "🚨 LEAVE NOW"
    assert leave_now.color == "#FF5252"


def test_engine_populates_presentation_attributes() -> None:
    """Verify evaluate_commute synthesises full contract attributes on states."""
    route_cfg = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        provider="tfl",
        walk_seconds=240,
        prep_seconds=120,
        grace_seconds=180,
        boarding_stop="STOP_B",
        destination_stop="STOP_D",
        in_vehicle_duration_seconds=1200,
        alighting_walk_seconds=600,
        target_arrival_time="14:40",
        corridor_stops=["STOP_A", "STOP_B"],
    )
    commute_cfg = CommuteConfig(
        commute_id="work_commute",
        routes=[route_cfg],
        target_arrival_time="14:40",
    )
    engine = CommuteEngine(config=commute_cfg)

    active_dep = DeparturePrediction(
        vehicle_id="BUS01",
        destination="Hackney Wick",
        expected_time="2026-09-14T14:10:00Z",
        seconds_to_arrival=600,
        is_realtime=True,
    )
    follower_dep = DeparturePrediction(
        vehicle_id="BUS02",
        destination="Hackney Wick",
        expected_time="2026-09-14T14:20:00Z",
        seconds_to_arrival=1200,
        is_realtime=True,
    )
    follower_dep_upstream = DeparturePrediction(
        vehicle_id="BUS02",
        destination="Hackney Wick",
        expected_time="2026-09-14T14:15:00Z",
        seconds_to_arrival=900,
        is_realtime=True,
    )
    line_status = LineStatus(
        status_label="Good Service",
        status_colour="#00A859",
        status_icon="mdi:check-circle",
    )
    telemetry = RouteTelemetry(
        route_id="bus_26",
        line_id="26",
        mode=TransitMode.BUS,
        departures=[active_dep, follower_dep],
        corridor_departures={
            "STOP_A": [follower_dep_upstream],
            "STOP_B": [active_dep, follower_dep],
        },
        stop_names={"STOP_A": "Victoria", "STOP_B": "Trafalgar Sq"},
        line_status=line_status,
    )

    ref_dt = datetime(2026, 9, 14, 14, 0, 0)
    state = engine.evaluate_commute(
        telemetries={"bus_26": telemetry},
        reference_time=ref_dt,
    )

    child = state.child_routes["bus_26"]
    assert child.route_label == "26"
    assert child.route_destination == "Hackney Wick"
    assert child.line_status == line_status
    assert child.minutes_to_arrival == 10
    assert child.leave_in_seconds == 240
    assert child.leave_in_minutes == 4
    assert child.leave_by_time == "14:04"
    assert child.estimated_transit_arrival == "14:30"
    assert child.estimated_destination_arrival == "14:40"
    assert child.timeliness == "on_time"
    assert child.will_arrive_in_time is True
    assert child.next_summary == "Next at 14:20 (in 20m)"
    assert child.pill_badge is not None
    assert child.pill_badge.label == "Prepare (4m)"
    assert len(child.corridor_stops) == 2
    assert child.corridor_stops[0] == {
        "stop_id": "STOP_A",
        "short_name": "Victoria",
        "is_target": False,
    }
    assert child.corridor_stops[1] == {
        "stop_id": "STOP_B",
        "short_name": "Trafalgar Sq",
        "is_target": True,
    }

    master = state.master_rollup
    assert master.active_option == "bus_26"
    assert master.route_label == "26"
    assert master.route_destination == "Hackney Wick"
    assert master.line_status == line_status
    assert master.minutes_to_arrival == 10
    assert master.leave_in_seconds == 240
    assert master.leave_in_minutes == 4
    assert master.leave_by_time == "14:04"
    assert master.estimated_transit_arrival == "14:30"
    assert master.estimated_destination_arrival == "14:40"
    assert master.timeliness == "on_time"
    assert master.next_summary == "Next at 14:20 (in 20m)"
    assert master.pill_badge is not None
    assert master.pill_badge.label == "Prepare (4m)"
