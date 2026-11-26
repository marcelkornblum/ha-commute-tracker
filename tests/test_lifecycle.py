"""Pure-Python unit tests for commute lifecycle transition and debounce engine."""

from custom_components.commute_tracker.engine import (
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.lifecycle import (
    COMMUTE_EVENT_TYPES,
    CommuteEventType,
    CommuteLifecycleTracker,
    format_default_message,
)
from custom_components.commute_tracker.models import (
    LineStatus,
    UrgencyStage,
)


def _make_state(
    *,
    active_option: str = "southern",
    mode: str = "train",
    route_label: str = "Southern",
    vehicle_id: str | None = None,
    urgency_stage: UrgencyStage = UrgencyStage.RELAXED,
    expected_boarding_time: str = "08:11",
    leave_by_time: str = "07:58",
    expected_destination_time: str = "08:40",
    seconds_to_leave: int = 600,
    seconds_to_board: int = 1200,
    amber_threshold_seconds: int = 210,
    prepare_threshold_seconds: int = 480,
    timeliness: str = "on_time",
    will_arrive_on_time: bool = True,
    line_status: LineStatus | None = None,
    is_active: bool = True,
) -> CommuteState:
    return CommuteState(
        commute_id="kolya_school",
        master_rollup=MasterRollupState(
            active_option=active_option,
            mode=mode,
            vehicle_id=vehicle_id,
            urgency_stage=urgency_stage,
            leave_by_time=leave_by_time,
            expected_boarding_time=expected_boarding_time,
            expected_destination_time=expected_destination_time,
            seconds_to_leave=seconds_to_leave,
            seconds_to_board=seconds_to_board,
            route_label=route_label,
            will_arrive_on_time=will_arrive_on_time,
            timeliness=timeliness,
            line_status=line_status,
            prepare_threshold_seconds=prepare_threshold_seconds,
            amber_threshold_seconds=amber_threshold_seconds,
            is_active=is_active,
        ),
    )


def test_commute_event_types_derived_from_enum() -> None:
    assert COMMUTE_EVENT_TYPES == [
        "prepare",
        "amber_warning",
        "leave_now",
        "route_switched",
        "rollover",
        "disrupted",
    ]


def test_format_default_message_handles_person_name_and_pluralisation() -> None:
    msg_leave_now = format_default_message(
        event_type=CommuteEventType.LEAVE_NOW,
        mode="train",
        route_label="Southern",
        expected_boarding_time="08:11",
        leave_in_minutes=0,
        person_name="Kolya",
    )
    assert msg_leave_now == "Kolya's train departs at 08:11, leave now!"

    msg_amber_plural = format_default_message(
        event_type=CommuteEventType.AMBER_WARNING,
        mode="bus",
        route_label="322",
        expected_boarding_time="08:30",
        leave_in_minutes=2,
        person_name="Kolya",
    )
    assert msg_amber_plural == "Kolya's bus departs at 08:30, leave in 2 minutes."

    msg_singular_no_person = format_default_message(
        event_type=CommuteEventType.PREPARE,
        mode="tube",
        route_label="Victoria",
        expected_boarding_time="08:15",
        leave_in_minutes=1,
        person_name=None,
    )
    assert msg_singular_no_person == "Your tube departs at 08:15, leave in 1 minute."

    msg_disrupted = format_default_message(
        event_type=CommuteEventType.DISRUPTED,
        mode="train",
        route_label="Southern",
        expected_boarding_time="08:11",
        leave_in_minutes=5,
        person_name="Kolya",
        status_label="Severe Delays",
    )
    assert msg_disrupted == "Kolya's train (Southern) has Severe Delays."


def test_lifecycle_stage_escalation_and_jitter_latching() -> None:
    tracker = CommuteLifecycleTracker()

    assert (
        tracker.evaluate(
            state=_make_state(urgency_stage=UrgencyStage.RELAXED, seconds_to_leave=600),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )

    prep_events = tracker.evaluate(
        state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=420),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in prep_events] == [CommuteEventType.PREPARE]
    assert prep_events[0].data["leave_in_minutes"] == 7
    assert prep_events[0].data["mode"] == "train"
    assert prep_events[0].data["person_name"] == "Kolya"

    assert (
        tracker.evaluate(
            state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=485),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )

    amber_events = tracker.evaluate(
        state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=205),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in amber_events] == [CommuteEventType.AMBER_WARNING]

    assert (
        tracker.evaluate(
            state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=215),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )
    assert (
        tracker.evaluate(
            state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=200),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )

    leave_events = tracker.evaluate(
        state=_make_state(urgency_stage=UrgencyStage.LEAVE_NOW, seconds_to_leave=-2),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in leave_events] == [CommuteEventType.LEAVE_NOW]
    assert leave_events[0].data["leave_in_minutes"] == 0
    assert (
        leave_events[0].data["default_message"]
        == "Kolya's train departs at 08:11, leave now!"
    )

    assert (
        tracker.evaluate(
            state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=2),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )
    assert (
        tracker.evaluate(
            state=_make_state(
                urgency_stage=UrgencyStage.LEAVE_NOW, seconds_to_leave=-1
            ),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )


def test_lifecycle_mid_window_wakeup_emits_only_highest_stage() -> None:
    tracker = CommuteLifecycleTracker()

    events = tracker.evaluate(
        state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=120),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in events] == [CommuteEventType.AMBER_WARNING]

    assert (
        tracker.evaluate(
            state=_make_state(urgency_stage=UrgencyStage.PREPARE, seconds_to_leave=300),
            is_active=True,
            commute_title="Kolya School",
            person_name="Kolya",
        )
        == []
    )


