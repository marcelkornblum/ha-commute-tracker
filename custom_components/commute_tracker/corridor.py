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


def _resolve_stop_name(sid: str, stop_names: dict[str, str]) -> str:
    """Return non-empty friendly stop name or fall back to stop identifier."""
    name = stop_names.get(sid)
    if name and name.strip():
        return name.strip()
    return sid


def calculate_corridor_progression(
    departure: DeparturePrediction,
    corridor_stops: list[str],
    corridor_departures: dict[str, list[DeparturePrediction]],
    stop_names: dict[str, str],
    boarding_stop: str | None = None,
    at_stop_threshold_seconds: int = 45,
    seconds_per_segment: int = 250,
) -> tuple[str, float]:
    """Synthesise natural language location and SVG fractional progression ratio.

    :param departure: The active departure prediction.
    :param corridor_stops: Ordered list of corridor stop identifiers.
    :param corridor_departures: Map of stop identifier to departure predictions.
    :param stop_names: Map of stop identifier to friendly name string.
    :param boarding_stop: Optional boarding stop identifier for empty corridors.
    :param at_stop_threshold_seconds: Threshold in seconds for stop arrival.
    :param seconds_per_segment: Assumed seconds per corridor segment for interpolation.
    :return: Tuple of (location_description, fractional_progress_index).
    """
    if departure.location:
        loc = departure.location
        if corridor_stops:
            loc_lower = loc.lower()
            matching_indices = [
                idx
                for idx, sid in enumerate(corridor_stops)
                if _resolve_stop_name(sid, stop_names).lower() in loc_lower
            ]
            has_live_keyword = any(
                kw in loc_lower
                for kw in ("at ", "approaching", "arriving", "left ", "between")
            )
            is_static_target_only = (
                len(corridor_stops) > 1
                and matching_indices == [len(corridor_stops) - 1]
                and departure.seconds_to_arrival > at_stop_threshold_seconds
                and not has_live_keyword
            )
            if not is_static_target_only:
                if matching_indices:
                    max_idx = max(matching_indices)
                    if "between" in loc_lower:
                        return loc, max(0.0, float(max_idx) - 0.5)
                    return loc, float(matching_indices[0])
                return loc, 0.0
        else:
            return loc, 0.0

    vid = departure.vehicle_id
    if not corridor_stops:
        if not vid and not boarding_stop:
            return "", 0.0
        b_id = boarding_stop or ""
        b_name = _resolve_stop_name(b_id, stop_names) if b_id else "Boarding Stop"
        if departure.seconds_to_arrival <= at_stop_threshold_seconds:
            return f"At {b_name}", 0.0
        return f"Approaching {b_name}", 0.0

    target_sid = corridor_stops[-1]
    target_name = _resolve_stop_name(target_sid, stop_names)
    target_idx = len(corridor_stops) - 1
    if departure.seconds_to_arrival <= at_stop_threshold_seconds:
        return f"At {target_name}", float(target_idx)

    if len(corridor_stops) == 1:
        return f"Approaching {target_name}", 0.0

    if not vid:
        num_segments = len(corridor_stops) - 1
        total_lead_seconds = num_segments * seconds_per_segment
        origin_name = _resolve_stop_name(corridor_stops[0], stop_names)
        if (
            total_lead_seconds <= 0
            or departure.seconds_to_arrival >= total_lead_seconds
        ):
            return f"Scheduled from {origin_name}", 0.0

        raw_progress = num_segments * (
            1.0 - departure.seconds_to_arrival / total_lead_seconds
        )
        progress = round(max(0.0, min(float(num_segments), raw_progress)), 2)
        nearest_idx = int(round(raw_progress))
        if (
            0 <= nearest_idx < num_segments
            and abs(
                departure.seconds_to_arrival
                - (num_segments - nearest_idx) * seconds_per_segment
            )
            <= at_stop_threshold_seconds
        ):
            stop_name = _resolve_stop_name(corridor_stops[nearest_idx], stop_names)
            return f"At {stop_name}", progress

        seg_idx = min(num_segments - 1, max(0, int(raw_progress)))
        prev_name = _resolve_stop_name(corridor_stops[seg_idx], stop_names)
        next_name = _resolve_stop_name(corridor_stops[seg_idx + 1], stop_names)
        return f"Between {prev_name} and {next_name}", progress

    valid_deps: dict[int, DeparturePrediction] = {}
    upper_bound = departure.seconds_to_arrival
    for idx in range(target_idx - 1, -1, -1):
        sid = corridor_stops[idx]
        candidates = [
            d
            for d in corridor_departures.get(sid, [])
            if d.vehicle_id == vid and 0 <= d.seconds_to_arrival < upper_bound
        ]
        if candidates:
            match_dep = min(candidates, key=lambda d: d.seconds_to_arrival)
            valid_deps[idx] = match_dep
            upper_bound = match_dep.seconds_to_arrival

    approaching_indices = [
        idx
        for idx, d in valid_deps.items()
        if d.seconds_to_arrival > at_stop_threshold_seconds
    ]
    if approaching_indices:
        first_approaching_idx = min(approaching_indices)
        if (first_approaching_idx - 1) in valid_deps:
            at_idx = first_approaching_idx - 1
            at_name = _resolve_stop_name(corridor_stops[at_idx], stop_names)
            return f"At {at_name}", float(at_idx)
        if first_approaching_idx == 0:
            origin_name = _resolve_stop_name(corridor_stops[0], stop_names)
            return f"Scheduled at {origin_name}", 0.0
        prev_name = _resolve_stop_name(
            corridor_stops[first_approaching_idx - 1], stop_names
        )
        stop_name = _resolve_stop_name(
            corridor_stops[first_approaching_idx], stop_names
        )
        return f"Between {prev_name} and {stop_name}", float(
            first_approaching_idx
        ) - 0.5

    if valid_deps:
        last_at_idx = max(valid_deps.keys())
        at_name = _resolve_stop_name(corridor_stops[last_at_idx], stop_names)
        return f"At {at_name}", float(last_at_idx)

    prev_sid = corridor_stops[-2]
    prev_name = _resolve_stop_name(prev_sid, stop_names)
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


