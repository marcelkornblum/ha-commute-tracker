"""Unit tests for timeliness, cascading thresholds, and urgency transitions."""

from datetime import datetime, timezone

from custom_components.commute_tracker.models import (
    CommuteConfig,
    LineStatus,
    RouteConfig,
    TransitMode,
    UrgencyStage,
)
from custom_components.commute_tracker.timeliness import (
    calculate_destination_margin,
    calculate_seconds_to_leave,
    calculate_urgency_stage,
    is_departure_reachable,
    resolve_route_thresholds,
)


def test_cascading_resolution_hierarchy() -> None:
    """Verify cascading resolution prioritises helpers over config and defaults."""
    res_default = resolve_route_thresholds(route_config={})
    assert res_default.boarding_walk_seconds == 240
    assert res_default.prep_seconds == 120
    assert res_default.grace_seconds == 60
    assert res_default.total_buffer_seconds == 360
    assert res_default.target_destination_time is None

    config = {
        "boarding_walk_seconds": 300,
        "prep_seconds": 60,
        "grace_seconds": 120,
        "target_destination_time": "14:45",
    }
    res_config = resolve_route_thresholds(route_config=config)
    assert res_config.boarding_walk_seconds == 300
    assert res_config.prep_seconds == 60
    assert res_config.grace_seconds == 120
    assert res_config.total_buffer_seconds == 360
    assert res_config.target_destination_time == "14:45"

    helpers = {
        "boarding_walk_seconds": 180,
        "prep_seconds": 90,
    }
    res_overridden = resolve_route_thresholds(
        route_config=config, helper_overrides=helpers
    )
    assert res_overridden.boarding_walk_seconds == 180
    assert res_overridden.prep_seconds == 90
    assert res_overridden.grace_seconds == 120
    assert res_overridden.total_buffer_seconds == 270
    assert res_overridden.target_destination_time == "14:45"


def test_cascading_resolution_with_route_config() -> None:
    """Verify cascading resolution handles strongly-typed RouteConfig."""
    route_cfg = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        boarding_walk_seconds=300,
        prep_seconds=60,
        grace_seconds=120,
    )
    resolved = resolve_route_thresholds(
        route_config=route_cfg,
        default_target_destination_time="15:00",
    )
    assert resolved.boarding_walk_seconds == 300
    assert resolved.prep_seconds == 60
    assert resolved.grace_seconds == 120
    assert resolved.target_destination_time == "15:00"

    helpers = {"boarding_walk_seconds": 150}
    res_helper = resolve_route_thresholds(
        route_config=route_cfg,
        helper_overrides=helpers,
    )
    assert res_helper.boarding_walk_seconds == 150
    assert res_helper.prep_seconds == 60


def test_cascading_resolution_route_config_fallback_defaults() -> None:
    """Verify RouteConfig with None thresholds cascades to global defaults."""
    route_cfg = RouteConfig(
        route_id="bus_unconfigured",
        mode=TransitMode.BUS,
        line="26",
    )
    resolved = resolve_route_thresholds(route_config=route_cfg)
    assert resolved.boarding_walk_seconds == 240
    assert resolved.prep_seconds == 120
    assert resolved.grace_seconds == 60
    assert resolved.total_buffer_seconds == 360


def test_commute_config_from_dict_cascading_fallbacks() -> None:
    """Verify CommuteConfig.from_dict preserves None for cascading resolution."""
    raw_config = {
        "commute_id": "work",
        "routes": [
            {
                "id": "bus_defaults",
                "mode": "bus",
                "line": "26",
            },
            {
                "id": "bus_seconds",
                "mode": "bus",
                "line": "73",
                "boarding_walk_seconds": 360,
                "prep_seconds": 180,
                "grace_seconds": 120,
            },
        ],
    }
    commute_cfg = CommuteConfig.from_dict(data=raw_config)
    route_defaults = commute_cfg.routes[0]
    resolved_defaults = resolve_route_thresholds(route_config=route_defaults)
    assert resolved_defaults.boarding_walk_seconds == 240
    assert resolved_defaults.prep_seconds == 120
    assert resolved_defaults.grace_seconds == 60

    route_custom = commute_cfg.routes[1]
    resolved_custom = resolve_route_thresholds(route_config=route_custom)
    assert resolved_custom.boarding_walk_seconds == 360
    assert resolved_custom.prep_seconds == 180
    assert resolved_custom.grace_seconds == 120


