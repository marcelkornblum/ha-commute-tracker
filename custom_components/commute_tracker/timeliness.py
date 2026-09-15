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
    PillBadge,
    RouteConfig,
    UrgencyStage,
)


@dataclass(slots=True, frozen=True)
class ResolvedThresholds:
    """Resolved time thresholds for a commute route following cascading resolution."""

    boarding_walk_seconds: int
    prep_seconds: int
    grace_seconds: int
    target_destination_time: str | None = None

    @property
    def total_buffer_seconds(self) -> int:
        """Calculate combined walking and preparation buffer threshold."""
        return self.boarding_walk_seconds + self.prep_seconds


def resolve_route_thresholds(
    route_config: RouteConfig | dict[str, Any],
    helper_overrides: dict[str, Any] | None = None,
    default_boarding_walk_seconds: int = DEFAULT_WALK_SECONDS,
    default_prep_seconds: int = DEFAULT_PREP_SECONDS,
    default_grace_seconds: int | None = None,
    default_grace_fraction: float | None = None,
    default_target_destination_time: str | None = None,
) -> ResolvedThresholds:
    """Resolve route time thresholds following the cascading resolution hierarchy.

    Precedence order:
    1. HA Input Helper Overrides
    2. YAML Route Configuration (seconds or fraction)
    3. Commute/Overall Defaults (seconds or fraction)
    4. Global Defaults

    :param route_config: RouteConfig object or route configuration dictionary.
    :param helper_overrides: Optional runtime overrides from HA input helpers.
    :param default_boarding_walk_seconds: Fallback walk duration in seconds.
    :param default_prep_seconds: Fallback prep buffer in seconds.
    :param default_grace_seconds: Fallback grace window in seconds.
    :param default_grace_fraction: Fallback grace fraction of walk duration.
    :param default_target_destination_time: Fallback target destination
        arrival time (HH:MM).
    :return: ResolvedThresholds instance.
    """
    helpers = helper_overrides or {}

    boarding_walk_seconds = _resolve_seconds(
        helpers=helpers,
        config=route_config,
        sec_key="boarding_walk_seconds",
        fallback=default_boarding_walk_seconds,
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
        walk_seconds=boarding_walk_seconds,
        commute_grace_seconds=default_grace_seconds,
        commute_grace_fraction=default_grace_fraction,
        global_fallback_fraction=DEFAULT_GRACE_FRACTION,
    )

    target_destination: str | None = None
    if helpers.get("target_destination_time"):
        target_destination = helpers["target_destination_time"]
    elif isinstance(route_config, dict) and route_config.get("target_destination_time"):
        target_destination = str(route_config["target_destination_time"])
    else:
        target_destination = default_target_destination_time

    return ResolvedThresholds(
        boarding_walk_seconds=boarding_walk_seconds,
        prep_seconds=prep_seconds,
        grace_seconds=grace_seconds,
        target_destination_time=target_destination,
    )


def _resolve_seconds(
    helpers: dict[str, Any],
    config: RouteConfig | dict[str, Any],
    sec_key: str,
    fallback: int,
) -> int:
    """Resolve an integer seconds value checking helper, then config, then fallback."""
    if sec_key in helpers and helpers[sec_key] is not None:
        return int(helpers[sec_key])
    if isinstance(config, RouteConfig):
        val = getattr(config, sec_key, None)
        if val is not None:
            return int(val)
    elif isinstance(config, dict) and config.get(sec_key) is not None:
        return int(config[sec_key])
    return fallback


