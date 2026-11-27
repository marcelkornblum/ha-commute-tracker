"""Pure-Python unit tests for LLM-friendly commute status payloads and summaries."""

from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    LineStatus,
    PillBadge,
    RouteConfig,
    TransitMode,
    UrgencyStage,
)
from custom_components.commute_tracker.status import (
    build_commute_status,
    format_commute_summary,
)


def _sample_config() -> CommuteConfig:
    return CommuteConfig(
        commute_id="kolya_school",
        commute_title="Kolya School",
        person_name="Kolya",
        destination="School",
        target_destination_time="08:50",
        routes=[
            RouteConfig(
                route_id="southern",
                mode=TransitMode.TRAIN,
                line="southern",
                destination="Victoria",
            ),
            RouteConfig(
                route_id="bus_315",
                mode=TransitMode.BUS,
                line="315",
                destination="Balham",
            ),
        ],
    )


def _active_state(
    *,
    urgency_stage: UrgencyStage = UrgencyStage.PREPARE,
    seconds_to_leave: int = 180,
    corridor_location: str = "between Forest Hill and Sydenham",
    corridor_progress: float = 0.65,
) -> CommuteState:
    return CommuteState(
        commute_id="kolya_school",
        master_rollup=MasterRollupState(
            active_option="southern",
            urgency_stage=urgency_stage,
            mode="train",
            leave_by_time="08:16",
            expected_boarding_time="08:32",
            expected_destination_time="08:45",
            seconds_to_leave=seconds_to_leave,
            seconds_to_board=seconds_to_leave + 960,
            route_label="Southern",
            destination="Victoria",
            will_arrive_on_time=True,
            timeliness="early",
            line_status=LineStatus(status_label="Good Service"),
            next_summary="Next at 08:47 (in 15m)",
            pill_badge=PillBadge(
                label="👟 Leave in 3m",
                color="#FF9800",
                bg="rgba(255, 152, 0, 0.15)",
                border="#FF9800",
            ),
            is_active=True,
        ),
        child_routes={
            "southern": ChildRouteState(
                route_id="southern",
                mode="train",
                urgency_stage=urgency_stage,
                leave_by_time="08:16",
                expected_boarding_time="08:32",
                expected_destination_time="08:45",
                seconds_to_leave=seconds_to_leave,
                seconds_to_board=seconds_to_leave + 960,
                will_arrive_on_time=True,
                timeliness="early",
                corridor_location=corridor_location,
                corridor_progress=corridor_progress,
                next_summary="Next at 08:47 (in 15m)",
                line_status=LineStatus(status_label="Good Service"),
                route_label="Southern",
                destination="Victoria",
                pill_badge=PillBadge(
                    label="👟 Leave in 3m",
                    color="#FF9800",
                    bg="rgba(255, 152, 0, 0.15)",
                    border="#FF9800",
                ),
                is_active=True,
            ),
            "bus_315": ChildRouteState(
                route_id="bus_315",
                mode="bus",
                urgency_stage=UrgencyStage.RELAXED,
                leave_by_time="08:20",
                expected_boarding_time="08:26",
                expected_destination_time="08:49",
                seconds_to_leave=420,
                seconds_to_board=780,
                will_arrive_on_time=True,
                timeliness="on_time",
                corridor_location="at Norwood Road",
                corridor_progress=0.4,
                next_summary="Next at 08:38 (in 12m)",
                line_status=LineStatus(status_label="Good Service"),
                route_label="315",
                destination="Balham",
                pill_badge=PillBadge(
                    label="Leave in 7m",
                    color="#4CAF50",
                    bg="rgba(76, 175, 80, 0.15)",
                    border="#4CAF50",
                ),
                is_active=True,
            ),
        },
    )


def test_build_commute_status_active_includes_recommended_routes_and_summary() -> None:
    payload = build_commute_status(
        state=_active_state(),
        config=_sample_config(),
        is_active=True,
        person_name="Kolya",
    )

    assert payload["commute_id"] == "kolya_school"
    assert payload["commute_title"] == "Kolya School"
    assert payload["person_name"] == "Kolya"
    assert payload["target_destination_time"] == "08:50"
    assert payload["is_active"] is True
    assert payload["is_relevant"] is True

    recommended = payload["recommended"]
    assert recommended is not None
    assert recommended["active_option"] == "southern"
    assert recommended["route_label"] == "Southern"
    assert recommended["mode"] == "train"
    assert recommended["urgency_stage"] == "prepare"
    assert recommended["pill_label"] == "👟 Leave in 3m"
    assert recommended["leave_by_time"] == "08:16"
    assert recommended["seconds_to_leave"] == 180
    assert recommended["expected_boarding_time"] == "08:32"
    assert recommended["expected_destination_time"] == "08:45"
    assert recommended["will_arrive_on_time"] is True
    assert recommended["timeliness"] == "early"
    assert recommended["line_status_label"] == "Good Service"
    assert recommended["next_summary"] == "Next at 08:47 (in 15m)"

    assert len(payload["routes"]) == 2
    assert payload["routes"][0]["route_id"] == "southern"
    assert payload["routes"][0]["corridor_location"] == (
        "between Forest Hill and Sydenham"
    )
    assert payload["routes"][0]["corridor_progress"] == 0.65
    assert payload["routes"][0]["destination"] == "Victoria"
    assert payload["routes"][1]["route_id"] == "bus_315"

    assert payload["summary"] == (
        "Leave by 08:16 (in 3 minutes) for the 08:32 Southern train to Victoria, "
        "currently between Forest Hill and Sydenham; arrives at School at 08:45."
    )


def test_build_commute_status_idle_returns_idle_summary() -> None:
    idle_state = CommuteState(
        commute_id="kolya_school",
        master_rollup=MasterRollupState(
            active_option="none",
            urgency_stage=UrgencyStage.STANDBY,
            is_active=False,
        ),
        child_routes={},
    )
    payload = build_commute_status(
        state=idle_state,
        config=_sample_config(),
        is_active=False,
        person_name="Kolya",
    )

    assert payload["is_active"] is False
    assert payload["is_relevant"] is False
    assert payload["recommended"] is None
    assert payload["summary"] == (
        "Commute tracking is currently idle outside the active window."
    )


def test_build_commute_status_live_override_marks_relevant_when_idle() -> None:
    payload = build_commute_status(
        state=_active_state(urgency_stage=UrgencyStage.LEAVE_NOW, seconds_to_leave=-15),
        config=_sample_config(),
        is_active=False,
        person_name="Kolya",
        live_override=True,
    )

    assert payload["is_active"] is False
    assert payload["is_relevant"] is True
    assert payload["recommended"] is not None
    assert payload["summary"].startswith("Leave now for the 08:32 Southern train")


def test_format_commute_summary_handles_singular_minute_and_no_corridor() -> None:
    summary = format_commute_summary(
        is_relevant=True,
        active_option="bus_315",
        route_label="315",
        mode="bus",
        leave_by_time="08:20",
        seconds_to_leave=60,
        expected_boarding_time="08:26",
        expected_destination_time="08:49",
        destination="Balham",
        commute_destination=None,
        corridor_location="",
    )

    assert summary == (
        "Leave by 08:20 (in 1 minute) for the 08:26 315 bus to Balham; "
        "arrives at 08:49."
    )