def test_lifecycle_route_switched_requires_two_consecutive_polls() -> None:
    tracker = CommuteLifecycleTracker()

    tracker.evaluate(
        state=_make_state(
            active_option="southern",
            mode="train",
            route_label="Southern",
            urgency_stage=UrgencyStage.PREPARE,
            seconds_to_leave=300,
        ),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )

    bus_state = _make_state(
        active_option="bus_322",
        mode="bus",
        route_label="322",
        vehicle_id="BUS1",
        expected_boarding_time="08:14",
        urgency_stage=UrgencyStage.PREPARE,
        seconds_to_leave=280,
    )
    first_switch_poll = tracker.evaluate(
        state=bus_state,
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert first_switch_poll == []

    second_switch_poll = tracker.evaluate(
        state=bus_state,
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in second_switch_poll] == [
        CommuteEventType.ROUTE_SWITCHED
    ]
    assert second_switch_poll[0].data["active_option"] == "bus_322"
    assert second_switch_poll[0].data["mode"] == "bus"


def test_lifecycle_route_switched_ignores_single_poll_oscillation() -> None:
    tracker = CommuteLifecycleTracker()
    train_state = _make_state(
        active_option="southern",
        urgency_stage=UrgencyStage.PREPARE,
        seconds_to_leave=300,
    )
    bus_state = _make_state(
        active_option="bus_322",
        mode="bus",
        route_label="322",
        vehicle_id="BUS1",
        urgency_stage=UrgencyStage.PREPARE,
        seconds_to_leave=290,
    )

    tracker.evaluate(state=train_state, is_active=True, commute_title="School")
    assert (
        tracker.evaluate(state=bus_state, is_active=True, commute_title="School") == []
    )
    assert (
        tracker.evaluate(state=train_state, is_active=True, commute_title="School")
        == []
    )
    assert (
        tracker.evaluate(state=bus_state, is_active=True, commute_title="School") == []
    )


def test_lifecycle_rollover_emits_and_rearms_stages_for_next_vehicle() -> None:
    tracker = CommuteLifecycleTracker()

    first = tracker.evaluate(
        state=_make_state(
            active_option="bus_322",
            mode="bus",
            route_label="322",
            vehicle_id="BUS1",
            expected_boarding_time="08:10",
            urgency_stage=UrgencyStage.LEAVE_NOW,
            seconds_to_leave=-10,
            seconds_to_board=230,
        ),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in first] == [CommuteEventType.LEAVE_NOW]

    rolled = tracker.evaluate(
        state=_make_state(
            active_option="bus_322",
            mode="bus",
            route_label="322",
            vehicle_id="BUS2",
            expected_boarding_time="08:22",
            urgency_stage=UrgencyStage.RELAXED,
            seconds_to_leave=600,
            seconds_to_board=950,
        ),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in rolled] == [CommuteEventType.ROLLOVER]
    assert rolled[0].data["expected_boarding_time"] == "08:22"

    later_leave = tracker.evaluate(
        state=_make_state(
            active_option="bus_322",
            mode="bus",
            route_label="322",
            vehicle_id="BUS2",
            expected_boarding_time="08:22",
            urgency_stage=UrgencyStage.LEAVE_NOW,
            seconds_to_leave=0,
            seconds_to_board=240,
        ),
        is_active=True,
        commute_title="Kolya School",
        person_name="Kolya",
    )
    assert [e.event_type for e in later_leave] == [CommuteEventType.LEAVE_NOW]


def test_lifecycle_disrupted_transitions_and_idle_reset() -> None:
    tracker = CommuteLifecycleTracker()
    good = LineStatus(status_label="Good Service")
    delayed = LineStatus(status_label="Severe Delays", is_delayed=True)

    assert (
        tracker.evaluate(
            state=_make_state(line_status=good, seconds_to_leave=600),
            is_active=True,
            commute_title="School",
        )
        == []
    )

    disrupted = tracker.evaluate(
        state=_make_state(line_status=delayed, seconds_to_leave=600),
        is_active=True,
        commute_title="School",
    )
    assert [e.event_type for e in disrupted] == [CommuteEventType.DISRUPTED]

    assert (
        tracker.evaluate(
            state=_make_state(line_status=delayed, seconds_to_leave=570),
            is_active=True,
            commute_title="School",
        )
        == []
    )

    assert (
        tracker.evaluate(
            state=_make_state(is_active=False),
            is_active=False,
            commute_title="School",
        )
        == []
    )

    rearmed = tracker.evaluate(
        state=_make_state(line_status=delayed, seconds_to_leave=600),
        is_active=True,
        commute_title="School",
    )
    assert [e.event_type for e in rearmed] == [CommuteEventType.DISRUPTED]


def test_lifecycle_transient_standby_blip_preserves_latches() -> None:
    tracker = CommuteLifecycleTracker()
    leave_state = _make_state(
        active_option="bus_322",
        mode="bus",
        route_label="322",
        vehicle_id="BUS1",
        urgency_stage=UrgencyStage.LEAVE_NOW,
        seconds_to_leave=0,
    )
    first = tracker.evaluate(
        state=leave_state,
        is_active=True,
        commute_title="School",
    )
    assert [e.event_type for e in first] == [CommuteEventType.LEAVE_NOW]

    blip_state = _make_state(
        active_option="none",
        urgency_stage=UrgencyStage.STANDBY,
        is_active=True,
    )
    assert (
        tracker.evaluate(state=blip_state, is_active=True, commute_title="School") == []
    )

    recovered = tracker.evaluate(
        state=leave_state,
        is_active=True,
        commute_title="School",
    )
    assert recovered == []


def test_lifecycle_route_switched_fires_from_leave_now_to_relaxed() -> None:
    tracker = CommuteLifecycleTracker()
    bus_leave_now = _make_state(
        active_option="bus_322",
        mode="bus",
        route_label="322",
        vehicle_id="BUS1",
        urgency_stage=UrgencyStage.LEAVE_NOW,
        seconds_to_leave=0,
    )
    train_relaxed = _make_state(
        active_option="southern",
        mode="train",
        route_label="Southern",
        expected_boarding_time="08:25",
        urgency_stage=UrgencyStage.RELAXED,
        seconds_to_leave=600,
    )

    tracker.evaluate(state=bus_leave_now, is_active=True, commute_title="School")
    assert (
        tracker.evaluate(state=train_relaxed, is_active=True, commute_title="School")
        == []
    )
    switched = tracker.evaluate(
        state=train_relaxed, is_active=True, commute_title="School"
    )
    assert [e.event_type for e in switched] == [CommuteEventType.ROUTE_SWITCHED]
    assert switched[0].data["active_option"] == "southern"
