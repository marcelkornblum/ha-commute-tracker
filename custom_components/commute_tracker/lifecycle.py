"""Pure-Python commute lifecycle transition detection and debouncing."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from custom_components.commute_tracker.engine import (
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import UrgencyStage


class CommuteEventType(StrEnum):
    """Canonical lifecycle event types emitted for commute transitions."""

    PREPARE = "prepare"
    AMBER_WARNING = "amber_warning"
    LEAVE_NOW = "leave_now"
    ROUTE_SWITCHED = "route_switched"
    ROLLOVER = "rollover"
    DISRUPTED = "disrupted"


COMMUTE_EVENT_TYPES: list[str] = [event_type.value for event_type in CommuteEventType]

_STAGE_ORDER: tuple[CommuteEventType, ...] = (
    CommuteEventType.PREPARE,
    CommuteEventType.AMBER_WARNING,
    CommuteEventType.LEAVE_NOW,
)
_URGENT_STAGES: frozenset[CommuteEventType] = frozenset(
    {CommuteEventType.AMBER_WARNING, CommuteEventType.LEAVE_NOW}
)
_ROUTE_SWITCH_CONFIRMATION_POLLS = 2


@dataclass(slots=True, frozen=True)
class CommuteLifecycleEvent:
    """Structured lifecycle event produced from commute state transitions."""

    event_type: CommuteEventType
    data: dict[str, Any]


def _format_minutes_phrase(leave_in_minutes: int) -> str:
    """Format leave countdown phrase with singular/plural grammar."""
    if leave_in_minutes <= 0:
        return "leave now!"
    unit = "minute" if leave_in_minutes == 1 else "minutes"
    return f"leave in {leave_in_minutes} {unit}."


def format_default_message(
    event_type: CommuteEventType,
    mode: str,
    route_label: str,
    expected_boarding_time: str,
    leave_in_minutes: int,
    person_name: str | None = None,
    status_label: str | None = None,
) -> str:
    """Build a natural-language announcement string for a lifecycle event."""
    service_noun = mode.strip() if mode and mode.strip() else "service"
    subject = (
        f"{person_name.strip()}'s {service_noun}"
        if person_name and person_name.strip()
        else f"Your {service_noun}"
    )
    board_time = expected_boarding_time or "soon"
    leave_phrase = _format_minutes_phrase(leave_in_minutes=leave_in_minutes)

    if event_type == CommuteEventType.LEAVE_NOW:
        return f"{subject} departs at {board_time}, leave now!"

    if event_type in {CommuteEventType.PREPARE, CommuteEventType.AMBER_WARNING}:
        return f"{subject} departs at {board_time}, {leave_phrase}"

    if event_type == CommuteEventType.ROUTE_SWITCHED:
        label_suffix = f" ({route_label})" if route_label else ""
        return (
            f"{subject}{label_suffix} is now best, departs at {board_time}, "
            f"{leave_phrase}"
        )

    if event_type == CommuteEventType.ROLLOVER:
        return f"{subject} rolled over to the {board_time} service, {leave_phrase}"

    label_suffix = f" ({route_label})" if route_label else ""
    disruption = status_label or "disrupted"
    return f"{subject}{label_suffix} has {disruption}."


def _determine_reached_stage(master: MasterRollupState) -> CommuteEventType | None:
    """Determine the highest urgency stage currently reached by master rollup."""
    if master.urgency_stage == UrgencyStage.LEAVE_NOW or master.seconds_to_leave <= 0:
        return CommuteEventType.LEAVE_NOW
    if (
        master.urgency_stage == UrgencyStage.PREPARE
        and master.seconds_to_leave <= master.amber_threshold_seconds
    ):
        return CommuteEventType.AMBER_WARNING
    if master.urgency_stage == UrgencyStage.PREPARE:
        return CommuteEventType.PREPARE
    return None


def _build_event(
    event_type: CommuteEventType,
    state: CommuteState,
    commute_title: str,
    person_name: str | None,
) -> CommuteLifecycleEvent:
    """Build structured event payload from evaluated commute state."""
    master = state.master_rollup
    leave_in_minutes = max(0, round(master.seconds_to_leave / 60))
    status_label = (
        master.line_status.status_label if master.line_status is not None else None
    )
    default_message = format_default_message(
        event_type=event_type,
        mode=master.mode,
        route_label=master.route_label,
        expected_boarding_time=master.expected_boarding_time,
        leave_in_minutes=leave_in_minutes,
        person_name=person_name,
        status_label=status_label,
    )
    payload: dict[str, Any] = {
        "commute_id": state.commute_id,
        "commute_title": commute_title,
        "person_name": person_name,
        "event_type": event_type.value,
        "active_option": master.active_option,
        "mode": master.mode,
        "route_label": master.route_label,
        "expected_boarding_time": master.expected_boarding_time,
        "leave_by_time": master.leave_by_time,
        "expected_destination_time": master.expected_destination_time,
        "seconds_to_leave": master.seconds_to_leave,
        "leave_in_minutes": leave_in_minutes,
        "expected_destination_margin_seconds": (
            master.expected_destination_margin_seconds
        ),
        "is_last_on_time_or_late": master.is_last_on_time_or_late,
        "timeliness": master.timeliness,
        "will_arrive_on_time": master.will_arrive_on_time,
        "default_message": default_message,
    }
    return CommuteLifecycleEvent(event_type=event_type, data=payload)


class CommuteLifecycleTracker:
    """Debounced state machine emitting commute lifecycle events from snapshots."""

    def __init__(self) -> None:
        """Initialise empty session state."""
        self._confirmed_option: str | None = None
        self._pending_switch: tuple[str, int] | None = None
        self._last_dep_key: tuple[str, str] | None = None
        self._last_seconds_to_board: int | None = None
        self._last_urgency_stage: UrgencyStage | None = None
        self._latched_stages: set[tuple[str, str, CommuteEventType]] = set()
        self._was_disrupted_by_option: dict[str, bool] = {}

    def reset(self) -> None:
        """Clear latched session state when commute becomes inactive."""
        self._confirmed_option = None
        self._pending_switch = None
        self._last_dep_key = None
        self._last_seconds_to_board = None
        self._last_urgency_stage = None
        self._latched_stages.clear()
        self._was_disrupted_by_option.clear()

    def _latch_through_stage(
        self, dep_key: tuple[str, str], stage: CommuteEventType
    ) -> None:
        """Latch the given urgency stage and all lower stages for a departure."""
        if stage not in _STAGE_ORDER:
            return
        max_idx = _STAGE_ORDER.index(stage)
        for idx in range(max_idx + 1):
            self._latched_stages.add((dep_key[0], dep_key[1], _STAGE_ORDER[idx]))

    def evaluate(
        self,
        state: CommuteState,
        is_active: bool,
        commute_title: str,
        person_name: str | None = None,
    ) -> list[CommuteLifecycleEvent]:
        """Evaluate a commute snapshot and return newly triggered lifecycle events."""
        master = state.master_rollup
        if not is_active or not master.is_active:
            self.reset()
            return []
        if master.active_option == "none":
            return []

        dep_identity = master.vehicle_id or master.expected_boarding_time
        dep_key = (master.active_option, dep_identity)
        reached_stage = _determine_reached_stage(master=master)
        events: list[CommuteLifecycleEvent] = []
        emitted_transition = False
        action_stages = {UrgencyStage.PREPARE, UrgencyStage.LEAVE_NOW}
        in_action_window = (
            self._last_urgency_stage in action_stages
            or master.urgency_stage in action_stages
        )

        if self._confirmed_option is None:
            self._confirmed_option = master.active_option
        elif master.active_option != self._confirmed_option:
            if in_action_window:
                prev_candidate, prev_count = (
                    self._pending_switch
                    if self._pending_switch is not None
                    else (None, 0)
                )
                count = prev_count + 1 if prev_candidate == master.active_option else 1
                if count < _ROUTE_SWITCH_CONFIRMATION_POLLS:
                    self._pending_switch = (master.active_option, count)
                    return []

                self._confirmed_option = master.active_option
                self._pending_switch = None
                events.append(
                    _build_event(
                        event_type=CommuteEventType.ROUTE_SWITCHED,
                        state=state,
                        commute_title=commute_title,
                        person_name=person_name,
                    )
                )
                emitted_transition = True
                if reached_stage is not None and reached_stage not in _URGENT_STAGES:
                    self._latch_through_stage(dep_key=dep_key, stage=reached_stage)
            else:
                self._confirmed_option = master.active_option
                self._pending_switch = None
        else:
            self._pending_switch = None

        if (
            not emitted_transition
            and self._last_dep_key is not None
            and self._last_dep_key[0] == master.active_option
            and dep_key != self._last_dep_key
            and self._last_seconds_to_board is not None
            and master.seconds_to_board > self._last_seconds_to_board
        ):
            self._latched_stages.clear()
            events.append(
                _build_event(
                    event_type=CommuteEventType.ROLLOVER,
                    state=state,
                    commute_title=commute_title,
                    person_name=person_name,
                )
            )
            emitted_transition = True
            if reached_stage is not None and reached_stage not in _URGENT_STAGES:
                self._latch_through_stage(dep_key=dep_key, stage=reached_stage)

        should_emit_stage = reached_stage is not None and (
            not emitted_transition or reached_stage in _URGENT_STAGES
        )
        if should_emit_stage and reached_stage is not None:
            latch_key = (dep_key[0], dep_key[1], reached_stage)
            if latch_key not in self._latched_stages:
                events.append(
                    _build_event(
                        event_type=reached_stage,
                        state=state,
                        commute_title=commute_title,
                        person_name=person_name,
                    )
                )
                self._latch_through_stage(dep_key=dep_key, stage=reached_stage)

        is_disrupted = bool(
            master.line_status is not None
            and (master.line_status.is_delayed or master.line_status.is_cancelled)
        )
        was_disrupted = self._was_disrupted_by_option.get(master.active_option, False)
        if is_disrupted and not was_disrupted:
            events.append(
                _build_event(
                    event_type=CommuteEventType.DISRUPTED,
                    state=state,
                    commute_title=commute_title,
                    person_name=person_name,
                )
            )
        self._was_disrupted_by_option[master.active_option] = is_disrupted

        self._last_dep_key = dep_key
        self._last_seconds_to_board = master.seconds_to_board
        self._last_urgency_stage = master.urgency_stage
        return events
