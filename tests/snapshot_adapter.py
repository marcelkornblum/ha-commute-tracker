"""Test harness fixture adaptor for offline snapshot evaluation."""

import zoneinfo
from datetime import datetime, timezone
from typing import Any, cast

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import TransitProvider
from custom_components.commute_tracker.providers.tfl import (
    TfLTransitProvider,
    clean_stop_name,
)

LONDON_TIMEZONE = zoneinfo.ZoneInfo("Europe/London")


def parse_datetime(iso_str: str) -> datetime:
    """Parse ISO datetime string into UTC datetime object."""
    clean_str = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LONDON_TIMEZONE)
    return dt.astimezone(timezone.utc)


def parse_countdown_adjustment(adjustment_str: str | None) -> int:
    """Parse countdown server adjustment ISO delta into integer seconds."""
    if not adjustment_str:
        return 0
    try:
        clean_parts = adjustment_str.lstrip("-").split(":")
        seconds_val = float(clean_parts[-1])
        adjusted_int = int(round(seconds_val))
        if adjustment_str.startswith("-"):
            return -adjusted_int
        return adjusted_int
    except ValueError, IndexError:
        return 0


def extract_stop_arrivals(
    mode_data: dict[str, Any],
    target_naptan: str,
) -> list[dict[str, Any]]:
    """Extract raw arrival items for target NaPTAN from discrete or line arrivals."""
    discrete: dict[str, Any] = mode_data.get("discrete_stop_arrivals", {})
    for arrivals_list in discrete.values():
        if isinstance(arrivals_list, list) and any(
            item.get("naptanId") == target_naptan for item in arrivals_list
        ):
            return cast(list[dict[str, Any]], arrivals_list)
    line_arrivals: list[dict[str, Any]] = mode_data.get("line_arrivals", [])
    return [item for item in line_arrivals if item.get("naptanId") == target_naptan]


def build_tfl_stop_names_map(mode_data: dict[str, Any]) -> dict[str, str]:
    """Extract cleaned station names from discrete and line arrivals."""
    names: dict[str, str] = {}
    discrete: dict[str, Any] = mode_data.get("discrete_stop_arrivals", {})
    for arr_list in discrete.values():
        if isinstance(arr_list, list):
            for item in arr_list:
                sid = item.get("naptanId")
                name = item.get("stationName")
                if sid and name and sid not in names:
                    names[sid] = clean_stop_name(raw_name=name)
    line_arrivals: list[dict[str, Any]] = mode_data.get("line_arrivals", [])
    for item in line_arrivals:
        sid = item.get("naptanId")
        name = item.get("stationName")
        if sid and name and sid not in names:
            names[sid] = clean_stop_name(raw_name=name)
    return names


def extract_snapshot_telemetry(
    provider: TransitProvider,
    route: RouteConfig,
    snapshot: dict[str, Any],
) -> RouteTelemetry:
    """Extract normalised telemetry from offline fixture snapshot for testing."""
    if isinstance(provider, TfLTransitProvider):
        return _extract_tfl_snapshot_telemetry(
            provider=provider, route=route, snapshot=snapshot
        )

    # Generic / template fallback for test fixtures
    if not snapshot:
        sample_departure = DeparturePrediction(
            vehicle_id="TEMPLATE_01",
            destination="Terminus Station",
            expected_time="2026-09-14T15:00:00Z",
            seconds_to_arrival=300,
            platform_or_bay="1",
            is_realtime=True,
        )
        return provider.build_route_telemetry(
            route=route,
            departures=[sample_departure],
            line_status=LineStatus(
                status_label="Good Service",
                status_color="#00A859",
                status_icon="mdi:check-circle",
            ),
            active_vehicle_id="TEMPLATE_01",
        )

    mode_key = route.mode.value.lower()
    mode_data = snapshot.get(mode_key, {})
    raw_arrivals = mode_data.get("arrivals", [])
    raw_status = mode_data.get("line_status", {})

    target_stop = route.boarding_stop or ""
    departures = provider.adapt_departures(
        raw_payload=raw_arrivals,
        target_stop=target_stop,
        line_id=route.line,
    )
    corridor_departures: dict[str, list[DeparturePrediction]] = {}
    for sid in route.corridor_stops:
        corridor_departures[sid] = provider.adapt_departures(
            raw_payload=raw_arrivals,
            target_stop=sid,
            line_id=route.line,
        )
    stop_names = provider.adapt_stop_names(raw_payload=raw_arrivals)
    line_status = provider.adapt_line_status(raw_payload=raw_status, mode=route.mode)

    return provider.build_route_telemetry(
        route=route,
        departures=departures,
        line_status=line_status,
        corridor_departures=corridor_departures,
        stop_names=stop_names,
    )


