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
    calculate_leave_countdown,
    calculate_target_slack,
    calculate_urgency_stage,
    is_departure_reachable,
    resolve_route_thresholds,
)


def test_cascading_resolution_hierarchy() -> None:
    """Verify cascading resolution prioritises helpers over config and defaults."""
    res_default = resolve_route_thresholds(route_config={})
    assert res_default.walk_seconds == 240
    assert res_default.prep_seconds == 120
    assert res_default.grace_seconds == 180
    assert res_default.total_buffer_seconds == 360
    assert res_default.target_arrival_time is None

    config = {
        "walk_seconds": 300,
        "prep_seconds": 60,
        "grace_seconds": 120,
        "target_arrival_time": "14:45",
    }
    res_config = resolve_route_thresholds(route_config=config)
    assert res_config.walk_seconds == 300
    assert res_config.prep_seconds == 60
    assert res_config.grace_seconds == 120
    assert res_config.total_buffer_seconds == 360
    assert res_config.target_arrival_time == "14:45"

    helpers = {
        "walk_seconds": 180,
        "prep_seconds": 90,
    }
    res_overridden = resolve_route_thresholds(
        route_config=config, helper_overrides=helpers
    )
    assert res_overridden.walk_seconds == 180
    assert res_overridden.prep_seconds == 90
    assert res_overridden.grace_seconds == 120
    assert res_overridden.total_buffer_seconds == 270
    assert res_overridden.target_arrival_time == "14:45"


def test_cascading_resolution_with_route_config() -> None:
    """Verify cascading resolution handles strongly-typed RouteConfig."""
    route_cfg = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        walk_seconds=300,
        prep_seconds=60,
        grace_seconds=120,
        target_arrival_time="15:00",
    )
    resolved = resolve_route_thresholds(route_config=route_cfg)
    assert resolved.walk_seconds == 300
    assert resolved.prep_seconds == 60
    assert resolved.grace_seconds == 120
    assert resolved.target_arrival_time == "15:00"

    helpers = {"walk_seconds": 150}
    res_helper = resolve_route_thresholds(
        route_config=route_cfg,
        helper_overrides=helpers,
    )
    assert res_helper.walk_seconds == 150
    assert res_helper.prep_seconds == 60


def test_cascading_resolution_minute_conversion() -> None:
    """Verify helpers or configs specified in minutes are converted to seconds."""
    config = {"walk_minutes": 5, "prep_minutes": 2.5}
    resolved = resolve_route_thresholds(route_config=config)
    assert resolved.walk_seconds == 300
    assert resolved.prep_seconds == 150


def test_cascading_resolution_route_config_fallback_defaults() -> None:
    """Verify RouteConfig with None thresholds cascades to global defaults."""
    route_cfg = RouteConfig(
        route_id="bus_unconfigured",
        mode=TransitMode.BUS,
        line="26",
    )
    resolved = resolve_route_thresholds(route_config=route_cfg)
    assert resolved.walk_seconds == 240
    assert resolved.prep_seconds == 120
    assert resolved.grace_seconds == 180
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
                "id": "bus_minutes",
                "mode": "bus",
                "line": "73",
                "walk_minutes": 6,
                "prep_minutes": 3,
                "grace_minutes": 2,
            },
        ],
    }
    commute_cfg = CommuteConfig.from_dict(data=raw_config)
    route_defaults = commute_cfg.routes[0]
    resolved_defaults = resolve_route_thresholds(route_config=route_defaults)
    assert resolved_defaults.walk_seconds == 240
    assert resolved_defaults.prep_seconds == 120
    assert resolved_defaults.grace_seconds == 180

    route_minutes = commute_cfg.routes[1]
    resolved_minutes = resolve_route_thresholds(route_config=route_minutes)
    assert resolved_minutes.walk_seconds == 360
    assert resolved_minutes.prep_seconds == 180
    assert resolved_minutes.grace_seconds == 120


