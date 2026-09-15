"""Unit tests for CommuteEngine Master Rollup arbitration strategies."""

from datetime import datetime, timezone

from custom_components.commute_tracker.engine import CommuteEngine
from custom_components.commute_tracker.models import (
    CommuteConfig,
    DeparturePrediction,
    LineStatus,
    RollupStrategy,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import (
    TransitProviderRegistry,
)


def _build_route_and_telemetry(
    route_id: str,
    line: str,
    mode: TransitMode,
    seconds_to_arrival: int,
    boarding_walk_seconds: int = 240,
    prep_seconds: int = 120,
    transit_duration_seconds: int = 1200,
    alighting_walk_seconds: int = 300,
) -> tuple[RouteConfig, RouteTelemetry]:
    """Create a RouteConfig and corresponding RouteTelemetry for arbitration."""
    route_cfg = RouteConfig(
        route_id=route_id,
        mode=mode,
        line=line,
        provider="mock",
        boarding_walk_seconds=boarding_walk_seconds,
        prep_seconds=prep_seconds,
        transit_duration_seconds=transit_duration_seconds,
        alighting_walk_seconds=alighting_walk_seconds,
    )
    telemetry = RouteTelemetry(
        route_id=route_id,
        line_id=line,
        mode=mode,
        departures=[
            DeparturePrediction(
                vehicle_id=f"VEH_{route_id}",
                destination="Destination",
                expected_time="2026-09-15T08:30:00Z",
                seconds_to_arrival=seconds_to_arrival,
            )
        ],
        line_status=LineStatus(
            status_label="Good Service",
            status_color="#00A859",
            status_icon="mdi:check-circle",
        ),
    )
    return route_cfg, telemetry


def test_arbitration_soonest_strategy() -> None:
    """Verify SOONEST strategy selects route with smallest positive leave window."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 900)
    r3, t3 = _build_route_and_telemetry(
        "route_3", "Thameslink", TransitMode.TRAIN, 1500
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2, r3],
        rollup_strategy=RollupStrategy.SOONEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2, r3.route_id: t3}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_1"
    assert commute_state.master_rollup.seconds_to_leave == 240
    assert commute_state.master_rollup.strategy == RollupStrategy.SOONEST


def test_arbitration_latest_strategy() -> None:
    """Verify LATEST strategy selects route with largest positive leave window."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 900)
    r3, t3 = _build_route_and_telemetry(
        "route_3", "Thameslink", TransitMode.TRAIN, 1500
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2, r3],
        rollup_strategy=RollupStrategy.LATEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2, r3.route_id: t3}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_3"
    assert commute_state.master_rollup.seconds_to_leave == 1140
    assert commute_state.master_rollup.strategy == RollupStrategy.LATEST


def test_arbitration_late_with_buffer_penultimate_selection() -> None:
    """Verify LATE_WITH_BUFFER selects penultimate candidate when within buffer."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 1200)
    r3, t3 = _build_route_and_telemetry(
        "route_3", "Thameslink", TransitMode.TRAIN, 1400
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2, r3],
        rollup_strategy=RollupStrategy.LATE_WITH_BUFFER,
        route_late_buffer_seconds=300,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2, r3.route_id: t3}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_2"
    assert commute_state.master_rollup.seconds_to_leave == 840
    assert commute_state.master_rollup.strategy == RollupStrategy.LATE_WITH_BUFFER


def test_arbitration_late_with_buffer_outside_buffer_selects_latest() -> None:
    """Verify LATE_WITH_BUFFER selects latest candidate when gap exceeds buffer."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 960)
    r3, t3 = _build_route_and_telemetry(
        "route_3", "Thameslink", TransitMode.TRAIN, 1500
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2, r3],
        rollup_strategy=RollupStrategy.LATE_WITH_BUFFER,
        route_late_buffer_seconds=300,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2, r3.route_id: t3}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_3"
    assert commute_state.master_rollup.seconds_to_leave == 1140


