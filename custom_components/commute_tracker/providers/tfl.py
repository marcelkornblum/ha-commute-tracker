"""Transport for London (TfL) transit provider implementation."""

from datetime import datetime, timezone
from typing import Any, ClassVar

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import TransitProvider

TFL_API_BASE_URL = "https://api.tfl.gov.uk"

# Standard TfL status severity colours and icons
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
}


def _parse_datetime(iso_str: str) -> datetime:
    """Parse ISO datetime string into UTC datetime object."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


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
            return LineStatus(
                status_label="Good Service",
                status_colour="#00A859",
                status_icon="mdi:check-circle",
                reason=None,
            )

        # Prioritise current active status
        active_status = next(
            (
                s
                for s in statuses
                if any(vp.get("isNow", False) for vp in s.get("validityPeriods", []))
            ),
            statuses[0],
        )

        label = active_status.get("statusSeverityDescription", "Good Service")
        reason = active_status.get("reason") or active_status.get("disruption", {}).get(
            "description"
        )
        colour, icon = SEVERITY_MAPPINGS.get(label, ("#FFAE42", "mdi:alert-circle"))

        return LineStatus(
            status_label=label,
            status_colour=colour,
            status_icon=icon,
            reason=reason,
        )

    def parse_bus_arrivals(
        self,
        payload: list[dict[str, Any]],
        target_stop: str,
        corridor_stops: list[str] | None = None,
    ) -> list[DeparturePrediction]:
        """Parse TfL bus arrival predictions targeting a specific stop.

        :param payload: List of Prediction entities.
        :param target_stop: Target boarding stop identifier (NaPTAN).
        :param corridor_stops: Optional list of upstream corridor stop identifiers.
        :return: Ordered list of DeparturePrediction objects.
        """
        predictions: list[DeparturePrediction] = []

        for item in payload:
            naptan = item.get("naptanId")
            if naptan != target_stop:
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

        # Sort ascending by arrival time
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

            # Only consider future or near-current departures (within 2 minutes leeway)
            if seconds_to_departure < -120:
                continue

            legs = journey.get("legs", [])
            destination = ""
            if legs:
                destination = legs[0].get("instruction", {}).get("summary", "")

            prediction = DeparturePrediction(
                vehicle_id=None,
                destination=destination,
                expected_time=start_iso,
                seconds_to_arrival=max(0, seconds_to_departure),
                platform_or_bay=None,
                is_realtime=False,
                location="Terminus Buffer",
            )
            predictions.append(prediction)

        predictions.sort(key=lambda p: p.seconds_to_arrival)
        return predictions

    def parse_tube_arrivals(
        self,
        payload: list[dict[str, Any]],
        target_stop: str,
        direction: str | None = None,
        corridor_stops: list[str] | None = None,
    ) -> list[DeparturePrediction]:
        """Parse TfL tube arrival predictions targeting a specific station.

        :param payload: List of Prediction entities.
        :param target_stop: Target boarding station identifier (NaPTAN).
        :param direction: Optional direction filter (e.g. 'inbound', 'outbound').
        :param corridor_stops: Optional list of upstream corridor stop identifiers.
        :return: Ordered list of DeparturePrediction objects.
        """
        predictions: list[DeparturePrediction] = []

        for item in payload:
            naptan = item.get("naptanId")
            if naptan != target_stop:
                continue

            item_dir = item.get("direction")
            if direction and item_dir and item_dir != direction:
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
        """Calculate normalized vehicle progression ratio along corridor.

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
            bus_discrete = bus_data.get("discrete_stop_arrivals", {})
            raw_arrivals = (
                bus_discrete.get("target_trafalgar_square")
                or snapshot.get("bus_corridor_stop_arrivals", {}).get(
                    "target_trafalgar_square", []
                )
                or bus_data.get("line_arrivals", [])
            )
            departures = self.parse_bus_arrivals(
                payload=raw_arrivals,
                target_stop=route.boarding_stop or "490013766F",
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
            )

        if route.mode == TransitMode.TRAIN:
            train_data = snapshot.get("train", {})
            journey_payload = train_data.get("journey_results") or snapshot.get(
                "train_journey_results", {}
            )
            departures = self.parse_rail_journey_results(
                payload=journey_payload,
                from_station=route.boarding_stop or "910GCHRX",
                to_station=route.destination_stop or "910GLNDNBDC",
                reference_time_iso=ref_timestamp,
            )
            raw_status = train_data.get("line_status", [])
            line_status = self.parse_line_status(payload=raw_status)

            return RouteTelemetry(
                route_id=route.route_id,
                line_id=route.line,
                mode=route.mode,
                departures=departures,
                active_vehicle_id=None,
                corridor_progress_ratio=0.0,
                current_stop_location="Charing Cross",
                line_status=line_status,
            )

        if route.mode == TransitMode.TUBE:
            tube_data = snapshot.get("tube", {})
            tube_discrete = tube_data.get("discrete_stop_arrivals", {})
            raw_arrivals = (
                tube_discrete.get("target_tottenham_court_road")
                or snapshot.get("tube_corridor_stop_arrivals", {}).get(
                    "target_tottenham_court_road", []
                )
                or tube_data.get("line_arrivals", [])
            )
            departures = self.parse_tube_arrivals(
                payload=raw_arrivals,
                target_stop=route.boarding_stop or "940GZZLUTCR",
                direction=route.direction or "inbound",
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
            )

        raise NotImplementedError(f"Mode {route.mode} not supported by TfL provider")

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
            if not self._session:
                return LineStatus(
                    status_label="Good Service",
                    status_colour="#00A859",
                    status_icon="mdi:check-circle",
                )
            url = f"{TFL_API_BASE_URL}/Line/{line_id}/Status"
            async with self._session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return self.parse_line_status(payload=data)

        return await self._cache.async_get_or_set(cache_key, _fetch)

    async def async_get_telemetry(
        self, route: RouteConfig, snapshot: dict[str, Any] | None = None
    ) -> RouteTelemetry:
        """Fetch and return route telemetry via TfL API or snapshot.

        :param route: RouteConfig instance.
        :param snapshot: Optional offline snapshot.
        :return: RouteTelemetry instance.
        """
        if snapshot is not None:
            return self.extract_telemetry_from_snapshot(route=route, snapshot=snapshot)

        line_status = await self.async_get_line_status(
            line_id=route.line, mode=route.mode
        )
        # Query line arrivals
        cache_key = f"tfl_arrivals_{route.line}"

        async def _fetch_arrivals() -> list[dict[str, Any]]:
            if not self._session:
                return []
            url = f"{TFL_API_BASE_URL}/Line/{route.line}/Arrivals"
            async with self._session.get(url) as response:
                response.raise_for_status()
                return await response.json()  # type: ignore[no-any-return]

        raw_arrivals = await self._cache.async_get_or_set(cache_key, _fetch_arrivals)
        departures = self.parse_bus_arrivals(
            payload=raw_arrivals,
            target_stop=route.boarding_stop or "",
        )

        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=departures,
            active_vehicle_id=departures[0].vehicle_id if departures else None,
            corridor_progress_ratio=0.0,
            current_stop_location="",
            line_status=line_status,
        )
