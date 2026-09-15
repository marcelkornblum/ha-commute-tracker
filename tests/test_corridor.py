"""Unit tests for corridor trajectory evaluation, filtering, and progression."""

from custom_components.commute_tracker.corridor import (
    calculate_corridor_progression,
    filter_approaching_departures,
    select_active_departures,
)
from custom_components.commute_tracker.models import (
    DeparturePrediction,
)


def test_filter_approaching_departures_empty_corridor() -> None:
    """Verify departure filtering passes departures when no corridor configured."""
    dep = DeparturePrediction(
        vehicle_id="BUS01",
        destination="Hackney",
        expected_time="2026-09-15T12:00:00Z",
        seconds_to_arrival=300,
    )
    assert filter_approaching_departures(
        departures=[dep],
        corridor_stops=[],
        corridor_departures={},
    ) == [dep]

    assert filter_approaching_departures(
        departures=[dep],
        corridor_stops=["STOP_A"],
        corridor_departures={},
        boarding_stop="STOP_B",
    ) == [dep]


def test_filter_approaching_departures_direction_evaluation() -> None:
    """Verify opposing direction vehicles are filtered and forward vehicles retained."""
    corridor = ["STOP_A", "STOP_B", "STOP_C"]
    target = "STOP_C"

    dep_approaching = DeparturePrediction(
        vehicle_id="VEH_APPROACHING",
        destination="Target",
        expected_time="2026-09-15T12:10:00Z",
        seconds_to_arrival=400,
    )
    dep_opposing = DeparturePrediction(
        vehicle_id="VEH_OPPOSING",
        destination="Away",
        expected_time="2026-09-15T12:02:00Z",
        seconds_to_arrival=120,
    )
    dep_far_away_unseen = DeparturePrediction(
        vehicle_id="VEH_FAR",
        destination="Target",
        expected_time="2026-09-15T12:20:00Z",
        seconds_to_arrival=900,
    )
    dep_near_unseen = DeparturePrediction(
        vehicle_id="VEH_NEAR",
        destination="Target",
        expected_time="2026-09-15T12:08:00Z",
        seconds_to_arrival=480,
    )
    dep_no_vid = DeparturePrediction(
        vehicle_id=None,
        destination="Target",
        expected_time="2026-09-15T12:05:00Z",
        seconds_to_arrival=300,
    )

    corridor_deps = {
        "STOP_A": [
            DeparturePrediction(
                vehicle_id="VEH_APPROACHING",
                destination="Target",
                expected_time=None,
                seconds_to_arrival=100,
            ),
            DeparturePrediction(
                vehicle_id="VEH_OPPOSING",
                destination="Away",
                expected_time=None,
                seconds_to_arrival=600,
            ),
        ],
        "STOP_B": [
            DeparturePrediction(
                vehicle_id="VEH_APPROACHING",
                destination="Target",
                expected_time=None,
                seconds_to_arrival=250,
            ),
        ],
    }

    candidates = [
        dep_approaching,
        dep_opposing,
        dep_far_away_unseen,
        dep_near_unseen,
        dep_no_vid,
    ]

    filtered = filter_approaching_departures(
        departures=candidates,
        corridor_stops=corridor,
        corridor_departures=corridor_deps,
        boarding_stop=target,
    )

    assert dep_approaching in filtered
    assert dep_opposing not in filtered
    assert dep_far_away_unseen not in filtered
    assert dep_near_unseen in filtered
    assert dep_no_vid in filtered


