"""Transport for London (TfL) transit provider implementation."""

import zoneinfo
from datetime import datetime, timezone
from typing import Any, ClassVar, cast

import aiohttp

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import TransitProvider

TFL_API_BASE_URL = "https://api.tfl.gov.uk"
LONDON_TIMEZONE = zoneinfo.ZoneInfo("Europe/London")

TFL_CANCELLED_STATUSES = {
    "Suspended",
    "Planned Closure",
    "Service Closed",
}

TFL_DELAYED_STATUSES = {
    "Severe Delays",
    "Part Suspended",
    "Part Closure",
    "Reduced Service",
    "Minor Delays",
}

SEVERITY_MAPPINGS: dict[str, tuple[str, str]] = {
    "Good Service": ("#00A859", "mdi:check-circle"),
    "Minor Delays": ("#FFAE42", "mdi:alert-circle"),
    "Part Suspended": ("#E65100", "mdi:alert-octagon"),
    "Severe Delays": ("#DC241F", "mdi:alert-octagon"),
    "Suspended": ("#DC241F", "mdi:close-octagon"),
    "Part Closure": ("#E65100", "mdi:alert-octagon"),
    "Planned Closure": ("#757575", "mdi:close-circle"),
    "Special Service": ("#1976D2", "mdi:information"),
    "Reduced Service": ("#FFAE42", "mdi:alert-circle"),
    "Service Closed": ("#212121", "mdi:power-off"),
    "Unknown": ("#757575", "mdi:help-circle"),
}


def clean_stop_name(raw_name: str) -> str:
    """Normalise verbose TfL station names into clean concise display labels.

    :param raw_name: Raw station name string from TfL API.
    :return: Cleaned concise stop name label.
    """
    name = raw_name
    for suffix in (
        " Underground Station",
        " Rail Station",
        " Station",
        " Stn  / Parliament Square",
        " Stn  / Trafalgar Square",
        " Parade",
    ):
        if suffix in name:
            name = name.replace(suffix, "")
    cleaned = name.strip()
    if cleaned == "Charing Cross" or "Trafalgar Square" in cleaned:
        return "Trafalgar Sq"
    return cleaned


def _parse_datetime(iso_str: str) -> datetime:
    """Parse ISO datetime string into UTC datetime object."""
    clean_str = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LONDON_TIMEZONE)
    return dt.astimezone(timezone.utc)


def _parse_countdown_adjustment(adjustment_str: str | None) -> int:
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


def _extract_stop_arrivals(
    mode_data: dict[str, Any],
    target_naptan: str,
) -> list[dict[str, Any]]:
    """Extract raw arrival items for target NaPTAN from discrete or line arrivals.

    :param mode_data: Mode-specific snapshot dictionary.
    :param target_naptan: Stop NaPTAN identifier to match.
    :return: List of raw arrival dictionaries.
    """
    discrete: dict[str, Any] = mode_data.get("discrete_stop_arrivals", {})
    for arrivals_list in discrete.values():
        if isinstance(arrivals_list, list) and any(
            item.get("naptanId") == target_naptan for item in arrivals_list
        ):
            return cast(list[dict[str, Any]], arrivals_list)
    line_arrivals: list[dict[str, Any]] = mode_data.get("line_arrivals", [])
    return [item for item in line_arrivals if item.get("naptanId") == target_naptan]


def _build_tfl_stop_names_map(mode_data: dict[str, Any]) -> dict[str, str]:
    """Extract cleaned station names from discrete and line arrivals.

    :param mode_data: Mode-specific snapshot dictionary.
    :return: Mapping of NaPTAN to cleaned display label.
    """
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