def test_leave_countdown_and_reachability() -> None:
    """Verify doorstep leave countdown math and physical reachability filter."""
    walk_seconds = 240
    prep_seconds = 120
    buffer_seconds = walk_seconds + prep_seconds
    grace_seconds = 180

    leave_in = calculate_seconds_to_leave(
        departure_seconds=400, total_buffer_seconds=buffer_seconds
    )
    assert leave_in == 40
    assert is_departure_reachable(
        departure_seconds=400,
        boarding_walk_seconds=walk_seconds,
        grace_seconds=grace_seconds,
    )

    leave_in = calculate_seconds_to_leave(
        departure_seconds=360, total_buffer_seconds=buffer_seconds
    )
    assert leave_in == 0
    assert is_departure_reachable(
        departure_seconds=360,
        boarding_walk_seconds=walk_seconds,
        grace_seconds=grace_seconds,
    )

    leave_in = calculate_seconds_to_leave(
        departure_seconds=100, total_buffer_seconds=buffer_seconds
    )
    assert leave_in == -260
    assert is_departure_reachable(
        departure_seconds=100,
        boarding_walk_seconds=walk_seconds,
        grace_seconds=grace_seconds,
    )

    leave_in = calculate_seconds_to_leave(
        departure_seconds=50, total_buffer_seconds=buffer_seconds
    )
    assert leave_in == -310
    assert not is_departure_reachable(
        departure_seconds=50,
        boarding_walk_seconds=walk_seconds,
        grace_seconds=grace_seconds,
    )


def test_urgency_stage_boundaries() -> None:
    """Verify urgency state transitions at exact boundary points."""
    assert calculate_urgency_stage(seconds_to_leave=None) == UrgencyStage.STANDBY
    assert calculate_urgency_stage(seconds_to_leave=481) == UrgencyStage.RELAXED
    assert calculate_urgency_stage(seconds_to_leave=480) == UrgencyStage.PREPARE
    assert calculate_urgency_stage(seconds_to_leave=1) == UrgencyStage.PREPARE
    assert calculate_urgency_stage(seconds_to_leave=0) == UrgencyStage.LEAVE_NOW
    assert calculate_urgency_stage(seconds_to_leave=-180) == UrgencyStage.LEAVE_NOW


def test_calculate_target_slack_and_timeliness() -> None:
    """Verify margin seconds, will_arrive_on_time, and timeliness classifications."""
    ref_time = datetime(2026, 9, 14, 13, 54, 0, tzinfo=timezone.utc)

    margin_sec, will_arrive, timeliness = calculate_destination_margin(
        target_destination_time_str="14:45",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
    )
    assert margin_sec == 180
    assert will_arrive is True
    assert timeliness == "on_time"

    margin_sec, will_arrive, timeliness = calculate_destination_margin(
        target_destination_time_str="14:40",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
    )
    assert margin_sec == -120
    assert will_arrive is False
    assert timeliness == "late"

    margin_sec, will_arrive, timeliness = calculate_destination_margin(
        target_destination_time_str="15:00",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
    )
    assert margin_sec == 1080
    assert will_arrive is True
    assert timeliness == "early"

    _, will_arrive_delayed, timeliness = calculate_destination_margin(
        target_destination_time_str="14:45",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        is_delayed=True,
    )
    assert will_arrive_delayed is True
    assert timeliness == "delayed"

    line_status_delayed = LineStatus(
        status_label="Severe Delays",
        is_delayed=True,
    )
    _, will_arrive_ls, timeliness = calculate_destination_margin(
        target_destination_time_str="14:45",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        line_status=line_status_delayed,
    )
    assert will_arrive_ls is True
    assert timeliness == "delayed"

    line_status_cancelled = LineStatus(
        status_label="Suspended",
        is_cancelled=True,
    )
    _, will_arrive_canc, timeliness = calculate_destination_margin(
        target_destination_time_str="14:45",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        line_status=line_status_cancelled,
    )
    assert will_arrive_canc is False
    assert timeliness == "cancelled"

    _, will_arrive_late_delayed, timeliness = calculate_destination_margin(
        target_destination_time_str="14:40",
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        is_delayed=True,
    )
    assert will_arrive_late_delayed is False
    assert timeliness == "late"

    margin_none, will_arrive_none, timeliness = calculate_destination_margin(
        target_destination_time_str=None,
        seconds_to_board=360,
        transit_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        is_delayed=True,
    )
    assert margin_none is None
    assert will_arrive_none is True
    assert timeliness == "delayed"


