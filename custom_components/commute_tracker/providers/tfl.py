"""Transport for London (TfL) transit provider implementation."""

import zoneinfo
from datetime import datetime, timezone
from typing import Any, ClassVar

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import (
    UNKNOWN_LINE_STATUS,
    TransitProvider,
)

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


class TfLTransitProvider(TransitProvider):
    """Transit provider for TfL Unified API using the Adaptor pattern."""

    provider_id: ClassVar[str] = "tfl"
    base_url: ClassVar[str] = TFL_API_BASE_URL
    supported_modes: ClassVar[set[TransitMode]] = {
        TransitMode.BUS,
        TransitMode.TRAIN,
        TransitMode.TUBE,
        TransitMode.TRAM,
    }

    def clean_stop_name(self, raw_name: str) -> str:
        """Normalise verbose TfL station names into clean concise display labels."""
        return clean_stop_name(raw_name=raw_name)

    def adapt_line_status(
        self,
        raw_payload: Any,
        mode: TransitMode = TransitMode.BUS,
    ) -> LineStatus:
        """Adapt raw TfL line status payload into normalised LineStatus.

        :param raw_payload: List of line status entities or single line object.
        :param mode: Transit mode.
        :return: Normalised LineStatus instance.
        """
        if isinstance(raw_payload, list) and raw_payload:
            line_data: dict[str, Any] = raw_payload[0]
        elif isinstance(raw_payload, dict):
            line_data = raw_payload
        else:
            line_data = {}

        statuses = line_data.get("lineStatuses", [])
        if not statuses:
            return UNKNOWN_LINE_STATUS

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
        color, icon = SEVERITY_MAPPINGS.get(label, SEVERITY_MAPPINGS["Unknown"])
        is_cancelled = label in TFL_CANCELLED_STATUSES
        is_delayed = label in TFL_DELAYED_STATUSES

        return LineStatus(
            status_label=label,
            status_color=color,
            status_icon=icon,
            detail=reason,
            is_delayed=is_delayed,
            is_cancelled=is_cancelled,
        )

    def adapt_departures(
        self,
        raw_payload: Any,
        target_stop: str,
        line_id: str | None = None,
    ) -> list[DeparturePrediction]:
        """Adapt TfL bus, tube, or tram arrival predictions targeting a specific stop.

        :param raw_payload: List of Prediction entities.
        :param target_stop: Target boarding stop identifier (NaPTAN).
        :param line_id: Optional line identifier filter (e.g. '26', 'central').
        :return: Ordered list of DeparturePrediction objects.
        """
        if not isinstance(raw_payload, list):
            return []

        predictions: list[DeparturePrediction] = []

        for item in raw_payload:
            if not isinstance(item, dict):
                continue
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

    def adapt_journey(
        self,
        raw_payload: Any,
        origin: str,
        destination: str,
        reference_time_iso: str | None = None,
    ) -> list[DeparturePrediction]:
        """Adapt TfL journey results into DeparturePredictions.

        :param raw_payload: ItineraryResult JSON payload.
        :param origin: Boarding stop identifier.
        :param destination: Alighting stop identifier.
        :param reference_time_iso: Optional reference snapshot timestamp.
        :return: Ordered list of DeparturePrediction objects.
        """
        if not isinstance(raw_payload, dict):
            return []

        journeys = raw_payload.get("journeys", [])
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

    def adapt_stop_names(self, raw_payload: Any) -> dict[str, str]:
        """Extract cleaned station names from TfL arrival predictions.

        :param raw_payload: List of Prediction entities.
        :return: Mapping of NaPTAN to cleaned display label.
        """
        names: dict[str, str] = {}
        if not isinstance(raw_payload, list):
            return names
        for item in raw_payload:
            if isinstance(item, dict):
                sid = item.get("naptanId")
                name = item.get("stationName")
                if sid and name and sid not in names:
                    names[sid] = self.clean_stop_name(raw_name=name)
        return names

    async def async_fetch_line_arrivals(self, line_id: str, mode: TransitMode) -> Any:
        """Fetch arrival predictions across an entire line via TfL API.

        :param line_id: Line identifier (e.g. '26', 'central').
        :param mode: Transit mode.
        :return: Decoded JSON response.
        """
        return await self.async_fetch_json(f"Line/{line_id}/Arrivals")

    async def async_fetch_line_status(self, line_id: str, mode: TransitMode) -> Any:
        """Fetch operational line status via TfL API.

        :param line_id: Line identifier.
        :param mode: Transit mode.
        :return: Decoded JSON response.
        """
        return await self.async_fetch_json(f"Line/{line_id}/Status")

    async def async_fetch_journey(
        self, origin: str, destination: str, mode: TransitMode
    ) -> Any:
        """Fetch rail journeys between stations via TfL JourneyPlanner API.

        :param origin: Origin station code.
        :param destination: Destination station code.
        :param mode: Transit mode.
        :return: Decoded JSON response.
        """
        endpoint = (
            f"Journey/JourneyResults/{origin}/to/{destination}"
            "?mode=national-rail&journeyPreference=LeastInterchange"
        )
        return await self.async_fetch_json(endpoint)

    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Fetch and return route telemetry via TfL API.

        :param route: RouteConfig instance.
        :return: RouteTelemetry instance.
        """
        line_status = await self.async_get_line_status(
            line_id=route.line, mode=route.mode
        )

        if route.mode in {TransitMode.BUS, TransitMode.TUBE, TransitMode.TRAM}:
            cache_key = f"tfl_arrivals_{route.mode.value.lower()}_{route.line}"

            async def _fetch_arrivals() -> list[dict[str, Any]]:
                try:
                    data = await self.async_fetch_line_arrivals(
                        line_id=route.line, mode=route.mode
                    )
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            raw_arrivals = await self.async_cached_fetch(
                cache_key=cache_key, fetch_callable=_fetch_arrivals
            )
            target_stop = route.boarding_stop or ""
            departures = self.adapt_departures(
                raw_payload=raw_arrivals,
                target_stop=target_stop,
                line_id=route.line,
            )

            corridor_departures: dict[str, list[DeparturePrediction]] = {}
            for sid in route.corridor_stops:
                corridor_departures[sid] = self.adapt_departures(
                    raw_payload=raw_arrivals,
                    target_stop=sid,
                    line_id=route.line,
                )

            stop_names = self.adapt_stop_names(raw_payload=raw_arrivals)

            if route.boarding_stop and route.boarding_stop not in stop_names:
                stop_names[route.boarding_stop] = self.clean_stop_name(
                    route.boarding_stop
                )
            for sid in route.corridor_stops:
                if sid not in stop_names:
                    stop_names[sid] = self.clean_stop_name(sid)

            return self.build_route_telemetry(
                route=route,
                departures=departures,
                line_status=line_status,
                corridor_departures=corridor_departures,
                stop_names=stop_names,
            )

        if route.mode == TransitMode.TRAIN:
            from_stop = route.boarding_stop or ""
            to_stop = route.alighting_stop or ""
            cache_key = f"tfl_journey_{from_stop}_{to_stop}"

            async def _fetch_journey() -> dict[str, Any]:
                try:
                    data = await self.async_fetch_journey(
                        origin=from_stop, destination=to_stop, mode=route.mode
                    )
                    return data if isinstance(data, dict) else {}
                except Exception:
                    return {}

            journey_data = await self.async_cached_fetch(
                cache_key=cache_key, fetch_callable=_fetch_journey
            )
            departures = self.adapt_journey(
                raw_payload=journey_data,
                origin=from_stop,
                destination=to_stop,
            )

            stop_names = {}
            if route.boarding_stop:
                stop_names[route.boarding_stop] = self.clean_stop_name(
                    route.boarding_stop
                )
            if route.alighting_stop:
                stop_names[route.alighting_stop] = self.clean_stop_name(
                    route.alighting_stop
                )

            return self.build_route_telemetry(
                route=route,
                departures=departures,
                line_status=line_status,
                corridor_departures={},
                stop_names=stop_names,
                active_vehicle_id=None,
            )

        raise NotImplementedError(f"Mode {route.mode} not supported by TfL provider")
