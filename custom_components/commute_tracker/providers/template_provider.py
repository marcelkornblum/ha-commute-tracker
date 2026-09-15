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
        return LineStatus(
            status_label="Good Service",
            status_colour="#00A859",
            status_icon="mdi:check-circle",
            detail=None,
        )

    def extract_telemetry_from_snapshot(
        self, route: RouteConfig, snapshot: dict[str, Any]
    ) -> RouteTelemetry:
        """Extract route telemetry from offline snapshot dictionary."""
        sample_departure = DeparturePrediction(
            vehicle_id="TEMPLATE_01",
            destination="Terminus Station",
            expected_time="2026-09-14T15:00:00Z",
            seconds_to_arrival=300,
            platform_or_bay="1",
            is_realtime=True,
        )
        return RouteTelemetry(
            route_id=route.route_id,
            line_id=route.line,
            mode=route.mode,
            departures=[sample_departure],
            active_vehicle_id="TEMPLATE_01",
            corridor_progress_ratio=0.5,
            current_stop_location="Approaching Boarding Stop",
            line_status=LineStatus(
                status_label="Good Service",
                status_colour="#00A859",
                status_icon="mdi:check-circle",
            ),
        )

    async def async_get_telemetry(self, route: RouteConfig) -> RouteTelemetry:
        """Fetch and normalise route predictions and vehicle progression.

        :param route: The configured route settings.
        :return: Normalised RouteTelemetry instance.
        """

        sample_departure = DeparturePrediction(
            vehicle_id="TEMPLATE_01",
            destination="Terminus Station",
            expected_time="2026-09-14T15:00:00Z",
            seconds_to_arrival=300,
            platform_or_bay="1",
            is_realtime=True,
        )

        line_status = await self.async_get_line_status(
            line_id=route.line, mode=route.mode
        )

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