def test_grace_fraction_and_hierarchical_resolution() -> None:
    """Verify route-level and commute-level grace fraction cascading resolution."""
    route_frac = RouteConfig(
        route_id="bus_fraction",
        mode=TransitMode.BUS,
        line="26",
        boarding_walk_seconds=240,
        grace_fraction=0.25,
    )
    res_route_frac = resolve_route_thresholds(route_config=route_frac)
    assert res_route_frac.boarding_walk_seconds == 240
    assert res_route_frac.grace_seconds == 60

    route_plain = RouteConfig(
        route_id="train_plain",
        mode=TransitMode.TRAIN,
        line="southeastern",
        boarding_walk_seconds=600,
    )
    res_commute_frac = resolve_route_thresholds(
        route_config=route_plain,
        default_grace_fraction=0.2,
    )
    assert res_commute_frac.boarding_walk_seconds == 600
    assert res_commute_frac.grace_seconds == 120

    res_override = resolve_route_thresholds(
        route_config=route_frac,
        default_grace_fraction=0.5,
    )
    assert res_override.grace_seconds == 60

    res_helper = resolve_route_thresholds(
        route_config=route_frac,
        helper_overrides={"grace_fraction": 0.1},
    )
    assert res_helper.grace_seconds == 24

    route_excessive = RouteConfig(
        route_id="tube_excessive",
        mode=TransitMode.TUBE,
        line="central",
        boarding_walk_seconds=90,
        grace_seconds=180,
    )
    res_excessive = resolve_route_thresholds(route_config=route_excessive)
    assert res_excessive.grace_seconds == 90


def test_commute_config_default_grace_parsing() -> None:
    """Verify CommuteConfig.from_dict parses top-level and route-level grace."""
    raw = {
        "commute_id": "multi_grace",
        "grace_fraction": 0.25,
        "routes": [
            {
                "id": "r1",
                "mode": "bus",
                "line": "26",
                "boarding_walk_seconds": 240,
            },
            {
                "id": "r2",
                "mode": "train",
                "line": "southeastern",
                "boarding_walk_seconds": 300,
                "grace_fraction": 0.1,
            },
            {
                "id": "r3",
                "mode": "tube",
                "line": "central",
                "boarding_walk_seconds": 400,
                "grace_seconds": 45,
            },
        ],
    }
    cfg = CommuteConfig.from_dict(raw)
    assert cfg.grace_fraction == 0.25
    assert cfg.routes[0].grace_fraction is None
    assert cfg.routes[1].grace_fraction == 0.1
    assert cfg.routes[2].grace_seconds == 45


def test_grace_precedence_hierarchy() -> None:
    """Verify strict step-by-step precedence for all grace configuration tiers."""
    cfg_bare = RouteConfig(
        route_id="r_bare",
        mode=TransitMode.BUS,
        line="26",
        boarding_walk_seconds=200,
    )
    res1 = resolve_route_thresholds(route_config=cfg_bare)
    assert res1.grace_seconds == 50

    res2 = resolve_route_thresholds(
        route_config=cfg_bare,
        default_grace_fraction=0.20,
    )
    assert res2.grace_seconds == 40

    res3 = resolve_route_thresholds(
        route_config=cfg_bare,
        default_grace_seconds=35,
        default_grace_fraction=0.20,
    )
    assert res3.grace_seconds == 35

    cfg_route_frac = RouteConfig(
        route_id="r_frac",
        mode=TransitMode.BUS,
        line="26",
        boarding_walk_seconds=200,
        grace_fraction=0.15,
    )
    res4 = resolve_route_thresholds(
        route_config=cfg_route_frac,
        default_grace_seconds=35,
        default_grace_fraction=0.20,
    )
    assert res4.grace_seconds == 30

    cfg_route_sec = RouteConfig(
        route_id="r_sec",
        mode=TransitMode.BUS,
        line="26",
        boarding_walk_seconds=200,
        grace_seconds=25,
        grace_fraction=0.15,
    )
    res5 = resolve_route_thresholds(
        route_config=cfg_route_sec,
        default_grace_seconds=35,
        default_grace_fraction=0.20,
    )
    assert res5.grace_seconds == 25

    res6 = resolve_route_thresholds(
        route_config=cfg_route_sec,
        default_grace_seconds=35,
        default_grace_fraction=0.20,
        helper_overrides={"grace_fraction": 0.05},
    )
    assert res6.grace_seconds == 10

    res7 = resolve_route_thresholds(
        route_config=cfg_route_sec,
        default_grace_seconds=35,
        default_grace_fraction=0.20,
        helper_overrides={"grace_seconds": 5, "grace_fraction": 0.05},
    )
    assert res7.grace_seconds == 5