def test_arbitration_late_with_buffer_single_candidate() -> None:
    """Verify LATE_WITH_BUFFER functions properly with a single candidate."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1],
        rollup_strategy=RollupStrategy.LATE_WITH_BUFFER,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_1"
    assert commute_state.master_rollup.seconds_to_leave == 240


def test_arbitration_on_time_priority_over_late_arrival() -> None:
    """Verify routes arriving in time are prioritised over late routes."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry(
        "route_2", "Thameslink", TransitMode.TRAIN, 2000
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2],
        target_destination_time="08:45",
        rollup_strategy=RollupStrategy.LATEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_1"
    assert commute_state.master_rollup.will_arrive_on_time is True
    assert commute_state.master_rollup.seconds_to_leave == 240


def test_arbitration_all_routes_late_falls_back_to_strategy() -> None:
    """Verify late routes fallback to strategy selection if none arrive on time."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry("route_2", "Thameslink", TransitMode.TRAIN, 900)

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2],
        target_destination_time="08:15",
        rollup_strategy=RollupStrategy.LATEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_2"
    assert commute_state.master_rollup.will_arrive_on_time is False


def test_arbitration_positive_leave_prioritised_over_negative_leave() -> None:
    """Verify positive seconds_to_leave is preferred over negative sprint."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 330)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 600)

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2],
        rollup_strategy=RollupStrategy.SOONEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_2"
    assert commute_state.master_rollup.seconds_to_leave == 240


def test_arbitration_all_negative_leave_falls_back_to_strategy() -> None:
    """Verify all negative routes fallback to strategy selection."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 330)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 300)

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2],
        rollup_strategy=RollupStrategy.SOONEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_2"
    assert commute_state.master_rollup.seconds_to_leave == -60


def test_arbitration_helper_overrides() -> None:
    """Verify runtime helper overrides for rollup_strategy and buffer seconds."""
    r1, t1 = _build_route_and_telemetry("route_1", "24", TransitMode.BUS, 600)
    r2, t2 = _build_route_and_telemetry("route_2", "Northern", TransitMode.TUBE, 900)
    r3, t3 = _build_route_and_telemetry(
        "route_3", "Thameslink", TransitMode.TRAIN, 1160
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2, r3],
        rollup_strategy=RollupStrategy.SOONEST,
        route_late_buffer_seconds=300,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2, r3.route_id: t3}

    state_latest = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
        helper_overrides={"rollup_strategy": "latest"},
    )
    assert state_latest.master_rollup.active_option == "route_3"
    assert state_latest.master_rollup.strategy == RollupStrategy.LATEST

    state_buf_300 = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
        helper_overrides={
            "rollup_strategy": "late_with_buffer",
            "route_late_buffer_seconds": 300,
        },
    )
    assert state_buf_300.master_rollup.active_option == "route_2"

    state_buf_200 = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
        helper_overrides={
            "rollup_strategy": "late_with_buffer",
            "route_late_buffer_seconds": 200,
        },
    )
    assert state_buf_200.master_rollup.active_option == "route_3"


def test_arbitration_tie_breaker_slack() -> None:
    """Verify tie-breaker prefers candidate with greater target slack."""
    r1, t1 = _build_route_and_telemetry(
        "route_1", "24", TransitMode.BUS, 600, transit_duration_seconds=1200
    )
    r2, t2 = _build_route_and_telemetry(
        "route_2", "Northern", TransitMode.TUBE, 600, transit_duration_seconds=600
    )

    config = CommuteConfig(
        commute_id="test_commute",
        routes=[r1, r2],
        target_destination_time="09:00",
        rollup_strategy=RollupStrategy.LATEST,
    )
    engine = CommuteEngine(config=config, registry=TransitProviderRegistry())
    telemetries = {r1.route_id: t1, r2.route_id: t2}

    commute_state = engine.evaluate_commute(
        telemetries=telemetries,
        reference_time=datetime(2026, 9, 15, 8, 0, 0, tzinfo=timezone.utc),
    )

    assert commute_state.master_rollup.active_option == "route_2"
    assert commute_state.master_rollup.expected_destination_margin_seconds > 0
