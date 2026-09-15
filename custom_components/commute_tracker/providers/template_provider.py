"""Template transit provider boilerplate for community extensions.

This module demonstrates how to implement a new transit authority provider
(e.g., Paris RATP, New York MTA, Berlin BVG, Deutsche Bahn, GTFS-RT) for the
Home Assistant Commute Tracker integration using the Adaptor pattern.

Architecture & Lifecycle:
-------------------------
A TransitProvider acts as an Adaptor between an external vendor API and the
integration's normalised domain models. To implement a new provider:

1. Subclass ``TransitProvider``.
2. Declare ``provider_id`` (string) and ``supported_modes`` (set of modes).
3. Optionally set ``base_url`` and configure authentication via
   ``get_default_params`` or ``get_default_headers``.
4. Implement the data adaptation hooks:
   - ``adapt_line_status``: Maps disruption payloads into ``LineStatus``.
     If status is missing or ambiguous, return ``UNKNOWN_LINE_STATUS``.
   - ``adapt_departures``: Maps arrival entities into sorted
     ``DeparturePrediction`` objects.
   - ``clean_stop_name``: Strips vendor suffixes (e.g. " Station", " Pier").
5. Implement or override fetching hooks:
   - Line-based APIs (e.g. TfL Line Arrivals): ``async_fetch_line_arrivals``.
   - Stop-centric APIs (e.g. SIRI StopMonitoring): ``async_fetch_stop_arrivals``.
   - Journey planners (e.g. National Rail, DB Hafas): ``async_fetch_journey``.
6. Implement ``async_get_telemetry`` to orchestrate fetching and model assembly
   using ``self.build_route_telemetry`` and ``async_get_line_status``.
"""

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


