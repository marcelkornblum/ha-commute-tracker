"""Domain service for corridor trajectory evaluation, filtering, and progression."""

from custom_components.commute_tracker.const import (
    BUS_DWELL_SECONDS,
    CORRIDOR_UPSTREAM_HORIZON_SECONDS,
)
from custom_components.commute_tracker.models import (
    DeparturePrediction,
    TransitMode,
)
from custom_components.commute_tracker.timeliness import (
    calculate_leave_countdown,
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
    bus_dwell_seconds: int = BUS_DWELL_SECONDS,
) -> tuple[str, float]:
    """Synthesise natural language location and SVG fractional progression ratio.

    :param departure: The active departure prediction.
    :param corridor_stops: Ordered list of corridor stop identifiers.
    :param corridor_departures: Map of stop identifier to departure predictions.
    :param stop_names: Map of stop identifier to friendly name string.
    :param boarding_stop: Optional boarding stop identifier for empty corridors.
    :param bus_dwell_seconds: Dwell threshold in seconds for stop arrival.
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
        if departure.seconds_to_arrival <= bus_dwell_seconds:
            return f"At {b_name}", 0.0
        return f"Approaching {b_name}", 0.0

    for idx, sid in enumerate(corridor_stops[:-1]):
        stop_name = stop_names.get(sid, sid)
        match_dep = next(
            (d for d in corridor_departures.get(sid, []) if d.vehicle_id == vid),
            None,
        )
        if match_dep is not None:
            if match_dep.seconds_to_arrival <= bus_dwell_seconds:
                return f"At {stop_name}", float(idx)
            prev_sid = corridor_stops[idx - 1] if idx > 0 else sid
            prev_name = stop_names.get(prev_sid, prev_sid)
            return f"Between {prev_name} and {stop_name}", float(idx) - 0.5

    target_sid = corridor_stops[-1]
    target_name = stop_names.get(target_sid, target_sid)
    target_idx = len(corridor_stops) - 1
    if departure.seconds_to_arrival <= bus_dwell_seconds:
        return f"At {target_name}", float(target_idx)

    prev_sid = corridor_stops[-2] if len(corridor_stops) > 1 else target_sid
    prev_name = stop_names.get(prev_sid, prev_sid)
    return f"Between {prev_name} and {target_name}", float(target_idx) - 0.5


def select_active_departures(
    mode: TransitMode,
    departures: list[DeparturePrediction],
    total_buffer_seconds: int,
    grace_seconds: int,
    dwell_seconds: int = BUS_DWELL_SECONDS,
) -> tuple[DeparturePrediction | None, DeparturePrediction | None]:
    """Select the lead viable departure and its subsequent follower departure.

    :param mode: Transit mode of the route.
    :param departures: Sorted candidate departure predictions.
    :param total_buffer_seconds: Combined walk and preparation threshold.
    :param grace_seconds: Grace leeway period in seconds.
    :param dwell_seconds: Stop dwell buffer threshold in seconds.
    :return: Tuple of (active_departure, follower_departure).
    """
    if not departures:
        return None, None

    if mode == TransitMode.BUS:
        for idx, dep in enumerate(departures):
            if dep.seconds_to_arrival > dwell_seconds:
                follower = departures[idx + 1] if idx + 1 < len(departures) else None
                return dep, follower
        return None, None

    for idx, dep in enumerate(departures):
        leave_in_sec = calculate_leave_countdown(
            seconds_to_arrival=dep.seconds_to_arrival,
            buffer_seconds=total_buffer_seconds,
        )
        if is_departure_reachable(
            leave_in_seconds=leave_in_sec,
            grace_seconds=grace_seconds,
        ):
            follower = departures[idx + 1] if idx + 1 < len(departures) else None
            return dep, follower

    return None, None