def test_leave_countdown_and_reachability() -> None:
    """Verify doorstep leave countdown math and physical reachability filter."""
    buffer_seconds = 360
    grace_seconds = 180

    leave_in = calculate_leave_countdown(
        seconds_to_arrival=400, buffer_seconds=buffer_seconds
    )
    assert leave_in == 40
    assert is_departure_reachable(
        leave_in_seconds=leave_in, grace_seconds=grace_seconds
    )

    leave_in = calculate_leave_countdown(
        seconds_to_arrival=360, buffer_seconds=buffer_seconds
    )
    assert leave_in == 0
    assert is_departure_reachable(
        leave_in_seconds=leave_in, grace_seconds=grace_seconds
    )

    leave_in = calculate_leave_countdown(
        seconds_to_arrival=200, buffer_seconds=buffer_seconds
    )
    assert leave_in == -160
    assert is_departure_reachable(
        leave_in_seconds=leave_in, grace_seconds=grace_seconds
    )

    leave_in = calculate_leave_countdown(
        seconds_to_arrival=170, buffer_seconds=buffer_seconds
    )
    assert leave_in == -190
    assert not is_departure_reachable(
        leave_in_seconds=leave_in, grace_seconds=grace_seconds
    )


def test_urgency_stage_boundaries() -> None:
    """Verify urgency state transitions at exact boundary points."""
    grace = 180

    assert (
        calculate_urgency_stage(leave_in_seconds=None, grace_seconds=grace)
        == UrgencyStage.STANDBY
    )
    assert (
        calculate_urgency_stage(leave_in_seconds=481, grace_seconds=grace)
        == UrgencyStage.RELAXED
    )
    assert (
        calculate_urgency_stage(leave_in_seconds=480, grace_seconds=grace)
        == UrgencyStage.PREPARE
    )
    assert (
        calculate_urgency_stage(leave_in_seconds=1, grace_seconds=grace)
        == UrgencyStage.PREPARE
    )
    assert (
        calculate_urgency_stage(leave_in_seconds=0, grace_seconds=grace)
        == UrgencyStage.LEAVE_NOW
    )
    assert (
        calculate_urgency_stage(leave_in_seconds=-180, grace_seconds=grace)
        == UrgencyStage.LEAVE_NOW
    )
    assert (
        calculate_urgency_stage(leave_in_seconds=-181, grace_seconds=grace)
        == UrgencyStage.STANDBY
    )


def test_calculate_target_slack_and_timeliness() -> None:
    """Verify slack minutes, will_arrive_in_time, and timeliness classifications."""
    ref_time = datetime(2026, 9, 14, 13, 54, 0, tzinfo=timezone.utc)

    slack_mins, will_arrive, timeliness = calculate_target_slack(
        target_arrival_time_str="14:45",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
    )
    assert slack_mins == 3
    assert will_arrive is True
    assert timeliness == "on_time"

    slack_mins, will_arrive, timeliness = calculate_target_slack(
        target_arrival_time_str="14:40",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
    )
    assert slack_mins == -2
    assert will_arrive is False
    assert timeliness == "late"

    slack_mins, will_arrive, timeliness = calculate_target_slack(
        target_arrival_time_str="15:00",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
    )
    assert slack_mins == 18
    assert will_arrive is True
    assert timeliness == "early"

    _, will_arrive_delayed, timeliness = calculate_target_slack(
        target_arrival_time_str="14:45",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
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
    _, will_arrive_ls, timeliness = calculate_target_slack(
        target_arrival_time_str="14:45",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
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
    _, will_arrive_canc, timeliness = calculate_target_slack(
        target_arrival_time_str="14:45",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        line_status=line_status_cancelled,
    )
    assert will_arrive_canc is False
    assert timeliness == "cancelled"

    _, will_arrive_late_delayed, timeliness = calculate_target_slack(
        target_arrival_time_str="14:40",
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        is_delayed=True,
    )
    assert will_arrive_late_delayed is False
    assert timeliness == "late"

    slack_none, will_arrive_none, timeliness = calculate_target_slack(
        target_arrival_time_str=None,
        boarding_arrival_seconds=360,
        in_vehicle_duration_seconds=1920,
        alighting_walk_seconds=600,
        reference_time=ref_time,
        is_delayed=True,
    )
    assert slack_none is None
    assert will_arrive_none is True
    assert timeliness == "delayed"
