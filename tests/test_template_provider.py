"""Unit tests for the template provider boilerplate."""

from typing import Any

import pytest

from custom_components.commute_tracker.models import (
    RouteConfig,
    TransitMode,
)
from custom_components.commute_tracker.providers.base import UNKNOWN_LINE_STATUS
from custom_components.commute_tracker.providers.template_provider import (
    TemplateTransitProvider,
)
from tests.snapshot_adapter import extract_snapshot_telemetry


def test_template_provider_instantiation_and_metadata() -> None:
    """Verify TemplateTransitProvider subclasses TransitProvider correctly."""
    provider = TemplateTransitProvider()
    assert provider.provider_id == "template"
    assert TransitMode.BUS in provider.supported_modes
    assert TransitMode.TRAIN in provider.supported_modes
    assert provider.base_url == "https://api.example-transit.org/v1"


def test_template_provider_clean_stop_name() -> None:
    """Verify clean_stop_name strips common transit suffixes."""
    provider = TemplateTransitProvider()
    assert provider.clean_stop_name("Central Station") == "Central"
    assert provider.clean_stop_name("North Pier") == "North"
    assert provider.clean_stop_name("South Terminus") == "South"
    assert provider.clean_stop_name("High Street Stop") == "High Street"
    assert provider.clean_stop_name("Market Square") == "Market Square"


def test_template_provider_adapt_line_status() -> None:
    """Verify adapt_line_status maps known statuses and defaults to Unknown."""
    provider = TemplateTransitProvider()

    # Unrecognised / empty must be Unknown
    assert provider.adapt_line_status({}) == UNKNOWN_LINE_STATUS
    assert provider.adapt_line_status("invalid") == UNKNOWN_LINE_STATUS

    # Good service
    good = provider.adapt_line_status({"status": "Good Service"})
    assert good.status_label == "Good Service"
    assert good.status_color == "#00A859"
    assert good.is_delayed is False

    # Minor delays
    minor = provider.adapt_line_status(
        {"status": "Minor Delays", "reason": "Signal fault"}
    )
    assert minor.status_label == "Minor Delays"
    assert minor.status_color == "#FFAE42"
    assert minor.is_delayed is True
    assert minor.detail == "Signal fault"

    # Suspended
    suspended = provider.adapt_line_status(
        {"status": "Suspended", "reason": "Flooding"}
    )
    assert suspended.status_label == "Suspended"
    assert suspended.status_color == "#DC241F"
    assert suspended.is_cancelled is True


def test_template_provider_adapt_departures() -> None:
    """Verify adapt_departures parses and sorts departures for target stop."""
    provider = TemplateTransitProvider()
    raw_payload = [
        {
            "stop_id": "stop_a",
            "line": "M15",
            "vehicle_id": "BUS_02",
            "destination": "Downtown",
            "expected_arrival": "2026-09-15T10:10:00Z",
            "countdown_seconds": 600,
            "platform": "1",
            "is_realtime": True,
            "current_location": "2 stops away",
        },
        {
            "stop_id": "stop_a",
            "line": "M15",
            "vehicle_id": "BUS_01",
            "destination": "Downtown",
            "expected_arrival": "2026-09-15T10:05:00Z",
            "countdown_seconds": 300,
            "platform": "1",
            "is_realtime": True,
            "current_location": "Approaching",
        },
        {
            "stop_id": "other_stop",
            "line": "M15",
            "vehicle_id": "BUS_99",
            "countdown_seconds": 120,
        },
    ]

    departures = provider.adapt_departures(
        raw_payload=raw_payload,
        target_stop="stop_a",
        line_id="M15",
    )

    assert len(departures) == 2
    # Chronologically sorted
    assert departures[0].vehicle_id == "BUS_01"
    assert departures[0].seconds_to_arrival == 300
    assert departures[1].vehicle_id == "BUS_02"
    assert departures[1].seconds_to_arrival == 600


def test_snapshot_adapter_with_template_provider() -> None:
    """Verify test harness snapshot adapter works with TemplateTransitProvider."""
    provider = TemplateTransitProvider()
    route = RouteConfig(
        route_id="sample_bus",
        mode=TransitMode.BUS,
        line="M15",
        provider="template",
        boarding_stop="stop_a",
        corridor_stops=["stop_b"],
    )
    snapshot: dict[str, Any] = {
        "bus": {
            "arrivals": [
                {
                    "stop_id": "stop_a",
                    "stop_name": "Alpha Station",
                    "line": "M15",
                    "vehicle_id": "BUS_01",
                    "destination": "Downtown",
                    "countdown_seconds": 180,
                },
                {
                    "stop_id": "stop_b",
                    "stop_name": "Beta Station",
                    "line": "M15",
                    "vehicle_id": "BUS_01",
                    "destination": "Downtown",
                    "countdown_seconds": 60,
                },
            ],
            "line_status": {"status": "Good Service"},
        }
    }

    telemetry = extract_snapshot_telemetry(
        provider=provider, route=route, snapshot=snapshot
    )
    assert telemetry.route_id == "sample_bus"
    assert len(telemetry.departures) == 1
    assert telemetry.active_vehicle_id == "BUS_01"
    assert telemetry.line_status is not None
    assert telemetry.line_status.status_label == "Good Service"
    assert "stop_b" in telemetry.corridor_departures
    assert telemetry.stop_names.get("stop_a") == "Alpha"
    assert telemetry.stop_names.get("stop_b") == "Beta"


@pytest.mark.asyncio
async def test_template_provider_async_methods() -> None:
    """Verify TemplateTransitProvider default implementations return valid models."""
    provider = TemplateTransitProvider()
    status = await provider.async_get_line_status("sample_line", TransitMode.BUS)
    # Default fallback without remote connection must be Unknown
    assert status.status_label == "Unknown"
    assert status.status_color == "#757575"
    assert status.status_icon == "mdi:help-circle"

    route = RouteConfig(
        route_id="sample_bus",
        mode=TransitMode.BUS,
        line="sample_line",
        provider="template",
        boarding_walk_seconds=180,
        prep_seconds=60,
        grace_seconds=120,
        boarding_stop="stop_a",
        alighting_stop="stop_b",
    )
    telemetry = await provider.async_get_telemetry(route)
    assert telemetry.route_id == "sample_bus"
    assert telemetry.line_id == "sample_line"
    assert telemetry.mode == TransitMode.BUS
    assert telemetry.line_status is not None
    assert telemetry.line_status.status_label == "Unknown"