class TfLTransitProvider(TransitProvider):
    """Transit provider for Transport for London Unified API."""

    provider_id: ClassVar[str] = "tfl"
    supported_modes: ClassVar[set[TransitMode]] = {
        TransitMode.BUS,
        TransitMode.TRAIN,
        TransitMode.TUBE,
        TransitMode.TRAM,
    }

    def parse_line_status(
        self, payload: list[dict[str, Any]] | dict[str, Any]
    ) -> LineStatus:
        """Parse raw TfL line status payload into normalised LineStatus.

        :param payload: List of line status entities or single line object.
        :return: LineStatus instance.
        """
        if isinstance(payload, list) and payload:
            line_data: dict[str, Any] = payload[0]
        elif isinstance(payload, dict):
            line_data = payload
        else:
            line_data = {}

        statuses = line_data.get("lineStatuses", [])
        if not statuses:
            colour, icon = SEVERITY_MAPPINGS["Unknown"]
            return LineStatus(
                status_label="Unknown",
                status_colour=colour,
                status_icon=icon,
                reason=None,
            )

        active_status = next(
            (
                s
                for s in statuses
                if any(vp.get("isNow", False) for vp in s.get("validityPeriods", []))
            ),
            statuses[0],
        )

        label = active_status.get("statusSeverityDescription", "Unknown")
        reason = active_status.get("reason") or active_status.get("disruption", {}).get(
            "description"
        )
        colour, icon = SEVERITY_MAPPINGS.get(label, SEVERITY_MAPPINGS["Unknown"])
        is_cancelled = label in TFL_CANCELLED_STATUSES
        is_delayed = label in TFL_DELAYED_STATUSES

        return LineStatus(
            status_label=label,
            status_colour=colour,
            status_icon=icon,
            reason=reason,
            is_delayed=is_delayed,
            is_cancelled=is_cancelled,
        )

    def parse_bus_arrivals(
        self,
        payload: list[dict[str, Any]],
        target_stop: str,
        line_id: str | None = None,
    ) -> list[DeparturePrediction]:
        """Parse TfL bus arrival predictions targeting a specific stop.

        :param payload: List of Prediction entities.
        :param target_stop: Target boarding stop identifier (NaPTAN).
        :param line_id: Optional line identifier filter (e.g. '26').
        :return: Ordered list of DeparturePrediction objects.
        """
        predictions: list[DeparturePrediction] = []

        for item in payload:
            naptan = item.get("naptanId")
            if naptan != target_stop:
                continue

            if (
                line_id
                and item.get("lineId") != line_id
                and item.get("lineName") != line_id
            ):
                continue

            tts = int(item.get("timeToStation", 0))
            prediction = DeparturePrediction(
                vehicle_id=item.get("vehicleId"),
                destination=item.get("destinationName", ""),
                expected_time=item.get("expectedArrival"),
                seconds_to_arrival=tts,
                platform_or_bay=item.get("platformName"),
                is_realtime=True,
                location=item.get("currentLocation", ""),
            )
            predictions.append(prediction)

        predictions.sort(key=lambda p: p.seconds_to_arrival)
        return predictions

    def parse_rail_journey_results(
        self,
        payload: dict[str, Any],
        from_station: str,
        to_station: str,
        reference_time_iso: str | None = None,
    ) -> list[DeparturePrediction]:
        """Parse TfL journey results for rail journeys into DeparturePredictions.

        :param payload: ItineraryResult JSON payload.
        :param from_station: Boarding station code.
        :param to_station: Alighting station code.
        :param reference_time_iso: Optional reference snapshot timestamp.
        :return: Ordered list of DeparturePrediction objects.
        """
        journeys = payload.get("journeys", [])
        predictions: list[DeparturePrediction] = []

        ref_dt = (
            _parse_datetime(reference_time_iso)
            if reference_time_iso
            else datetime.now(timezone.utc)
        )

        for journey in journeys:
            start_iso = journey.get("startDateTime")
            if not start_iso:
                continue

            start_dt = _parse_datetime(start_iso)
            seconds_to_departure = int((start_dt - ref_dt).total_seconds())

            if seconds_to_departure < -120:
                continue

            legs = journey.get("legs", [])
            destination = ""
            departure_name = ""
            if legs:
                destination = legs[0].get("instruction", {}).get("summary", "")
                dep_point = legs[0].get("departurePoint", {})
                departure_name = dep_point.get("commonName", "")

            prediction = DeparturePrediction(
                vehicle_id=None,
                destination=destination,
                expected_time=start_iso,
                seconds_to_arrival=max(0, seconds_to_departure),
                platform_or_bay=None,
                is_realtime=False,
                location=departure_name or "Terminus Buffer",
            )
            predictions.append(prediction)

        predictions.sort(key=lambda p: p.seconds_to_arrival)
        return predictions

    def parse_tube_arrivals(
        self,
        payload: list[dict[str, Any]],
        target_stop: str,
        line_id: str | None = None,
    ) -> list[DeparturePrediction]:
        """Parse TfL tube arrival predictions targeting a specific station.

        :param payload: List of Prediction entities.
        :param target_stop: Target boarding station identifier (NaPTAN).
        :param line_id: Optional line identifier filter (e.g. 'central').
        :return: Ordered list of DeparturePrediction objects.
        """
        predictions: list[DeparturePrediction] = []

        for item in payload:
            naptan = item.get("naptanId")
            if naptan != target_stop:
                continue

            if (
                line_id
                and item.get("lineId") != line_id
                and item.get("lineName") != line_id
            ):
                continue

            tts = int(item.get("timeToStation", 0))
            prediction = DeparturePrediction(
                vehicle_id=item.get("vehicleId"),
                destination=item.get("destinationName", ""),
                expected_time=item.get("expectedArrival"),
                seconds_to_arrival=tts,
                platform_or_bay=item.get("platformName"),
                is_realtime=True,
                location=item.get("currentLocation", ""),
            )
            predictions.append(prediction)

        predictions.sort(key=lambda p: p.seconds_to_arrival)
        return predictions

    def calculate_corridor_progress(
        self,
        current_naptan: str,
        corridor_stops: list[str],
        stop_names: dict[str, str] | None = None,
    ) -> tuple[float, str]:
        """Calculate normalised vehicle progression ratio along corridor.

        :param current_naptan: NaPTAN identifier where the vehicle was recorded.
        :param corridor_stops: Ordered list of corridor stop NaPTANs.
        :param stop_names: Optional dictionary mapping NaPTANs to friendly names.
        :return: Tuple of (progress_ratio 0.0-1.0, current_location_label).
        """
        if current_naptan not in corridor_stops or not corridor_stops:
            return 0.0, ""

        index = corridor_stops.index(current_naptan)
        total_steps = max(len(corridor_stops) - 1, 1)
        ratio = round(index / total_steps, 2)
        label = (stop_names or {}).get(current_naptan, current_naptan)
        return ratio, label

    def extract_telemetry_from_snapshot(
        self, route: RouteConfig, snapshot: dict[str, Any]
    ) -> RouteTelemetry:
        """Extract normalised telemetry for a route from a multi-modal snapshot.

        :param route: Configured RouteConfig instance.
        :param snapshot: Offline snapshot dictionary.
        :return: Normalised RouteTelemetry instance.
        """
        ref_timestamp: str = snapshot.get("timestamp", "")

        if route.mode == TransitMode.BUS:
            bus_data = snapshot.get("bus", {})
            bus_line_arrivals = bus_data.get("line_arrivals", [])
            stop_names = _build_tfl_stop_names_map(mode_data=bus_data)
            target_naptan = route.boarding_stop or ""
            raw_arrivals = (
                _extract_stop_arrivals(mode_data=bus_data, target_naptan=target_naptan)
                if target_naptan
                else []
            )

            departures = self.parse_bus_arrivals(
                payload=raw_arrivals,
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
                    adj_str = line_match.get("timing", {}).get(
                        "countdownServerAdjustment"
                    )
                    adj_sec = _parse_countdown_adjustment(adjustment_str=adj_str)
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
                sid_arrivals = _extract_stop_arrivals(
                    mode_data=bus_data, target_naptan=sid
                )
                corridor_departures[sid] = self.parse_bus_arrivals(
                    payload=sid_arrivals,
                    target_stop=sid,
                    line_id=route.line,
                )

            raw_status = bus_data.get("line_status", [])
            line_status = self.parse_line_status(payload=raw_status)
            active_vid = departures[0].vehicle_id if departures else None

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=active_vid,
                corridor_progress_ratio=0.0,
                current_stop_location="",
                line_status=line_status,
                corridor_departures=corridor_departures,
                stop_names=stop_names,
            )

        if route.mode == TransitMode.TRAIN:
            train_data = snapshot.get("train", {})
            journey_payload = train_data.get("journey_results") or snapshot.get(
                "train_journey_results", {}
            )
            departures = self.parse_rail_journey_results(
                payload=journey_payload,
                from_station=route.boarding_stop or "",
                to_station=route.destination_stop or "",
                reference_time_iso=ref_timestamp,
            )
            raw_status = train_data.get("line_status", [])
            line_status = self.parse_line_status(payload=raw_status)
            current_loc = departures[0].location if departures else ""

            stop_names = {}
            if route.boarding_stop:
                stop_names[route.boarding_stop] = clean_stop_name(
                    raw_name=route.boarding_stop
                )
            if route.destination_stop:
                stop_names[route.destination_stop] = clean_stop_name(
                    raw_name=route.destination_stop
                )

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=None,
                corridor_progress_ratio=0.0,
                current_stop_location=current_loc,
                line_status=line_status,
                corridor_departures={},
                stop_names=stop_names,
            )

        if route.mode == TransitMode.TUBE:
            tube_data = snapshot.get("tube", {})
            stop_names = _build_tfl_stop_names_map(mode_data=tube_data)
            target_naptan = route.boarding_stop or ""
            raw_arrivals = (
                _extract_stop_arrivals(mode_data=tube_data, target_naptan=target_naptan)
                if target_naptan
                else []
            )

            departures = self.parse_tube_arrivals(
                payload=raw_arrivals,
                target_stop=target_naptan,
                line_id=route.line,
            )

            corridor_departures = {}
            for sid in route.corridor_stops:
                sid_arrivals = _extract_stop_arrivals(
                    mode_data=tube_data, target_naptan=sid
                )
                corridor_departures[sid] = self.parse_tube_arrivals(
                    payload=sid_arrivals,
                    target_stop=sid,
                    line_id=route.line,
                )

            raw_status = tube_data.get("line_status", [])
            line_status = self.parse_line_status(payload=raw_status)
            active_vid = departures[0].vehicle_id if departures else None

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=active_vid,
                corridor_progress_ratio=0.0,
                current_stop_location="",
                line_status=line_status,
                corridor_departures=corridor_departures,
                stop_names=stop_names,
            )

        raise NotImplementedError(f"Mode {route.mode} not supported by TfL provider")

    async def _async_fetch_json(self, url: str) -> Any:
        """Fetch JSON payload from URL using configured or ephemeral session."""
        headers = {
            "User-Agent": "HomeAssistant-CommuteTracker/1.0",
            "Accept": "application/json",
        }
        if self._session is not None:
            async with self._session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Fetch and return line status via TfL API with caching.

        :param line_id: Line identifier (e.g. '26', 'central').
        :param mode: Transit mode.
        :return: LineStatus instance.
        """
        cache_key = f"tfl_status_{line_id}"

        async def _fetch() -> LineStatus:
            try:
                url = f"{TFL_API_BASE_URL}/Line/{line_id}/Status"
                data = await self._async_fetch_json(url)
                return self.parse_line_status(payload=data)
            except Exception:
                colour, icon = SEVERITY_MAPPINGS["Unknown"]
                return LineStatus(
                    status_label="Unknown",
                    status_colour=colour,
                    status_icon=icon,
                )

        return await self._cache.async_get_or_set(cache_key, _fetch)

    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Fetch and return route telemetry via TfL API.

        :param route: RouteConfig instance.
        :return: RouteTelemetry instance.
        """
        line_status = await self.async_get_line_status(
            line_id=route.line, mode=route.mode
        )

        if route.mode == TransitMode.BUS:
            cache_key = f"tfl_arrivals_bus_{route.line}"

            async def _fetch_bus_arrivals() -> list[dict[str, Any]]:
                try:
                    url = f"{TFL_API_BASE_URL}/Line/{route.line}/Arrivals"
                    data = await self._async_fetch_json(url)
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            raw_arrivals = await self._cache.async_get_or_set(
                cache_key, _fetch_bus_arrivals
            )
            target_stop = route.boarding_stop or ""
            departures = self.parse_bus_arrivals(
                payload=raw_arrivals,
                target_stop=target_stop,
                line_id=route.line,
            )

            corridor_departures: dict[str, list[DeparturePrediction]] = {}
            for sid in route.corridor_stops:
                corridor_departures[sid] = self.parse_bus_arrivals(
                    payload=raw_arrivals,
                    target_stop=sid,
                    line_id=route.line,
                )

            stop_names: dict[str, str] = {}
            for item in raw_arrivals:
                naptan = item.get("naptanId")
                st_name = item.get("stationName")
                if naptan and st_name and naptan not in stop_names:
                    stop_names[naptan] = clean_stop_name(st_name)

            if route.boarding_stop and route.boarding_stop not in stop_names:
                stop_names[route.boarding_stop] = clean_stop_name(route.boarding_stop)
            for sid in route.corridor_stops:
                if sid not in stop_names:
                    stop_names[sid] = clean_stop_name(sid)

            active_vid = departures[0].vehicle_id if departures else None

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=active_vid,
                corridor_progress_ratio=0.0,
                current_stop_location="",
                line_status=line_status,
                corridor_departures=corridor_departures,
                stop_names=stop_names,
            )

        if route.mode == TransitMode.TRAIN:
            from_stop = route.boarding_stop or ""
            to_stop = route.destination_stop or ""
            cache_key = f"tfl_journey_{from_stop}_{to_stop}"

            async def _fetch_journey() -> dict[str, Any]:
                try:
                    url = (
                        f"{TFL_API_BASE_URL}/Journey/JourneyResults/{from_stop}"
                        f"/to/{to_stop}?mode=national-rail&journeyPreference=LeastInterchange"
                    )
                    data = await self._async_fetch_json(url)
                    return data if isinstance(data, dict) else {}
                except Exception:
                    return {}

            journey_data = await self._cache.async_get_or_set(cache_key, _fetch_journey)
            departures = self.parse_rail_journey_results(
                payload=journey_data,
                from_station=from_stop,
                to_station=to_stop,
            )
            current_loc = departures[0].location if departures else ""

            stop_names = {}
            if route.boarding_stop:
                stop_names[route.boarding_stop] = clean_stop_name(route.boarding_stop)
            if route.destination_stop:
                stop_names[route.destination_stop] = clean_stop_name(
                    route.destination_stop
                )

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=None,
                corridor_progress_ratio=0.0,
                current_stop_location=current_loc,
                line_status=line_status,
                corridor_departures={},
                stop_names=stop_names,
            )

        if route.mode == TransitMode.TUBE:
            cache_key = f"tfl_arrivals_tube_{route.line}"

            async def _fetch_tube_arrivals() -> list[dict[str, Any]]:
                try:
                    url = f"{TFL_API_BASE_URL}/Line/{route.line}/Arrivals"
                    data = await self._async_fetch_json(url)
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            raw_arrivals = await self._cache.async_get_or_set(
                cache_key, _fetch_tube_arrivals
            )
            target_stop = route.boarding_stop or ""
            departures = self.parse_tube_arrivals(
                payload=raw_arrivals,
                target_stop=target_stop,
                line_id=route.line,
            )

            corridor_departures = {}
            for sid in route.corridor_stops:
                corridor_departures[sid] = self.parse_tube_arrivals(
                    payload=raw_arrivals,
                    target_stop=sid,
                    line_id=route.line,
                )

            stop_names = {}
            for item in raw_arrivals:
                naptan = item.get("naptanId")
                st_name = item.get("stationName")
                if naptan and st_name and naptan not in stop_names:
                    stop_names[naptan] = clean_stop_name(st_name)

            if route.boarding_stop and route.boarding_stop not in stop_names:
                stop_names[route.boarding_stop] = clean_stop_name(route.boarding_stop)
            for sid in route.corridor_stops:
                if sid not in stop_names:
                    stop_names[sid] = clean_stop_name(sid)

            active_vid = departures[0].vehicle_id if departures else None

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=active_vid,
                corridor_progress_ratio=0.0,
                current_stop_location="",
                line_status=line_status,
                corridor_departures=corridor_departures,
                stop_names=stop_names,
            )

        raise NotImplementedError(f"Mode {route.mode} not supported by TfL provider")