def test_calculate_corridor_progression_explicit_location() -> None:
    """Verify calculate_corridor_progression with explicit location text."""
    corridor = ["STOP_A", "STOP_B", "STOP_C"]
    names = {"STOP_A": "Bank", "STOP_B": "Holborn", "STOP_C": "Tottenham Court Road"}

    dep_at = DeparturePrediction(
        vehicle_id="001",
        destination="Ealing",
        expected_time=None,
        seconds_to_arrival=180,
        location="At Holborn",
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_at,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "At Holborn"
    assert prog == 1.0

    dep_between = DeparturePrediction(
        vehicle_id="002",
        destination="Ealing",
        expected_time=None,
        seconds_to_arrival=120,
        location="Between Holborn and Tottenham Court Road",
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_between,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert "Between" in loc
    assert prog == 1.5


def test_calculate_corridor_progression_vehicle_trajectory() -> None:
    """Verify calculate_corridor_progression from upstream corridor arrivals."""
    corridor = ["STOP_1", "STOP_2", "STOP_3"]
    names = {
        "STOP_1": "Station One",
        "STOP_2": "Station Two",
        "STOP_3": "Station Three",
    }

    dep_dwelling = DeparturePrediction(
        vehicle_id="BUS_DWELL",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=500,
    )
    corridor_deps_dwell = {
        "STOP_1": [
            DeparturePrediction(
                vehicle_id="BUS_DWELL",
                destination="Terminus",
                expected_time=None,
                seconds_to_arrival=30,
            )
        ]
    }
    loc, prog = calculate_corridor_progression(
        departure=dep_dwelling,
        corridor_stops=corridor,
        corridor_departures=corridor_deps_dwell,
        stop_names=names,
    )
    assert loc == "At Station One"
    assert prog == 0.0

    dep_transit = DeparturePrediction(
        vehicle_id="BUS_TRANSIT",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=350,
    )
    corridor_deps_transit = {
        "STOP_2": [
            DeparturePrediction(
                vehicle_id="BUS_TRANSIT",
                destination="Terminus",
                expected_time=None,
                seconds_to_arrival=100,
            )
        ]
    }
    loc, prog = calculate_corridor_progression(
        departure=dep_transit,
        corridor_stops=corridor,
        corridor_departures=corridor_deps_transit,
        stop_names=names,
    )
    assert loc == "Between Station One and Station Two"
    assert prog == 0.5


def test_calculate_corridor_progression_target_arrival() -> None:
    """Verify corridor progression when approaching or arriving at target stop."""
    corridor = ["STOP_1", "STOP_2"]
    names = {"STOP_1": "Station One", "STOP_2": "Target Station"}

    dep_at_target = DeparturePrediction(
        vehicle_id="BUS_TARGET",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=20,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_at_target,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "At Target Station"
    assert prog == 1.0

    dep_approaching_target = DeparturePrediction(
        vehicle_id="BUS_TARGET",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=120,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_approaching_target,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "Between Station One and Target Station"
    assert prog == 0.5


def test_calculate_corridor_progression_no_corridor_fallback() -> None:
    """Verify fallback text when route defines no corridor stops."""
    dep = DeparturePrediction(
        vehicle_id="BUS_NO_CORRIDOR",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=150,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep,
        corridor_stops=[],
        corridor_departures={},
        stop_names={"STOP_BOARD": "Main Street"},
        boarding_stop="STOP_BOARD",
    )
    assert loc == "Approaching Main Street"
    assert prog == 0.0

    dep_dwelling = DeparturePrediction(
        vehicle_id="BUS_NO_CORRIDOR",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=30,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_dwelling,
        corridor_stops=[],
        corridor_departures={},
        stop_names={"STOP_BOARD": "Main Street"},
        boarding_stop="STOP_BOARD",
    )
    assert loc == "At Main Street"
    assert prog == 0.0


def test_select_active_departures_skips_unreachable() -> None:
    """Verify departure selection skips unreachable departures and assigns follower."""
    dep_unreachable = DeparturePrediction(
        vehicle_id="DEP_01",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=30,
    )
    dep_reachable = DeparturePrediction(
        vehicle_id="DEP_02",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=250,
    )
    dep_subsequent = DeparturePrediction(
        vehicle_id="DEP_03",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=600,
    )

    active, follower = select_active_departures(
        departures=[dep_unreachable, dep_reachable, dep_subsequent],
        boarding_walk_seconds=240,
        grace_seconds=180,
    )

    assert active == dep_reachable
    assert follower == dep_subsequent


def test_select_active_departures_empty_and_unreachable() -> None:
    """Verify fallback behaviour for empty or fully unreachable departures."""
    dep_unreachable = DeparturePrediction(
        vehicle_id="DEP_01",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=30,
    )

    active, follower = select_active_departures(
        departures=[],
        boarding_walk_seconds=240,
        grace_seconds=180,
    )
    assert active is None
    assert follower is None

    active, follower = select_active_departures(
        departures=[dep_unreachable],
        boarding_walk_seconds=240,
        grace_seconds=180,
    )
    assert active is None
    assert follower is None

    dep_only_one = DeparturePrediction(
        vehicle_id="DEP_02",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=300,
    )
    active, follower = select_active_departures(
        departures=[dep_only_one],
        boarding_walk_seconds=240,
        grace_seconds=180,
    )
    assert active == dep_only_one
    assert follower is None