class TemplateTransitProvider(TransitProvider):
    """Reference transit provider illustrating Adaptor pattern and hooks."""

    provider_id: ClassVar[str] = "template"
    base_url: ClassVar[str] = "https://api.example-transit.org/v1"
    supported_modes: ClassVar[set[TransitMode]] = {
        TransitMode.BUS,
        TransitMode.TRAIN,
        TransitMode.TUBE,
        TransitMode.TRAM,
        TransitMode.FERRY,
    }

    def clean_stop_name(self, raw_name: str) -> str:
        """Normalise verbose stop names into concise display labels.

        :param raw_name: Raw station name string from the vendor API.
        :return: Cleaned stop name label.
        """
        name = raw_name
        for suffix in (" Station", " Terminus", " Pier", " Stop"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name.strip()

    def adapt_line_status(
        self, raw_payload: Any, mode: TransitMode = TransitMode.BUS
    ) -> LineStatus:
        """Adapt raw vendor status payload into normalised LineStatus.

        If the status payload is empty, invalid, or unrecognised, default to
        ``UNKNOWN_LINE_STATUS``. Never assume "Good Service" without evidence.

        :param raw_payload: Raw line status response dictionary or list.
        :param mode: Transit mode of the line.
        :return: Normalised LineStatus instance.
        """
        if not isinstance(raw_payload, dict) or not raw_payload:
            return UNKNOWN_LINE_STATUS

        status_text = raw_payload.get("status", "Unknown")
        if status_text == "Good Service":
            return LineStatus(
                status_label="Good Service",
                status_color="#00A859",
                status_icon="mdi:check-circle",
                detail=None,
            )
        if status_text == "Minor Delays":
            return LineStatus(
                status_label="Minor Delays",
                status_color="#FFAE42",
                status_icon="mdi:alert-circle",
                detail=raw_payload.get("reason"),
                is_delayed=True,
            )
        if status_text in {"Severe Delays", "Suspended"}:
            return LineStatus(
                status_label=status_text,
                status_color="#DC241F",
                status_icon="mdi:close-octagon",
                detail=raw_payload.get("reason"),
                is_cancelled=status_text == "Suspended",
                is_delayed=status_text == "Severe Delays",
            )

        return UNKNOWN_LINE_STATUS

    def adapt_departures(
        self,
        raw_payload: Any,
        target_stop: str,
        line_id: str | None = None,
    ) -> list[DeparturePrediction]:
        """Adapt raw arrival predictions into sorted DeparturePredictions.

        :param raw_payload: Raw arrivals list or dictionary from vendor API.
        :param target_stop: Target boarding stop identifier.
        :param line_id: Optional line filter.
        :return: Chronologically sorted list of DeparturePrediction instances.
        """
        if not isinstance(raw_payload, list):
            return []

        predictions: list[DeparturePrediction] = []
        for item in raw_payload:
            if not isinstance(item, dict):
                continue
            if item.get("stop_id") != target_stop:
                continue
            if line_id and item.get("line") != line_id:
                continue

            predictions.append(
                DeparturePrediction(
                    vehicle_id=item.get("vehicle_id"),
                    destination=item.get("destination", ""),
                    expected_time=item.get("expected_arrival"),
                    seconds_to_arrival=int(item.get("countdown_seconds", 0)),
                    platform_or_bay=item.get("platform"),
                    is_realtime=bool(item.get("is_realtime", True)),
                    location=item.get("current_location", ""),
                )
            )

        predictions.sort(key=lambda p: p.seconds_to_arrival)
        return predictions

    def adapt_stop_names(self, raw_payload: Any) -> dict[str, str]:
        """Extract mapping of stop identifier to clean station name.

        :param raw_payload: Raw arrivals payload from API.
        :return: Mapping of stop ID to cleaned station name label.
        """
        if not isinstance(raw_payload, list):
            return {}

        names: dict[str, str] = {}
        for item in raw_payload:
            if isinstance(item, dict):
                sid = item.get("stop_id")
                raw_name = item.get("stop_name")
                if sid and raw_name and sid not in names:
                    names[sid] = self.clean_stop_name(raw_name=raw_name)
        return names

    async def async_fetch_line_arrivals(self, line_id: str, mode: TransitMode) -> Any:
        """Fetch arrival predictions across an entire line via HTTP.

        :param line_id: Transit line identifier.
        :param mode: Transit mode.
        :return: Raw API payload.
        """
        try:
            return await self.async_fetch_json(f"lines/{line_id}/arrivals")
        except Exception:
            return []

    async def async_fetch_line_status(self, line_id: str, mode: TransitMode) -> Any:
        """Fetch raw operational line status via HTTP.

        :param line_id: Transit line identifier.
        :param mode: Transit mode.
        :return: Raw API payload.
        """
        try:
            return await self.async_fetch_json(f"lines/{line_id}/status")
        except Exception:
            return None

    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Fetch live telemetry and predictions for a configured route.

        :param route: The configured route settings.
        :return: Normalised RouteTelemetry instance.
        """
        cache_key = f"{self.provider_id}_arrivals_{route.line}"

        async def _fetch() -> Any:
            return await self.async_fetch_line_arrivals(
                line_id=route.line, mode=route.mode
            )

        raw_arrivals = await self.async_cached_fetch(
            cache_key=cache_key, fetch_callable=_fetch
        )
        if raw_arrivals is None:
            raw_arrivals = []

        target_stop = route.boarding_stop or ""
        departures = self.adapt_departures(
            raw_payload=raw_arrivals,
            target_stop=target_stop,
            line_id=route.line,
        )

        corridor_departures: dict[str, list[DeparturePrediction]] = {}
        for stop_id in route.corridor_stops:
            corridor_departures[stop_id] = self.adapt_departures(
                raw_payload=raw_arrivals,
                target_stop=stop_id,
                line_id=route.line,
            )

        stop_names = self.adapt_stop_names(raw_payload=raw_arrivals)
        line_status = await self.async_get_line_status(
            line_id=route.line, mode=route.mode
        )

        return self.build_route_telemetry(
            route=route,
            departures=departures,
            line_status=line_status,
            corridor_departures=corridor_departures,
            stop_names=stop_names,
        )