def _extract_tfl_snapshot_telemetry(
    provider: TfLTransitProvider,
    route: RouteConfig,
    snapshot: dict[str, Any],
) -> RouteTelemetry:
    """Extract TfL snapshot telemetry using TfL transit provider adaptors."""
    ref_timestamp: str = snapshot.get("timestamp", "")

    if route.mode == TransitMode.BUS:
        bus_data = snapshot.get("bus", {})
        bus_line_arrivals = bus_data.get("line_arrivals", [])
        stop_names = build_tfl_stop_names_map(mode_data=bus_data)
        target_naptan = route.boarding_stop or ""
        raw_arrivals = (
            extract_stop_arrivals(mode_data=bus_data, target_naptan=target_naptan)
            if target_naptan
            else []
        )

        departures = provider.adapt_departures(
            raw_payload=raw_arrivals,
            target_stop=target_naptan,
            line_id=route.line,
        )

        for idx in range(1, len(departures)):
            dep = departures[idx]
            if not dep.vehicle_id:
                continue
            line_match = next(
                (
                    item
                    for item in bus_line_arrivals
                    if item.get("vehicleId") == dep.vehicle_id
                    and item.get("naptanId") == target_naptan
                ),
                None,
            )
            if line_match is not None:
                tts = int(line_match.get("timeToStation", 0))
                adj_str = line_match.get("timing", {}).get("countdownServerAdjustment")
                adj_sec = parse_countdown_adjustment(adjustment_str=adj_str)
                departures[idx] = DeparturePrediction(
                    vehicle_id=dep.vehicle_id,
                    destination=dep.destination,
                    expected_time=dep.expected_time,
                    seconds_to_arrival=tts + adj_sec,
                    platform_or_bay=dep.platform_or_bay,
                    is_realtime=dep.is_realtime,
                    location=dep.location,
                )

        corridor_departures: dict[str, list[DeparturePrediction]] = {}
        for sid in route.corridor_stops:
            sid_arrivals = extract_stop_arrivals(mode_data=bus_data, target_naptan=sid)
            corridor_departures[sid] = provider.adapt_departures(
                raw_payload=sid_arrivals,
                target_stop=sid,
                line_id=route.line,
            )

        raw_status = bus_data.get("line_status", [])
        line_status = provider.adapt_line_status(
            raw_payload=raw_status, mode=route.mode
        )

        return provider.build_route_telemetry(
            route=route,
            departures=departures,
            line_status=line_status,
            corridor_departures=corridor_departures,
            stop_names=stop_names,
        )

    if route.mode == TransitMode.TRAIN:
        train_data = snapshot.get("train", {})
        journey_payload = train_data.get("journey_results") or snapshot.get(
            "train_journey_results", {}
        )
        departures = provider.adapt_journey(
            raw_payload=journey_payload,
            origin=route.boarding_stop or "",
            destination=route.alighting_stop or "",
            reference_time_iso=ref_timestamp,
        )
        raw_status = train_data.get("line_status", [])
        line_status = provider.adapt_line_status(
            raw_payload=raw_status, mode=route.mode
        )

        stop_names = {}
        if route.boarding_stop:
            stop_names[route.boarding_stop] = provider.clean_stop_name(
                raw_name=route.boarding_stop
            )
        if route.alighting_stop:
            stop_names[route.alighting_stop] = provider.clean_stop_name(
                raw_name=route.alighting_stop
            )

        return provider.build_route_telemetry(
            route=route,
            departures=departures,
            line_status=line_status,
            corridor_departures={},
            stop_names=stop_names,
            active_vehicle_id=None,
        )

    if route.mode == TransitMode.TUBE:
        tube_data = snapshot.get("tube", {})
        stop_names = build_tfl_stop_names_map(mode_data=tube_data)
        target_naptan = route.boarding_stop or ""
        raw_arrivals = (
            extract_stop_arrivals(mode_data=tube_data, target_naptan=target_naptan)
            if target_naptan
            else []
        )

        departures = provider.adapt_departures(
            raw_payload=raw_arrivals,
            target_stop=target_naptan,
            line_id=route.line,
        )

        corridor_departures = {}
        for sid in route.corridor_stops:
            sid_arrivals = extract_stop_arrivals(mode_data=tube_data, target_naptan=sid)
            corridor_departures[sid] = provider.adapt_departures(
                raw_payload=sid_arrivals,
                target_stop=sid,
                line_id=route.line,
            )

        raw_status = tube_data.get("line_status", [])
        line_status = provider.adapt_line_status(
            raw_payload=raw_status, mode=route.mode
        )

        return provider.build_route_telemetry(
            route=route,
            departures=departures,
            line_status=line_status,
            corridor_departures=corridor_departures,
            stop_names=stop_names,
        )

    raise NotImplementedError(
        f"Mode {route.mode} not supported by TfL snapshot adapter"
    )
