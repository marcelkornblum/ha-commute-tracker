"""Template transit provider boilerplate for community extensions.

This module demonstrates how to implement a new transit authority provider
(e.g., Paris RATP, New York MTA, Berlin BVG, Deutsche Bahn) for the
Home Assistant Commute Tracker integration.
"""

from typing import Any, ClassVar

from custom_components.commute_tracker.models import (
    DeparturePrediction,
    LineStatus,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import TransitProvider


class TemplateTransitProvider(TransitProvider):
    """Reference transit provider illustrating required methods and models."""

    provider_id: ClassVar[str] = "template"
    supported_modes: ClassVar[set[TransitMode]] = {
        TransitMode.BUS,
        TransitMode.TRAIN,
        TransitMode.TUBE,
        TransitMode.TRAM,
        TransitMode.FERRY,
    }

    async def async_get_line_status(
        self, line_id: str, mode: TransitMode
    ) -> LineStatus:
        """Fetch and normalise transit line operational status.

        :param line_id: The line identifier (e.g. 'M15', 'U2', 'S1').
        :param mode: The mode of transit.
        :return: Normalised LineStatus instance.
        """
        # Providers can use self._session to perform async HTTP calls,
        # wrapped in self._cache.async_get_or_set() for deduplication.
        return LineStatus(
            status_label="Good Service",
            status_colour="#00A859",
            status_icon="mdi:check-circle",
            reason=None,
        )

    async def async_get_telemetry(
        self, route: RouteConfig, snapshot: dict[str, Any] | None = None
    ) -> RouteTelemetry:
        """Fetch and normalise route predictions and vehicle progression.

        :param route: The configured route settings.
        :param snapshot: Optional offline snapshot dictionary for testing.
        :return: Normalised RouteTelemetry instance.
        """
        # Step 1: Query API or parse offline snapshot
        # Step 2: Extract predictions targeting route.boarding_stop
        # Step 3: Return structured RouteTelemetry
        sample_departure = DeparturePrediction(
            vehicle_id="TEMPLATE_01",
            destination="Terminus Station",
            expected_time="2026-09-14T15:00:00Z",
            seconds_to_arrival=300,
            platform_or_bay="1",
            is_realtime=True,
        )

        line_status = await self.async_get_line_status(route.line, route.mode)

        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=[sample_departure],
            active_vehicle_id="TEMPLATE_01",
            corridor_progress_ratio=0.5,
            current_stop_location="Approaching Boarding Stop",
            line_status=line_status,
        )
