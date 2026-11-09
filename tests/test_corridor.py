"""Unit tests for corridor trajectory evaluation, filtering, and progression."""

from custom_components.commute_tracker.corridor import (
    calculate_corridor_progression,
    discover_upstream_corridor,
    filter_approaching_departures,
    find_target_branch,
    select_active_departures,
    slice_upstream_corridor,
)
from custom_components.commute_tracker.models import (
    CorridorStop,
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


def test_slice_upstream_corridor_empty_payload() -> None:
    """Verify empty sequence payload yields empty corridor list."""
    assert discover_upstream_corridor is slice_upstream_corridor
    assert slice_upstream_corridor([], "490000001A") == []


def test_slice_upstream_corridor_match_by_id() -> None:
    """Verify sequence is extracted up to boarding stop matched by ID."""
    sequence = [
        CorridorStop(id="STOP_1", name="Victoria"),
        CorridorStop(id="STOP_2", name="Hyde Park Corner"),
        CorridorStop(id="STOP_3", name="Marble Arch"),
        CorridorStop(id="STOP_4", name="Oxford Circus"),
        CorridorStop(id="STOP_5", name="Tottenham Court Road"),
    ]

    corridor = slice_upstream_corridor(
        sequences=sequence,
        boarding_stop="STOP_3",
    )

    assert len(corridor) == 3
    assert corridor[0] == CorridorStop(id="STOP_1", name="Victoria", is_target=False)
    assert corridor[1] == CorridorStop(
        id="STOP_2", name="Hyde Park Corner", is_target=False
    )
    assert corridor[2] == CorridorStop(id="STOP_3", name="Marble Arch", is_target=True)
    # Verify backwards compatibility subscript access
    assert corridor[0]["id"] == "STOP_1"
    assert corridor[2]["is_target"] is True


def test_slice_upstream_corridor_match_by_name() -> None:
    """Verify sequence matches boarding stop by station name case-insensitively."""
    sequence = [
        CorridorStop(id="STOP_A", name="St Julian's"),
        CorridorStop(id="STOP_B", name="WN Station"),
        CorridorStop(id="STOP_C", name="Robson Rd"),
        CorridorStop(id="STOP_D", name="York Hill"),
        CorridorStop(id="STOP_E", name="Royal Circus"),
    ]

    corridor = slice_upstream_corridor(
        sequences=sequence,
        boarding_stop="royal circus",
    )

    assert len(corridor) == 5
    assert corridor[-1].id == "STOP_E"
    assert corridor[-1].is_target is True
    assert corridor[0].id == "STOP_A"
    assert corridor[0].is_target is False


def test_slice_upstream_corridor_with_time_window() -> None:
    """Verify stops are trimmed to the requested time window ending at boarding stop."""
    sequence = [CorridorStop(id=f"STOP_{i}", name=f"Station {i}") for i in range(1, 16)]

    corridor = slice_upstream_corridor(
        sequences=sequence,
        boarding_stop="STOP_12",
        target_time_window_seconds=480,
        seconds_per_stop=120,
    )

    assert len(corridor) == 4
    assert [s.id for s in corridor] == [
        "STOP_9",
        "STOP_10",
        "STOP_11",
        "STOP_12",
    ]
    assert corridor[-1].is_target is True
    assert not any(s.is_target for s in corridor[:-1])


def test_slice_upstream_corridor_boarding_stop_is_first() -> None:
    """Verify single stop returned when boarding stop is terminus/first stop."""
    sequence = [
        CorridorStop(id="STOP_FIRST", name="First"),
        CorridorStop(id="STOP_SECOND", name="Second"),
    ]

    corridor = slice_upstream_corridor(
        sequences=sequence,
        boarding_stop="STOP_FIRST",
    )

    assert len(corridor) == 1
    assert corridor[0] == CorridorStop(id="STOP_FIRST", name="First", is_target=True)


def test_slice_upstream_corridor_stop_not_found() -> None:
    """Verify empty list when boarding stop is not present in line sequences."""
    sequence = [
        CorridorStop(id="STOP_1", name="Station 1"),
        CorridorStop(id="STOP_2", name="Station 2"),
    ]

    assert (
        slice_upstream_corridor(
            sequences=sequence,
            boarding_stop="NONEXISTENT_STOP",
        )
        == []
    )


def test_slice_upstream_corridor_branch_selection() -> None:
    """Verify correct branch is picked when line has multiple branches."""
    branches = [
        [
            CorridorStop(id="BRANCH_1_A", name="Branch 1 Alpha"),
            CorridorStop(id="BRANCH_1_B", name="Branch 1 Beta"),
        ],
        [
            CorridorStop(id="BRANCH_2_A", name="Branch 2 Alpha"),
            CorridorStop(id="BRANCH_2_B", name="Branch 2 Beta"),
            CorridorStop(id="BRANCH_2_C", name="Branch 2 Target"),
        ],
    ]

    corridor = slice_upstream_corridor(
        sequences=branches,
        boarding_stop="BRANCH_2_C",
    )

    assert len(corridor) == 3
    assert [s.id for s in corridor] == [
        "BRANCH_2_A",
        "BRANCH_2_B",
        "BRANCH_2_C",
    ]
    assert corridor[-1].is_target is True


def test_slice_upstream_corridor_with_scheduled_lead_times() -> None:
    """Verify corridor trimming uses scheduled lead times when annotated."""
    sequence = [
        CorridorStop(id="STOP_1", name="Far Origin", scheduled_lead_seconds=720),
        CorridorStop(id="STOP_2", name="Way Upstream", scheduled_lead_seconds=540),
        CorridorStop(id="STOP_3", name="Mid Corridor", scheduled_lead_seconds=360),
        CorridorStop(id="STOP_4", name="Near Upstream", scheduled_lead_seconds=180),
        CorridorStop(id="STOP_5", name="Boarding Target", scheduled_lead_seconds=0),
    ]

    corridor = slice_upstream_corridor(
        sequences=sequence,
        boarding_stop="STOP_5",
        target_time_window_seconds=400,
        seconds_per_stop=120,
    )

    assert len(corridor) == 3
    assert [s.id for s in corridor] == ["STOP_3", "STOP_4", "STOP_5"]
    assert corridor[0].scheduled_lead_seconds == 360
    assert corridor[1].scheduled_lead_seconds == 180
    assert corridor[2].scheduled_lead_seconds == 0
    assert corridor[2].is_target is True


def test_find_target_branch_matching() -> None:
    """Verify find_target_branch locates branch and index by id or substring name."""
    b1 = [CorridorStop(id="S1", name="Alpha"), CorridorStop(id="S2", name="Beta")]
    b2 = [
        CorridorStop(id="S3", name="Gamma"),
        CorridorStop(id="S4", name="Delta Station"),
    ]

    assert find_target_branch(sequences=[], target_query="S1") is None
    assert find_target_branch(sequences=[b1, b2], target_query="") is None

    # Match by ID
    res = find_target_branch(sequences=[b1, b2], target_query="S2")
    assert res is not None
    assert res[0] == b1
    assert res[1] == 1

    # Match by friendly name substring case-insensitively
    res = find_target_branch(sequences=[b1, b2], target_query="delta")
    assert res is not None
    assert res[0] == b2
    assert res[1] == 1

    # Single flat sequence
    res = find_target_branch(sequences=b1, target_query="alpha")
    assert res is not None
    assert res[0] == b1
    assert res[1] == 0

    # Non-matching query
    assert find_target_branch(sequences=[b1, b2], target_query="Omega") is None


def test_calculate_corridor_progression_train_upstream_interpolation() -> None:
    """Verify train departures without vehicle_id interpolate along corridor."""
    corridor = [
        "STOP_0",
        "STOP_1",
        "STOP_2",
        "STOP_3",
        "STOP_4",
        "STOP_5",
        "STOP_6",
    ]
    names = {
        "STOP_0": "Victoria",
        "STOP_1": "Brixton",
        "STOP_2": "Herne Hill",
        "STOP_3": "West Dulwich",
        "STOP_4": "Sydenham Hill",
        "STOP_5": "Penge East",
        "STOP_6": "Gipsy Hill",
    }

    # Far future scheduled departure (>= 1500s across 6 segments * 250s)
    # Even if location has the static boarding station name from Journey Planner
    dep_scheduled = DeparturePrediction(
        vehicle_id="",
        destination="London Bridge",
        expected_time=None,
        seconds_to_arrival=1620,
        location="Gipsy Hill Rail Station",
        is_realtime=False,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_scheduled,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "Scheduled from Victoria"
    assert prog == 0.0

    # Halfway along the 6-segment (1500s) corridor -> 750s remaining -> index 3.0
    dep_mid_stop = DeparturePrediction(
        vehicle_id="",
        destination="London Bridge",
        expected_time=None,
        seconds_to_arrival=750,
        location="",
        is_realtime=False,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_mid_stop,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "At West Dulwich"
    assert prog == 3.0

    # Between stop 3 (750s) and stop 4 (500s) -> 625s remaining -> index 3.5
    dep_between = DeparturePrediction(
        vehicle_id="",
        destination="London Bridge",
        expected_time=None,
        seconds_to_arrival=625,
        location="",
        is_realtime=False,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_between,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "Between West Dulwich and Sydenham Hill"
    assert prog == 3.5

    # Arriving at boarding stop (<= 45s) -> index 6.0
    dep_arriving = DeparturePrediction(
        vehicle_id="",
        destination="London Bridge",
        expected_time=None,
        seconds_to_arrival=30,
        location="",
        is_realtime=False,
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_arriving,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "At Gipsy Hill"
    assert prog == 6.0


def test_calculate_corridor_progression_bus_lingering_origin_and_turnaround() -> None:
    """Verify bus progression ignores lingering origin and turnaround predictions."""
    corridor = ["STOP_0", "STOP_1", "STOP_2", "STOP_3", "STOP_4"]
    names = {
        "STOP_0": "St Julian's",
        "STOP_1": "WN Station",
        "STOP_2": "Robson Rd",
        "STOP_3": "York Hill",
        "STOP_4": "Royal Circus",
    }

    # Case 1: Only origin stop has a prediction > 45s -> "Scheduled at <origin>", 0.0
    dep_at_origin = DeparturePrediction(
        vehicle_id="LK66BXD",
        destination="Elephant & Castle",
        expected_time=None,
        seconds_to_arrival=700,
    )
    corridor_deps_origin = {
        "STOP_0": [
            DeparturePrediction(
                vehicle_id="LK66BXD",
                destination="Elephant & Castle",
                expected_time=None,
                seconds_to_arrival=240,
            )
        ]
    }
    loc, prog = calculate_corridor_progression(
        departure=dep_at_origin,
        corridor_stops=corridor,
        corridor_departures=corridor_deps_origin,
        stop_names=names,
    )
    assert loc == "Scheduled at St Julian's"
    assert prog == 0.0

    # Case 2: Lingering origin prediction (<= 45s) when bus is downstream
    dep_downstream = DeparturePrediction(
        vehicle_id="LK66BXD",
        destination="Elephant & Castle",
        expected_time=None,
        seconds_to_arrival=200,
    )
    corridor_deps_lingering = {
        "STOP_0": [
            DeparturePrediction(
                vehicle_id="LK66BXD",
                destination="Elephant & Castle",
                expected_time=None,
                seconds_to_arrival=15,
            )
        ],
        "STOP_3": [
            DeparturePrediction(
                vehicle_id="LK66BXD",
                destination="Elephant & Castle",
                expected_time=None,
                seconds_to_arrival=90,
            )
        ],
    }
    loc, prog = calculate_corridor_progression(
        departure=dep_downstream,
        corridor_stops=corridor,
        corridor_departures=corridor_deps_lingering,
        stop_names=names,
    )
    assert loc == "Between Robson Rd and York Hill"
    assert prog == 2.5

    # Case 3: Turnaround/subsequent trip prediction at STOP_0 (> target arrival)
    corridor_deps_turnaround = {
        "STOP_0": [
            DeparturePrediction(
                vehicle_id="LK66BXD",
                destination="Elephant & Castle",
                expected_time=None,
                seconds_to_arrival=1200,
            )
        ],
        "STOP_2": [
            DeparturePrediction(
                vehicle_id="LK66BXD",
                destination="Elephant & Castle",
                expected_time=None,
                seconds_to_arrival=25,
            )
        ],
        "STOP_3": [
            DeparturePrediction(
                vehicle_id="LK66BXD",
                destination="Elephant & Castle",
                expected_time=None,
                seconds_to_arrival=90,
            )
        ],
    }
    loc, prog = calculate_corridor_progression(
        departure=dep_downstream,
        corridor_stops=corridor,
        corridor_departures=corridor_deps_turnaround,
        stop_names=names,
    )
    assert loc == "At Robson Rd"
    assert prog == 2.0


def test_calculate_corridor_progression_empty_stop_names() -> None:
    """Verify empty string stop names fall back to stop IDs without false matches."""
    corridor = ["STOP_1", "STOP_2", "STOP_3"]
    names = {"STOP_1": "", "STOP_2": "   ", "STOP_3": "Target"}

    # Location string should not falsely match empty string at index 0
    dep_with_loc = DeparturePrediction(
        vehicle_id="V1",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=20,
        location="At Target",
    )
    loc, prog = calculate_corridor_progression(
        departure=dep_with_loc,
        corridor_stops=corridor,
        corridor_departures={},
        stop_names=names,
    )
    assert loc == "At Target"
    assert prog == 2.0

    # Vehicle trajectory between STOP_1 and STOP_2 uses stop IDs when names are empty
    dep_between = DeparturePrediction(
        vehicle_id="V1",
        destination="Terminus",
        expected_time=None,
        seconds_to_arrival=300,
    )
    corridor_deps = {
        "STOP_2": [
            DeparturePrediction(
                vehicle_id="V1",
                destination="Terminus",
                expected_time=None,
                seconds_to_arrival=100,
            )
        ]
    }
    loc2, prog2 = calculate_corridor_progression(
        departure=dep_between,
        corridor_stops=corridor,
        corridor_departures=corridor_deps,
        stop_names=names,
    )
    assert loc2 == "Between STOP_1 and STOP_2"
    assert prog2 == 0.5


def test_slice_upstream_corridor_with_alighting_stop_direction() -> None:
    """Verify branch selection prefers direction where alighting_stop is downstream."""
    inbound = [
        CorridorStop(id="STOP_D", name="Oxford Circus"),
        CorridorStop(id="STOP_C", name="Marble Arch"),
        CorridorStop(id="STOP_B", name="Hyde Park Corner"),
        CorridorStop(id="STOP_A", name="Victoria"),
    ]
    outbound = [
        CorridorStop(id="STOP_A", name="Victoria"),
        CorridorStop(id="STOP_B", name="Hyde Park Corner"),
        CorridorStop(id="STOP_C", name="Marble Arch"),
        CorridorStop(id="STOP_D", name="Oxford Circus"),
    ]
    # Put inbound first to ensure outbound is chosen by direction, not list order
    branches = [inbound, outbound]

    corridor_outbound = slice_upstream_corridor(
        sequences=branches,
        boarding_stop="STOP_C",
        alighting_stop="Oxford Circus",
    )
    assert [s.id for s in corridor_outbound] == ["STOP_A", "STOP_B", "STOP_C"]

    corridor_inbound = slice_upstream_corridor(
        sequences=branches,
        boarding_stop="STOP_C",
        alighting_stop="Victoria",
    )
    assert [s.id for s in corridor_inbound] == ["STOP_D", "STOP_C"]

    # When boarding at terminus STOP_D without alighting_stop, prefer branch where
    # STOP_D has upstream stops (outbound index 3) over inbound index 0
    corridor_terminus = slice_upstream_corridor(
        sequences=branches,
        boarding_stop="STOP_D",
    )
    assert [s.id for s in corridor_terminus] == [
        "STOP_A",
        "STOP_B",
        "STOP_C",
        "STOP_D",
    ]
