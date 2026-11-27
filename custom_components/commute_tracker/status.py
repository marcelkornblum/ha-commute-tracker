"""Pure-Python LLM-friendly commute status payloads and natural-language summaries."""

from typing import Any

from custom_components.commute_tracker.const import DEFAULT_LINE_STATUS
from custom_components.commute_tracker.engine import (
    ChildRouteState,
    CommuteState,
)
from custom_components.commute_tracker.models import CommuteConfig


def _format_leave_lead(leave_by_time: str, seconds_to_leave: int) -> str:
    """Format doorstep departure lead-in phrase for natural-language summaries."""
    if seconds_to_leave <= 0:
        return "Leave now"
    minutes = max(1, round(seconds_to_leave / 60))
    unit = "minute" if minutes == 1 else "minutes"
    if leave_by_time:
        return f"Leave by {leave_by_time} (in {minutes} {unit})"
    return f"Leave in {minutes} {unit}"


def _format_service_phrase(
    expected_boarding_time: str,
    route_label: str,
    mode: str,
    destination: str,
) -> str:
    """Format boarding time, line, mode, and optional destination phrase."""
    label = route_label.strip()
    mode_clean = mode.strip()
    if label and mode_clean and not label.lower().endswith(mode_clean.lower()):
        service = f"{label} {mode_clean}"
    else:
        service = label or mode_clean or "service"

    prefix = (
        f"the {expected_boarding_time} {service}"
        if expected_boarding_time
        else f"the {service}"
    )
    dest = destination.strip()
    if dest:
        return f"{prefix} to {dest}"
    return prefix


def format_commute_summary(
    *,
    is_relevant: bool,
    active_option: str,
    route_label: str,
    mode: str,
    leave_by_time: str,
    seconds_to_leave: int,
    expected_boarding_time: str,
    expected_destination_time: str,
    destination: str,
    commute_destination: str | None,
    corridor_location: str,
) -> str:
    """Build a concise natural-language summary sentence for Assist and LLMs."""
    if not is_relevant:
        return "Commute tracking is currently idle outside the active window."
    if active_option == "none":
        return "No upcoming departures are currently available."

    leave_lead = _format_leave_lead(
        leave_by_time=leave_by_time,
        seconds_to_leave=seconds_to_leave,
    )
    service_phrase = _format_service_phrase(
        expected_boarding_time=expected_boarding_time,
        route_label=route_label,
        mode=mode,
        destination=destination,
    )
    sentence = f"{leave_lead} for {service_phrase}"

    corridor = corridor_location.strip()
    if corridor:
        sentence = f"{sentence}, currently {corridor}"

    if expected_destination_time:
        dest_name = (commute_destination or "").strip()
        if dest_name:
            sentence = (
                f"{sentence}; arrives at {dest_name} at {expected_destination_time}"
            )
        else:
            sentence = f"{sentence}; arrives at {expected_destination_time}"

    return f"{sentence}."


def _serialise_child_route(child: ChildRouteState) -> dict[str, Any]:
    """Serialise a single child route snapshot into an LLM-friendly dictionary."""
    return {
        "route_id": child.route_id,
        "route_label": child.route_label,
        "mode": child.mode,
        "urgency_stage": child.urgency_stage.value,
        "pill_label": child.pill_badge.label if child.pill_badge is not None else None,
        "leave_by_time": child.leave_by_time,
        "seconds_to_leave": child.seconds_to_leave,
        "expected_boarding_time": child.expected_boarding_time,
        "expected_destination_time": child.expected_destination_time,
        "will_arrive_on_time": child.will_arrive_on_time,
        "timeliness": child.timeliness,
        "line_status_label": (
            child.line_status.status_label
            if child.line_status is not None
            else DEFAULT_LINE_STATUS
        ),
        "next_summary": child.next_summary,
        "corridor_location": child.corridor_location,
        "corridor_progress": child.corridor_progress,
        "destination": child.destination,
    }


def build_commute_status(
    *,
    state: CommuteState,
    config: CommuteConfig,
    is_active: bool,
    person_name: str | None = None,
    live_override: bool = False,
) -> dict[str, Any]:
    """Build a structured, LLM-friendly status payload for a commute."""
    master = state.master_rollup
    is_relevant = (is_active or live_override) and master.is_active
    commute_title = config.commute_title or config.commute_id

    active_child = state.child_routes.get(master.active_option)
    corridor_location = (
        active_child.corridor_location if active_child is not None else ""
    )
    corridor_progress = (
        active_child.corridor_progress if active_child is not None else 0.0
    )

    recommended: dict[str, Any] | None = None
    if is_relevant and master.active_option != "none":
        recommended = {
            "active_option": master.active_option,
            "route_label": master.route_label,
            "mode": master.mode,
            "urgency_stage": master.urgency_stage.value,
            "pill_label": (
                master.pill_badge.label if master.pill_badge is not None else None
            ),
            "leave_by_time": master.leave_by_time,
            "seconds_to_leave": master.seconds_to_leave,
            "expected_boarding_time": master.expected_boarding_time,
            "expected_destination_time": master.expected_destination_time,
            "will_arrive_on_time": master.will_arrive_on_time,
            "timeliness": master.timeliness,
            "line_status_label": (
                master.line_status.status_label
                if master.line_status is not None
                else DEFAULT_LINE_STATUS
            ),
            "next_summary": master.next_summary,
            "destination": master.destination,
            "corridor_location": corridor_location,
            "corridor_progress": corridor_progress,
        }

    routes = [
        _serialise_child_route(child=child) for child in state.child_routes.values()
    ]
    summary = format_commute_summary(
        is_relevant=is_relevant,
        active_option=master.active_option,
        route_label=master.route_label,
        mode=master.mode,
        leave_by_time=master.leave_by_time,
        seconds_to_leave=master.seconds_to_leave,
        expected_boarding_time=master.expected_boarding_time,
        expected_destination_time=master.expected_destination_time,
        destination=master.destination,
        commute_destination=config.destination,
        corridor_location=corridor_location,
    )

    return {
        "commute_id": config.commute_id,
        "commute_title": commute_title,
        "person_name": person_name,
        "target_destination_time": config.target_destination_time,
        "destination": config.destination or master.destination or None,
        "is_active": is_active,
        "is_relevant": is_relevant,
        "recommended": recommended,
        "routes": routes,
        "summary": summary,
    }
