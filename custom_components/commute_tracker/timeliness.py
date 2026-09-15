"""Timeliness calculation, cascading thresholds, and urgency transition engine.

Provides pure-Python calculations for doorstep reachability, leave deadlines,
destination slack, and urgency state machines.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from custom_components.commute_tracker.const import (
    DEFAULT_GRACE_FRACTION,
    DEFAULT_GRACE_SECONDS,
    DEFAULT_PREP_SECONDS,
    DEFAULT_PREPARE_THRESHOLD_SECONDS,
    DEFAULT_WALK_SECONDS,
    MIDNIGHT_WRAP_THRESHOLD_SECONDS,
)
from custom_components.commute_tracker.models import (
    LineStatus,
    RouteConfig,
    UrgencyStage,
)


@dataclass(slots=True, frozen=True)
class ResolvedThresholds:
    """Resolved time thresholds for a commute route following cascading resolution."""

    walk_seconds: int
    prep_seconds: int
    grace_seconds: int
    target_arrival_time: str | None = None

    @property
    def total_buffer_seconds(self) -> int:
        """Calculate combined walking and preparation buffer threshold."""
        return self.walk_seconds + self.prep_seconds


def resolve_route_thresholds(
    route_config: RouteConfig | dict[str, Any],
    helper_overrides: dict[str, Any] | None = None,
    default_walk_seconds: int = DEFAULT_WALK_SECONDS,
    default_prep_seconds: int = DEFAULT_PREP_SECONDS,
    default_grace_seconds: int | None = None,
    default_grace_fraction: float | None = None,
    default_target_arrival_time: str | None = None,
) -> ResolvedThresholds:
    """Resolve route time thresholds following the cascading resolution hierarchy.

    Precedence order:
    1. HA Input Helper Overrides
    2. YAML Route Configuration (seconds or fraction)
    3. Commute/Overall Defaults (seconds or fraction)
    4. Global Defaults

    :param route_config: RouteConfig object or route configuration dictionary.
    :param helper_overrides: Optional runtime overrides from HA input helpers.
    :param default_walk_seconds: Fallback walk duration in seconds.
    :param default_prep_seconds: Fallback prep buffer in seconds.
    :param default_grace_seconds: Fallback grace window in seconds.
    :param default_grace_fraction: Fallback grace fraction of walk duration.
    :param default_target_arrival_time: Fallback target arrival time (HH:MM).
    :return: ResolvedThresholds instance.
    """
    helpers = helper_overrides or {}

    walk_seconds = _resolve_seconds(
        helpers=helpers,
        config=route_config,
        sec_key="walk_seconds",
        fallback=default_walk_seconds,
    )

    prep_seconds = _resolve_seconds(
        helpers=helpers,
        config=route_config,
        sec_key="prep_seconds",
        fallback=default_prep_seconds,
    )

    grace_seconds = _resolve_grace_seconds(
        helpers=helpers,
        config=route_config,
        walk_seconds=walk_seconds,
        default_grace_seconds=default_grace_seconds,
        default_grace_fraction=default_grace_fraction,
        global_fallback_fraction=DEFAULT_GRACE_FRACTION,
    )

    target_arrival: str | None = None
    if helpers.get("target_arrival_time"):
        target_arrival = helpers["target_arrival_time"]
    elif isinstance(route_config, RouteConfig):
        target_arrival = route_config.target_arrival_time or default_target_arrival_time
    else:
        target_arrival = (
            route_config.get("target_arrival_time") or default_target_arrival_time
        )

    return ResolvedThresholds(
        walk_seconds=walk_seconds,
        prep_seconds=prep_seconds,
        grace_seconds=grace_seconds,
        target_arrival_time=target_arrival,
    )


def _resolve_grace_seconds(
    helpers: dict[str, Any],
    config: RouteConfig | dict[str, Any],
    walk_seconds: int,
    default_grace_seconds: int | None,
    default_grace_fraction: float | None,
    global_fallback_fraction: float = DEFAULT_GRACE_FRACTION,
) -> int:
    """Resolve grace seconds using tiered hierarchy and optional fraction of walk time.

    Precedence order:
    1. HA Helper explicit grace_seconds
    2. HA Helper grace_fraction
    3. Route explicit grace_seconds
    4. Route grace_fraction
    5. Commute default_grace_seconds
    6. Commute default_grace_fraction
    7. Global default fraction fallback (0.25)

    Grace seconds are capped at walk_seconds so minimum travel time cannot be negative.
    """
    raw_grace: int | None = None

    if "grace_seconds" in helpers and helpers["grace_seconds"] is not None:
        raw_grace = int(helpers["grace_seconds"])
    elif "grace_fraction" in helpers and helpers["grace_fraction"] is not None:
        raw_grace = int(round(walk_seconds * float(helpers["grace_fraction"])))
    elif isinstance(config, RouteConfig) and config.grace_seconds is not None:
        raw_grace = int(config.grace_seconds)
    elif isinstance(config, dict) and config.get("grace_seconds") is not None:
        raw_grace = int(config["grace_seconds"])
    elif isinstance(config, RouteConfig) and config.grace_fraction is not None:
        raw_grace = int(round(walk_seconds * float(config.grace_fraction)))
    elif isinstance(config, dict) and config.get("grace_fraction") is not None:
        raw_grace = int(round(walk_seconds * float(config["grace_fraction"])))
    elif default_grace_seconds is not None:
        raw_grace = int(default_grace_seconds)
    elif default_grace_fraction is not None:
        raw_grace = int(round(walk_seconds * float(default_grace_fraction)))
    else:
        raw_grace = int(round(walk_seconds * global_fallback_fraction))

    return max(0, min(raw_grace, walk_seconds))


def _resolve_seconds(
    helpers: dict[str, Any],
    config: RouteConfig | dict[str, Any],
    sec_key: str,
    fallback: int,
) -> int:
    """Resolve a seconds threshold from helpers, config, or fallback."""
    if sec_key in helpers and helpers[sec_key] is not None:
        return int(helpers[sec_key])

    if isinstance(config, RouteConfig):
        val = getattr(config, sec_key, None)
        if val is not None:
            return int(val)
        return fallback

    if sec_key in config and config[sec_key] is not None:
        return int(config[sec_key])

    return fallback


def calculate_leave_countdown(seconds_to_arrival: int, buffer_seconds: int) -> int:
    """Calculate remaining seconds until doorstep departure deadline.

    :param seconds_to_arrival: Countdown to transit arrival at boarding stop.
    :param buffer_seconds: Combined walk and preparation duration threshold.
    :return: Seconds until departure (negative indicates departure time passed).
    """
    return seconds_to_arrival - buffer_seconds


def is_departure_reachable(
    seconds_to_arrival: int,
    walk_seconds: int,
    grace_seconds: int = DEFAULT_GRACE_SECONDS,
) -> bool:
    """Determine whether transit departure is physically reachable within grace window.

    A departure is reachable if the arrival time satisfies:
    `seconds_to_arrival >= walk_seconds - grace_seconds`

    :param seconds_to_arrival: Countdown to transit arrival at boarding stop.
    :param walk_seconds: Doorstep walking duration in seconds.
    :param grace_seconds: Leeway buffer allowing commuter to sprint to stop.
    :return: True if departure can still be caught, False if missed.
    """
    return seconds_to_arrival >= (walk_seconds - grace_seconds)


def calculate_urgency_stage(
    leave_in_seconds: int | None,
    prepare_threshold_seconds: int = DEFAULT_PREPARE_THRESHOLD_SECONDS,
) -> UrgencyStage:
    """Determine the active urgency lifecycle stage from leave countdown.

    :param leave_in_seconds: Seconds until doorstep departure deadline
        (None if no active departure).
    :param prepare_threshold_seconds: Relaxed-to-prepare transition threshold.
    :return: UrgencyStage enum instance.
    """
    if leave_in_seconds is None:
        return UrgencyStage.STANDBY
    if leave_in_seconds <= 0:
        return UrgencyStage.LEAVE_NOW
    if leave_in_seconds <= prepare_threshold_seconds:
        return UrgencyStage.PREPARE
    return UrgencyStage.RELAXED


def calculate_target_slack(
    target_arrival_time_str: str | None,
    boarding_arrival_seconds: int,
    in_vehicle_duration_seconds: int,
    alighting_walk_seconds: int,
    reference_time: datetime | None = None,
    line_status: LineStatus | None = None,
    is_delayed: bool = False,
    is_cancelled: bool = False,
) -> tuple[int | None, bool, str]:
    """Calculate destination arrival slack minutes and normalised timeliness status.

    :param target_arrival_time_str: Target destination arrival deadline (HH:MM).
    :param boarding_arrival_seconds: Countdown to arrival at boarding stop.
    :param in_vehicle_duration_seconds: Duration of transit journey in seconds.
    :param alighting_walk_seconds: Walking duration from alighting stop to destination.
    :param reference_time: Datetime of observation (defaults to current time).
    :param line_status: Optional LineStatus model holding disruption flags.
    :param is_delayed: Whether the service or route is marked delayed.
    :param is_cancelled: Whether the service or route is marked cancelled.
    :return: Tuple of (target_slack_minutes, will_arrive_in_time, timeliness_label).
    """
    effective_cancelled = is_cancelled or (
        line_status.is_cancelled if line_status is not None else False
    )
    effective_delayed = is_delayed or (
        line_status.is_delayed if line_status is not None else False
    )

    ref_dt = reference_time or datetime.now()

    total_journey_seconds = (
        boarding_arrival_seconds + in_vehicle_duration_seconds + alighting_walk_seconds
    )
    est_arrival_dt = ref_dt + timedelta(seconds=total_journey_seconds)

    if not target_arrival_time_str:
        if effective_cancelled:
            return None, False, "cancelled"
        if effective_delayed:
            return None, True, "delayed"
        return None, True, "on_time"

    target_time = _parse_time_string(time_str=target_arrival_time_str)
    if ref_dt.tzinfo is not None:
        target_dt = datetime.combine(ref_dt.date(), target_time, tzinfo=ref_dt.tzinfo)
    else:
        target_dt = datetime.combine(ref_dt.date(), target_time)

    if (est_arrival_dt - target_dt).total_seconds() > MIDNIGHT_WRAP_THRESHOLD_SECONDS:
        target_dt += timedelta(days=1)
    elif (target_dt - est_arrival_dt).total_seconds() > MIDNIGHT_WRAP_THRESHOLD_SECONDS:
        target_dt -= timedelta(days=1)

    slack_seconds = (target_dt - est_arrival_dt).total_seconds()
    slack_minutes = int(round(slack_seconds / 60))
    will_arrive_in_time = slack_seconds >= 0

    if effective_cancelled:
        timeliness_label = "cancelled"
        will_arrive_in_time = False
    elif not will_arrive_in_time:
        timeliness_label = "late"
    elif effective_delayed:
        timeliness_label = "delayed"
    elif slack_minutes >= 5:
        timeliness_label = "early"
    else:
        timeliness_label = "on_time"

    return slack_minutes, will_arrive_in_time, timeliness_label


def _parse_time_string(time_str: str) -> time:
    """Parse HH:MM formatted string into datetime.time."""
    parts = time_str.strip().split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))
