from collections.abc import Sequence
from typing import cast

from custom_components.commute_tracker.const import (
    CORRIDOR_UPSTREAM_HORIZON_SECONDS,
)
from custom_components.commute_tracker.models import (
    CorridorStop,
    DeparturePrediction,
)
from custom_components.commute_tracker.timeliness import (
    is_departure_reachable,
)


def filter_approaching_departures(
    departures: list[DeparturePrediction],
    corridor_stops: list[str],
    corridor_departures: dict[str, list[DeparturePrediction]],
    boarding_stop: str | None = None,
) -> list[DeparturePrediction]:
    """Filter departures at boarding stop to those approaching along the corridor.

    Discards vehicles moving in reverse direction (where upstream corridor arrival
    is later than target arrival) or far away vehicles with no corridor presence.

    :param departures: Candidate departure predictions at the boarding stop.
    :param corridor_stops: Ordered list of corridor stop identifiers.
    :param corridor_departures: Map of stop identifier to departure predictions.
    :param boarding_stop: Boarding stop identifier (defaults to last corridor stop).
    :return: Filtered list of approaching DeparturePrediction objects.
    """
    target = boarding_stop or (corridor_stops[-1] if corridor_stops else None)
    if not corridor_stops or not target or target not in corridor_stops:
        return departures

    idx = corridor_stops.index(target)
    upstream_stops = corridor_stops[:idx]
    if not upstream_stops or not corridor_departures:
        return departures

    stop_lookup: dict[tuple[str, str], int] = {}
    for sid, deps in corridor_departures.items():
        for dep in deps:
            if dep.vehicle_id:
                stop_lookup[(sid, dep.vehicle_id)] = dep.seconds_to_arrival

    filtered: list[DeparturePrediction] = []
    for dep in departures:
        vid = dep.vehicle_id
        if not vid:
            filtered.append(dep)
            continue

        has_downstream = any(
            stop_lookup.get((sid, vid), -1) > dep.seconds_to_arrival
            for sid in upstream_stops
        )
        if has_downstream:
            continue

        has_upstream = any(
            0 <= stop_lookup.get((sid, vid), -1) < dep.seconds_to_arrival
            for sid in upstream_stops
        )
        if (
            not has_upstream
            and dep.seconds_to_arrival > CORRIDOR_UPSTREAM_HORIZON_SECONDS
        ):
            continue

        filtered.append(dep)

    return filtered


def calculate_corridor_progression(
    departure: DeparturePrediction,
    corridor_stops: list[str],
    corridor_departures: dict[str, list[DeparturePrediction]],
    stop_names: dict[str, str],
    boarding_stop: str | None = None,
    at_stop_threshold_seconds: int = 45,
) -> tuple[str, float]:
    """Synthesise natural language location and SVG fractional progression ratio.

    :param departure: The active departure prediction.
    :param corridor_stops: Ordered list of corridor stop identifiers.
    :param corridor_departures: Map of stop identifier to departure predictions.
    :param stop_names: Map of stop identifier to friendly name string.
    :param boarding_stop: Optional boarding stop identifier for empty corridors.
    :param at_stop_threshold_seconds: Threshold in seconds for stop arrival.
    :return: Tuple of (location_description, fractional_progress_index).
    """
    if departure.location:
        loc = departure.location
        if corridor_stops:
            loc_lower = loc.lower()
            matching_indices = [
                idx
                for idx, sid in enumerate(corridor_stops)
                if stop_names.get(sid, sid).lower() in loc_lower
            ]
            if matching_indices:
                max_idx = max(matching_indices)
                if "between" in loc_lower and max_idx > 0:
                    return loc, float(max_idx) - 0.5
                return loc, float(matching_indices[0])
        return loc, 0.0

    vid = departure.vehicle_id
    if not vid:
        return "", 0.0

    if not corridor_stops:
        b_name = stop_names.get(boarding_stop or "", boarding_stop or "Boarding Stop")
        if departure.seconds_to_arrival <= at_stop_threshold_seconds:
            return f"At {b_name}", 0.0
        return f"Approaching {b_name}", 0.0

    for idx, sid in enumerate(corridor_stops[:-1]):
        stop_name = stop_names.get(sid, sid)
        match_dep = next(
            (d for d in corridor_departures.get(sid, []) if d.vehicle_id == vid),
            None,
        )
        if match_dep is not None:
            if match_dep.seconds_to_arrival <= at_stop_threshold_seconds:
                return f"At {stop_name}", float(idx)
            prev_sid = corridor_stops[idx - 1] if idx > 0 else sid
            prev_name = stop_names.get(prev_sid, prev_sid)
            return f"Between {prev_name} and {stop_name}", float(idx) - 0.5

    target_sid = corridor_stops[-1]
    target_name = stop_names.get(target_sid, target_sid)
    target_idx = len(corridor_stops) - 1
    if departure.seconds_to_arrival <= at_stop_threshold_seconds:
        return f"At {target_name}", float(target_idx)

    prev_sid = corridor_stops[-2] if len(corridor_stops) > 1 else target_sid
    prev_name = stop_names.get(prev_sid, prev_sid)
    return f"Between {prev_name} and {target_name}", float(target_idx) - 0.5