def _stop_matches_query(st: CorridorStop, query: str) -> bool:
    """Check whether a CorridorStop matches a stop ID or name query."""
    sid = st.id.strip().lower()
    sname = st.name.strip().lower()
    return sid == query or sname == query or query in sname


def find_target_branch(
    sequences: Sequence[Sequence[CorridorStop]] | Sequence[CorridorStop],
    target_query: str,
    alighting_query: str | None = None,
) -> tuple[Sequence[CorridorStop], int] | None:
    """Find branch sequence and stop index containing the target boarding stop.

    :param sequences: Branch sequences containing CorridorStop objects.
    :param target_query: Boarding stop identifier or friendly name.
    :param alighting_query: Optional alighting stop identifier or friendly name.
    :return: Tuple of (matching_branch, target_index), or None if not found.
    """
    if not sequences or not target_query:
        return None

    query = target_query.strip().lower()
    alight_q = alighting_query.strip().lower() if alighting_query else ""
    first_elem = sequences[0]
    branches: list[Sequence[CorridorStop]]
    if isinstance(first_elem, CorridorStop):
        branches = [cast(Sequence[CorridorStop], sequences)]
    else:
        branches = list(cast(Sequence[Sequence[CorridorStop]], sequences))

    candidates: list[tuple[int, Sequence[CorridorStop], int]] = []
    for branch in branches:
        for idx, st in enumerate(branch):
            if _stop_matches_query(st, query):
                if alight_q:
                    has_downstream_alight = any(
                        _stop_matches_query(s, alight_q) for s in branch[idx + 1 :]
                    )
                    has_upstream_alight = any(
                        _stop_matches_query(s, alight_q) for s in branch[:idx]
                    )
                    if has_downstream_alight:
                        rank = 0 if idx > 0 else 1
                    elif has_upstream_alight:
                        rank = 4
                    else:
                        rank = 2 if idx > 0 else 3
                else:
                    rank = 0 if idx > 0 else 1
                candidates.append((rank, branch, idx))

    if not candidates:
        return None

    _, best_branch, best_idx = min(candidates, key=lambda item: item[0])
    return best_branch, best_idx


def slice_upstream_corridor(
    sequences: Sequence[Sequence[CorridorStop]] | Sequence[CorridorStop],
    boarding_stop: str,
    target_time_window_seconds: int | None = None,
    seconds_per_stop: int = 120,
    alighting_stop: str | None = None,
) -> list[CorridorStop]:
    """Slice and order upstream corridor stops leading to the target boarding stop.

    Searches normalised branches of stops for the target boarding stop (matching
    by id or name, case-insensitively). Returns an ordered list of upstream stops
    ending at the target boarding stop, optionally constrained by travel time window.

    :param sequences: Branch sequences containing CorridorStop objects.
    :param boarding_stop: Boarding stop identifier or name.
    :param target_time_window_seconds: Optional duration window for corridor stops.
    :param seconds_per_stop: Average seconds per stop for window calculation.
    :param alighting_stop: Optional alighting stop identifier or name for direction.
    :return: List of CorridorStop objects with is_target flagged on the final stop.
    """
    if not sequences or not boarding_stop:
        return []

    match = find_target_branch(
        sequences=sequences,
        target_query=boarding_stop,
        alighting_query=alighting_stop,
    )
    if match is None:
        return []

    matching_branch, target_index = match
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
