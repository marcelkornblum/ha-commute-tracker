"""End-to-end acceptance test suite for forthcoming CommuteEngine (Phases 3 and 4).

Validates multi-modal ingestion, vehicle progression, doorstep reachability,
rollover events, and Master Rollup arbitration against concrete time codes
and vehicles captured in the 45-minute multi-modal time-series fixtures.
"""

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.xfail(
    reason="Forthcoming CommuteEngine (Phase 3/4) not yet implemented",
    raises=(ImportError, ModuleNotFoundError, NotImplementedError, AttributeError),
    strict=False,
)


def test_e2e_snapshot_001_initial_state_bus_preferred(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 001 evaluation produces expected lead bus and leave_now state."""
    from custom_components.commute_tracker.engine import CommuteEngine

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(1)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN16OJA"
    assert bus_state.seconds_to_arrival == 326
    assert bus_state.leave_in_seconds == -34
    assert bus_state.urgency_stage == "leave_now"

    train_state = state.child_routes["train_southeastern"]
    assert train_state.scheduled_departure == "2026-09-14T14:01:00"
    assert train_state.seconds_to_arrival == 363
    assert train_state.leave_in_seconds == 3
    assert train_state.urgency_stage == "prepare"

    tube_state = state.child_routes["tube_central"]
    assert tube_state.vehicle_id == "012"
    assert "Notting Hill Gate" in tube_state.corridor_location
    assert tube_state.seconds_to_arrival == 573
    assert tube_state.leave_in_seconds == -147
    assert tube_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "bus_26"
    assert master.urgency_stage == "leave_now"
    assert master.seconds_to_arrival == 326
    assert master.leave_in_seconds == -34
    assert master.route_label == "26"


def test_e2e_snapshot_006_train_arbitration_takeover(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 006 promotes Southeastern train when it reaches leave_now."""
    from custom_components.commute_tracker.engine import CommuteEngine

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(6)
    state = engine.process_snapshot(snapshot=snapshot)

    train_state = state.child_routes["train_southeastern"]
    assert train_state.scheduled_departure == "2026-09-14T14:04:00"
    assert train_state.seconds_to_arrival == 357
    assert train_state.leave_in_seconds == -3
    assert train_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "train_southeastern"
    assert master.urgency_stage == "leave_now"
    assert master.route_label == "Southeastern"
    assert master.seconds_to_arrival == 357


def test_e2e_snapshot_009_bus_doorstep_and_queue(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 009 tracks lead bus final arrival and next vehicle in queue."""
    from custom_components.commute_tracker.engine import CommuteEngine

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(9)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN16OJA"
    assert bus_state.seconds_to_arrival == 75
    assert bus_state.urgency_stage == "leave_now"
    assert bus_state.next_vehicle_id == "SN66WRP"
    assert bus_state.next_seconds_to_arrival == 414


def test_e2e_snapshot_011_bus_rollover_to_next_vehicle(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 011 rolls over to follow bus and reclaims master arbitration."""
    from custom_components.commute_tracker.engine import CommuteEngine

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(11)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN66WRP"
    assert bus_state.seconds_to_arrival == 354
    assert bus_state.leave_in_seconds == -6
    assert bus_state.urgency_stage == "leave_now"

    master = state.master_rollup
    assert master.active_option == "bus_26"
    assert master.urgency_stage == "leave_now"
    assert master.seconds_to_arrival == 354


def test_e2e_snapshot_021_tube_arbitration_takeover(
    snapshot_loader: Callable[[int], dict[str, Any]],
    canonical_commute_config: dict[str, Any],
) -> None:
    """Verify snapshot 021 promotes Central Line tube when bus and train are relaxed."""
    from custom_components.commute_tracker.engine import CommuteEngine

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(21)
    state = engine.process_snapshot(snapshot=snapshot)

    bus_state = state.child_routes["bus_26"]
    assert bus_state.vehicle_id == "SN66WRO"
    assert bus_state.seconds_to_arrival == 1234
    assert bus_state.urgency_stage == "relaxed"

    train_state = state.child_routes["train_southeastern"]
    assert train_state.scheduled_departure == "2026-09-14T14:20:00"
    assert train_state.seconds_to_arrival == 756
    assert train_state.urgency_stage == "prepare"

    tube_state = state.child_routes["tube_central"]
    assert tube_state.vehicle_id == "022"
    assert tube_state.seconds_to_arrival == 592
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
    from custom_components.commute_tracker.engine import CommuteEngine

    engine = CommuteEngine(config=canonical_commute_config)
    snapshot = snapshot_loader(46)
    state = engine.process_snapshot(snapshot=snapshot)

    train_state = state.child_routes["train_southeastern"]
    assert train_state.scheduled_departure == "2026-09-14T14:29:00"
    assert train_state.seconds_to_arrival == 353
    assert train_state.leave_in_seconds == -7
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
    from custom_components.commute_tracker.engine import CommuteEngine

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
