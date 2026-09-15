"""End-to-end acceptance test suite for forthcoming CommuteEngine (Phases 3 and 4).

Validates multi-modal ingestion, vehicle progression, doorstep reachability,
rollover events, and Master Rollup arbitration against concrete time codes
and vehicles captured in the 45-minute multi-modal time-series fixtures.
"""

from collections.abc import Callable
from typing import Any

from custom_components.commute_tracker.engine import CommuteEngine
from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteTelemetry,
    TransitMode,
)


def test_e2e_snapshot_001_initial_state_bus_preferred(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 001 evaluation produces expected lead bus and leave_now state."""

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(1)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN16OJA"
    assert bus_state.seconds_to_board == 326
    assert bus_state.seconds_to_leave == -34
    assert bus_state.urgency_stage == "leave_now"

    train_state = state.child_routes["train_southeastern"]
    assert train_state.expected_boarding_time == "14:01"
    assert train_state.seconds_to_board == 363
    assert train_state.seconds_to_leave == 3
    assert train_state.urgency_stage == "prepare"

    tube_state = state.child_routes["tube_central"]
    assert tube_state.vehicle_id == "012"
    assert "Notting Hill Gate" in tube_state.corridor_location
    assert tube_state.seconds_to_board == 573
    assert tube_state.seconds_to_leave == -147
    assert tube_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "bus_26"
    assert master.urgency_stage == "leave_now"
    assert master.seconds_to_board == 326
    assert master.seconds_to_leave == -34
    assert master.route_label == "26"


def test_e2e_snapshot_006_train_arbitration_takeover(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 006 promotes Southeastern train when it reaches leave_now."""

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(6)
    state = engine.process_snapshot(snapshot=snapshot)

    train_state = state.child_routes["train_southeastern"]
    assert train_state.expected_boarding_time == "14:04"
    assert train_state.seconds_to_board == 357
    assert train_state.seconds_to_leave == -3
    assert train_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "train_southeastern"
    assert master.urgency_stage == "leave_now"
    assert master.route_label == "Southeastern"
    assert master.seconds_to_board == 357


def test_e2e_snapshot_009_bus_doorstep_and_queue(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 009 tracks lead bus final arrival and next vehicle in queue."""

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(9)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN16OJA"
    assert bus_state.seconds_to_board == 75
    assert bus_state.urgency_stage == "leave_now"
    assert bus_state.next_vehicle_id == "SN66WRP"
    assert bus_state.seconds_to_next_board == 414


def test_e2e_snapshot_011_bus_rollover_to_next_vehicle(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 011 rolls over to follow bus and reclaims master arbitration."""

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(11)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN66WRP"
    assert bus_state.seconds_to_board == 354
    assert bus_state.seconds_to_leave == -6
    assert bus_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "bus_26"
    assert master.urgency_stage == "leave_now"
    assert master.seconds_to_board == 354


def test_e2e_snapshot_021_tube_arbitration_takeover(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 021 promotes Central Line tube when bus and train are relaxed."""

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(21)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN66WRO"
    assert bus_state.seconds_to_board == 1234
    assert bus_state.urgency_stage == "relaxed"

    train_state = state.child_routes["train_southeastern"]
    assert train_state.expected_boarding_time == "14:20"
    assert train_state.seconds_to_board == 756
    assert train_state.urgency_stage == "prepare"

    tube_state = state.child_routes["tube_central"]
    assert tube_state.vehicle_id == "022"
    assert tube_state.seconds_to_board == 592
    assert tube_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "tube_central"
    assert master.urgency_stage == "leave_now"
    assert master.route_label == "Central"


def test_e2e_snapshot_046_train_reclaims_arbitration(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 046 promotes Southeastern train on scheduled 14:29 departure."""

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(46)
    state = engine.process_snapshot(snapshot=snapshot)

    train_state = state.child_routes["train_southeastern"]
    assert train_state.expected_boarding_time == "14:29"
    assert train_state.seconds_to_board == 353
    assert train_state.seconds_to_leave == -7
    assert train_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "train_southeastern"
    assert master.urgency_stage == "leave_now"
    assert master.route_label == "Southeastern"


def test_e2e_continuous_playback_and_rollover_sequence(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify feeding snapshots 001 to 015 sequentially executes clean handovers."""

    engine = CommuteEngine(config=canonical_commute_config)
    observed_vehicles: list[str] = []

    for index in range(1, 16):
        snapshot = snapshot_loader(index)
        state = engine.process_snapshot(snapshot=snapshot)

        bus_vehicle = state.child_routes["bus_26"].vehicle_id
        assert bus_vehicle is not None
        if not observed_vehicles or observed_vehicles[-1] != bus_vehicle:
            observed_vehicles.append(bus_vehicle)

        master = state.master_rollup
        assert master.active_option in {"bus_26", "train_southeastern", "tube_central"}
        assert master.urgency_stage in {"leave_now", "prepare", "relaxed"}

    assert observed_vehicles == ["SN16OJA", "SN66WRP"]


def test_engine_evaluate_commute_direct_evaluation(
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify CommuteEngine processes pre-fetched RouteTelemetry directly."""
    engine = CommuteEngine(config=canonical_commute_config)

    bus_dep = DeparturePrediction(
        vehicle_id="BUS_DIRECT",
        destination="Hackney",
        expected_time="2026-09-14T14:00:00Z",
        seconds_to_arrival=300,
    )
    status = LineStatus(
        status_label="Good Service",
        status_colour="#00A859",
        status_icon="mdi:check-circle",
    )
    telemetries = {
        "bus_26": RouteTelemetry(
            route_id="bus_26",
            line_id="26",
            mode=TransitMode.BUS,
            departures=[bus_dep],
            active_vehicle_id="BUS_DIRECT",
            line_status=status,
        ),
    }

    state = engine.evaluate_commute(telemetries=telemetries)
    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "BUS_DIRECT"
    assert bus_state.seconds_to_board == 300
    assert bus_state.seconds_to_leave == -60
    assert bus_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "bus_26"
    assert master.urgency_stage == "leave_now"


def test_engine_evaluate_commute_with_helper_overrides(
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify evaluate_commute respects dynamic helper overrides."""
    engine = CommuteEngine(config=canonical_commute_config)

    bus_dep = DeparturePrediction(
        vehicle_id="BUS_DIRECT",
        destination="Hackney",
        expected_time="2026-09-14T14:00:00Z",
        seconds_to_arrival=500,
    )
    telemetries = {
        "bus_26": RouteTelemetry(
            route_id="bus_26",
            line_id="26",
            mode=TransitMode.BUS,
            departures=[bus_dep],
            line_status=LineStatus(status_label="Good Service"),
        ),
    }

    state = engine.evaluate_commute(telemetries=telemetries)
    assert state.child_routes["bus_26"].seconds_to_leave == 140
    assert state.child_routes["bus_26"].urgency_stage == "prepare"

    overrides = {"boarding_walk_seconds": 60}
    state2 = engine.evaluate_commute(
        telemetries=telemetries, helper_overrides=overrides
    )
    assert state2.child_routes["bus_26"].seconds_to_leave == 320


def test_engine_template_provider_dispatch() -> None:
    """Verify CommuteEngine dispatches route evaluation via TransitProviderRegistry."""
    config = {
        "commute_id": "template_commute",
        "routes": [
            {
                "id": "route_template",
                "mode": "bus",
                "line": "T1",
                "provider": "template",
                "boarding_walk_seconds": 120,
                "prep_seconds": 60,
                "grace_seconds": 60,
            }
        ],
    }
    engine = CommuteEngine(config=config)
    state = engine.process_snapshot(snapshot={})

    child = state.child_routes["route_template"]
    assert child.vehicle_id == "TEMPLATE_01"
    assert child.seconds_to_board == 300
    assert child.seconds_to_leave == 120
    assert child.urgency_stage == "prepare"

    master = state.master_rollup
    assert master.active_option == "route_template"
    assert master.urgency_stage == "prepare"