def select_active_departures(
    departures: list[DeparturePrediction],
    boarding_walk_seconds: int,
    grace_seconds: int,
    total_buffer_seconds: int | None = None,
) -> tuple[DeparturePrediction | None, DeparturePrediction | None]:
    """Select the lead viable departure and its subsequent follower departure.

    A departure is skipped if it is physically unreachable within the
    walk and grace window.

    :param departures: Sorted candidate departure predictions.
    :param boarding_walk_seconds: Doorstep walking duration in seconds.
    :param grace_seconds: Grace leeway period in seconds.
    :param total_buffer_seconds: Optional total buffer threshold.
    :return: Tuple of (active_departure, follower_departure).
    """
    for idx, dep in enumerate(departures):
        if not is_departure_reachable(
            departure_seconds=dep.seconds_to_arrival,
            boarding_walk_seconds=boarding_walk_seconds,
            grace_seconds=grace_seconds,
        ):
            continue

        follower = departures[idx + 1] if idx + 1 < len(departures) else None
        return dep, follower

    return None, None


def slice_upstream_corridor(
    sequences: Sequence[Sequence[CorridorStop]] | Sequence[CorridorStop],
    boarding_stop: str,
    target_time_window_seconds: int | None = None,
    seconds_per_stop: int = 120,
) -> list[CorridorStop]:
    """Slice and order upstream corridor stops leading to the target boarding stop.

    Searches normalised branches of stops for the target boarding stop (matching
    by id or name, case-insensitively). Returns an ordered list of upstream stops
    ending at the target boarding stop, optionally constrained by travel time window.

    :param sequences: Branch sequences containing CorridorStop objects.
    :param boarding_stop: Boarding stop identifier or name.
    :param target_time_window_seconds: Optional duration window for corridor stops.
    :param seconds_per_stop: Average seconds per stop for window calculation.
    :return: List of CorridorStop objects with is_target flagged on the final stop.
    """
    if not sequences or not boarding_stop:
        return []

    target_query = boarding_stop.strip().lower()

    first_elem = sequences[0]
    branches: list[Sequence[CorridorStop]]
    if isinstance(first_elem, CorridorStop):
        branches = [cast(Sequence[CorridorStop], sequences)]
    else:
        branches = list(cast(Sequence[Sequence[CorridorStop]], sequences))

    matching_branch: Sequence[CorridorStop] | None = None
    target_index: int = -1

    for branch in branches:
        for idx, st in enumerate(branch):
            sid = st.id.strip().lower()
            sname = st.name.strip().lower()
            if sid == target_query or sname == target_query or target_query in sname:
                matching_branch = branch
                target_index = idx
                break
        if matching_branch is not None:
            break

    if matching_branch is None or target_index < 0:
        return []

    candidate_stops = matching_branch[: target_index + 1]

    if target_time_window_seconds is not None:
        has_scheduled_lead = any(
            s.scheduled_lead_seconds is not None for s in candidate_stops[:-1]
        )
        if has_scheduled_lead:
            candidate_stops = [
                s
                for s in candidate_stops
                if s.scheduled_lead_seconds is None
                or s.scheduled_lead_seconds <= target_time_window_seconds
            ]
        elif seconds_per_stop > 0:
            max_stops = max(1, target_time_window_seconds // seconds_per_stop)
            if len(candidate_stops) > max_stops:
                candidate_stops = candidate_stops[-max_stops:]

    result: list[CorridorStop] = []
    last_idx = len(candidate_stops) - 1
    for idx, st in enumerate(candidate_stops):
        result.append(
            CorridorStop(
                id=st.id,
                name=st.name,
                is_target=(idx == last_idx),
                scheduled_lead_seconds=st.scheduled_lead_seconds,
            )
        )
    return result


discover_upstream_corridor = slice_upstream_corridor