def _resolve_grace_seconds(
    helpers: dict[str, Any],
    config: RouteConfig | dict[str, Any],
    walk_seconds: int,
    commute_grace_seconds: int | None,
    commute_grace_fraction: float | None,
    global_fallback_fraction: float = DEFAULT_GRACE_FRACTION,
) -> int:
    """Resolve grace seconds using tiered hierarchy and optional fraction of walk time.

    Precedence order:
    1. HA Helper explicit grace_seconds
    2. HA Helper grace_fraction
    3. Route explicit grace_seconds
    4. Route grace_fraction
    5. Commute grace_seconds
    6. Commute grace_fraction
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
    elif commute_grace_seconds is not None:
        raw_grace = int(commute_grace_seconds)
    elif commute_grace_fraction is not None:
        raw_grace = int(round(walk_seconds * float(commute_grace_fraction)))
    else:
        raw_grace = int(round(walk_seconds * global_fallback_fraction))

    return min(raw_grace, walk_seconds)


def is_departure_reachable(
    departure_seconds: int,
    boarding_walk_seconds: int,
    grace_seconds: int = DEFAULT_GRACE_SECONDS,
) -> bool:
    """Determine whether transit departure is physically reachable within grace window.

    A departure is reachable if the arrival time satisfies:
    `departure_seconds >= boarding_walk_seconds - grace_seconds`

    :param departure_seconds: Countdown to transit arrival at boarding stop.
    :param boarding_walk_seconds: Doorstep walking duration in seconds.
    :param grace_seconds: Leeway buffer allowing commuter to sprint to stop.
    :return: True if departure can still be caught, False if missed.
    """
    return departure_seconds >= (boarding_walk_seconds - grace_seconds)


def calculate_seconds_to_leave(
    departure_seconds: int,
    total_buffer_seconds: int,
) -> int:
    """Calculate countdown seconds until doorstep departure cutoff.

    :param departure_seconds: Seconds until vehicle arrives at boarding stop.
    :param total_buffer_seconds: Required walking and prep buffer in seconds.
    :return: Integer seconds until doorstep deadline (can be negative).
    """
    return departure_seconds - total_buffer_seconds


def calculate_urgency_stage(
    seconds_to_leave: int | None,
    prepare_threshold_seconds: int = DEFAULT_PREPARE_THRESHOLD_SECONDS,
) -> UrgencyStage:
    """Compute active urgency stage from doorstep leave countdown.

    :param seconds_to_leave: Seconds until doorstep departure deadline.
    :param prepare_threshold_seconds: Advance preparation buffer threshold.
    :return: UrgencyStage enum value.
    """
    if seconds_to_leave is None:
        return UrgencyStage.STANDBY

    if seconds_to_leave <= 0:
        return UrgencyStage.LEAVE_NOW

    if seconds_to_leave <= prepare_threshold_seconds:
        return UrgencyStage.PREPARE

    return UrgencyStage.RELAXED


def calculate_leave_by_time(
    seconds_to_leave: int,
    reference_time: datetime | None = None,
) -> str:
    """Calculate formatted doorstep departure clock time (HH:MM).

    :param seconds_to_leave: Countdown until doorstep departure deadline.
    :param reference_time: Datetime of observation (defaults to current time).
    :return: Formatted clock time string (HH:MM).
    """
    ref_dt = reference_time or datetime.now()
    leave_dt = ref_dt + timedelta(seconds=seconds_to_leave)
    return leave_dt.strftime("%H:%M")


def calculate_milestone_times(
    seconds_to_board: int,
    transit_duration_seconds: int = 0,
    alighting_walk_seconds: int = 0,
    reference_time: datetime | None = None,
    expected_boarding_time_str: str | None = None,
) -> tuple[str, str, str]:
    """Calculate formatted milestone times (HH:MM) for transit legs.

    :param seconds_to_board: Countdown to transit departure at boarding stop.
    :param transit_duration_seconds: Duration of transit journey in seconds.
    :param alighting_walk_seconds: Walking duration from alighting stop to destination.
    :param reference_time: Datetime of observation (defaults to current time).
    :param expected_boarding_time_str: Optional explicit ISO or formatted timestamp.
    :return: Tuple of expected boarding, alighting, and destination clock times.
    """
    ref_dt = reference_time or datetime.now()
    board_dt: datetime
    if expected_boarding_time_str and "T" in expected_boarding_time_str:
        try:
            board_dt = datetime.fromisoformat(expected_boarding_time_str)
        except ValueError:
            board_dt = ref_dt + timedelta(seconds=seconds_to_board)
    else:
        board_dt = ref_dt + timedelta(seconds=seconds_to_board)

    alight_dt = board_dt + timedelta(seconds=transit_duration_seconds)
    dest_dt = alight_dt + timedelta(seconds=alighting_walk_seconds)
    return (
        board_dt.strftime("%H:%M"),
        alight_dt.strftime("%H:%M"),
        dest_dt.strftime("%H:%M"),
    )


def format_next_summary(
    seconds_to_next_board: int | None,
    next_expected_time: str | None = None,
    reference_time: datetime | None = None,
) -> str:
    """Format subsequent service departure summary for display.

    :param seconds_to_next_board: Countdown to subsequent vehicle arrival.
    :param next_expected_time: Optional explicit ISO or HH:MM timestamp.
    :param reference_time: Datetime of observation.
    :return: Formatted summary string (e.g. 'Next at 08:36 (in 12m)' or
        'None scheduled').
    """
    if seconds_to_next_board is None:
        return "None scheduled"

    mins = max(0, int(round(seconds_to_next_board / 60)))
    ref_dt = reference_time or datetime.now()

    if next_expected_time and "T" in next_expected_time:
        try:
            dep_dt = datetime.fromisoformat(next_expected_time)
            clock_str = dep_dt.strftime("%H:%M")
        except ValueError:
            clock_str = (ref_dt + timedelta(seconds=seconds_to_next_board)).strftime(
                "%H:%M"
            )
    elif next_expected_time and ":" in next_expected_time:
        clock_str = next_expected_time
    else:
        clock_str = (ref_dt + timedelta(seconds=seconds_to_next_board)).strftime(
            "%H:%M"
        )

    return f"Next at {clock_str} (in {mins}m)"


def calculate_pill_badge(
    urgency_stage: UrgencyStage,
    seconds_to_leave: int | None = None,
) -> PillBadge:
    """Calculate UI badge styling and text tokens from urgency stage and countdown.

    :param urgency_stage: Active UrgencyStage enum value.
    :param seconds_to_leave: Optional countdown until doorstep deadline.
    :return: Strongly-typed PillBadge token model.
    """
    if urgency_stage == UrgencyStage.STANDBY or seconds_to_leave is None:
        return PillBadge(
            label="Standby",
            color="#8E8E93",
            bg="rgba(142, 142, 147, 0.2)",
            border="#8E8E93",
        )

    leave_in_minutes = int(round(seconds_to_leave / 60))

    if urgency_stage == UrgencyStage.LEAVE_NOW:
        return PillBadge(
            label="🚨 LEAVE NOW",
            color="#FF5252",
            bg="rgba(255, 82, 82, 0.15)",
            border="#FF5252",
        )

    if urgency_stage == UrgencyStage.PREPARE:
        label = f"Prepare ({leave_in_minutes}m)" if leave_in_minutes > 0 else "Prepare"
        return PillBadge(
            label=label,
            color="#FF9800",
            bg="rgba(255, 152, 0, 0.15)",
            border="#FF9800",
        )

    label = f"Leave in {leave_in_minutes}m" if leave_in_minutes > 0 else "Relaxed"
    return PillBadge(
        label=label,
        color="#4CAF50",
        bg="rgba(76, 175, 80, 0.15)",
        border="#4CAF50",
    )


def calculate_destination_margin(
    target_destination_time_str: str | None,
    seconds_to_board: int,
    transit_duration_seconds: int,
    alighting_walk_seconds: int,
    reference_time: datetime | None = None,
    line_status: LineStatus | None = None,
    is_delayed: bool = False,
    is_cancelled: bool = False,
) -> tuple[int | None, bool, str]:
    """Calculate destination arrival margin seconds and normalised timeliness status.

    :param target_destination_time_str: Target destination arrival deadline (HH:MM).
    :param seconds_to_board: Countdown to transit departure at boarding stop.
    :param transit_duration_seconds: Duration of transit journey in seconds.
    :param alighting_walk_seconds: Walking duration from alighting stop to destination.
    :param reference_time: Datetime of observation (defaults to current time).
    :param line_status: Optional LineStatus model holding disruption flags.
    :param is_delayed: Whether the service or route is marked delayed.
    :param is_cancelled: Whether the service or route is marked cancelled.
    :return: Tuple of expected destination margin seconds, arrival timeliness flag,
        and status label.
    """
    effective_cancelled = is_cancelled or (
        line_status.is_cancelled if line_status is not None else False
    )
    effective_delayed = is_delayed or (
        line_status.is_delayed if line_status is not None else False
    )

    ref_dt = reference_time or datetime.now()

    total_journey_seconds = (
        seconds_to_board + transit_duration_seconds + alighting_walk_seconds
    )
    est_arrival_dt = ref_dt + timedelta(seconds=total_journey_seconds)

    if not target_destination_time_str:
        if effective_cancelled:
            return None, False, "cancelled"
        if effective_delayed:
            return None, True, "delayed"
        return None, True, "on_time"

    target_time = _parse_time_string(time_str=target_destination_time_str)
    if ref_dt.tzinfo is not None:
        target_dt = datetime.combine(ref_dt.date(), target_time, tzinfo=ref_dt.tzinfo)
    else:
        target_dt = datetime.combine(ref_dt.date(), target_time)

    if (est_arrival_dt - target_dt).total_seconds() > MIDNIGHT_WRAP_THRESHOLD_SECONDS:
        target_dt += timedelta(days=1)
    elif (target_dt - est_arrival_dt).total_seconds() > MIDNIGHT_WRAP_THRESHOLD_SECONDS:
        target_dt -= timedelta(days=1)

    margin_seconds = int(round((target_dt - est_arrival_dt).total_seconds()))
    will_arrive_on_time = margin_seconds >= 0

    if effective_cancelled:
        timeliness_label = "cancelled"
        will_arrive_on_time = False
    elif not will_arrive_on_time:
        timeliness_label = "late"
    elif effective_delayed:
        timeliness_label = "delayed"
    elif margin_seconds >= 300:
        timeliness_label = "early"
    else:
        timeliness_label = "on_time"

    return margin_seconds, will_arrive_on_time, timeliness_label


def _parse_time_string(time_str: str) -> time:
    """Parse HH:MM formatted string into datetime.time."""
    parts = time_str.strip().split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))
