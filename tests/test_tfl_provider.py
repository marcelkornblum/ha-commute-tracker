"""Unit tests for the TfLTransitProvider against static JSON fixtures."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.commute_tracker.corridor import filter_approaching_departures
from custom_components.commute_tracker.models import (
    RouteConfig,
    TransitMode,
)
from custom_components.commute_tracker.providers.tfl import (
    TfLTransitProvider,
    clean_stop_name,
)
from tests.snapshot_adapter import extract_snapshot_telemetry


def test_clean_stop_name() -> None:
    """Verify clean_stop_name removes suffixes and applies friendly mappings."""
    assert clean_stop_name(raw_name="Waterloo Rail Station") == "Waterloo"
    assert clean_stop_name(raw_name="Oxford Circus Station") == "Oxford Circus"
    assert clean_stop_name(raw_name="Southfields Parade") == "Southfields"
    assert (
        clean_stop_name(raw_name="Charing Cross Underground Station") == "Trafalgar Sq"
    )
    assert (
        clean_stop_name(raw_name="Charing Cross Stn  / Trafalgar Square")
        == "Trafalgar Sq"
    )
    assert (
        clean_stop_name(raw_name="Westminster Stn  / Parliament Square")
        == "Westminster"
    )
    assert clean_stop_name(raw_name="Aldgate") == "Aldgate"


@pytest.fixture
def tfl_provider() -> TfLTransitProvider:
    """Return an instantiated TfLTransitProvider."""
    return TfLTransitProvider()


def test_tfl_provider_metadata(tfl_provider: TfLTransitProvider) -> None:
    """Verify TfL provider metadata and supported modes."""
    assert tfl_provider.provider_id == "tfl"
    assert TransitMode.BUS in tfl_provider.supported_modes
    assert TransitMode.TRAIN in tfl_provider.supported_modes
    assert TransitMode.TUBE in tfl_provider.supported_modes
    assert TransitMode.TRAM in tfl_provider.supported_modes


def test_adapt_bus_line_status(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify adapting TfL bus line status from fixture."""
    status_path = nelson_commute_dir / "set3_consolidated_bus" / "line_status.json"
    status_json = json.loads(status_path.read_text(encoding="utf-8"))

    line_status = tfl_provider.adapt_line_status(raw_payload=status_json)
    assert line_status.status_label == "Special Service"
    assert "STRAND, WC2" in (line_status.detail or "")
    assert line_status.status_color != ""
    assert line_status.status_icon.startswith("mdi:")


def test_adapt_line_status_fallback_unknown(tfl_provider: TfLTransitProvider) -> None:
    """Verify adapt_line_status returns Unknown when status data is absent."""
    status_empty_list = tfl_provider.adapt_line_status(raw_payload=[])
    assert status_empty_list.status_label == "Unknown"
    assert status_empty_list.status_color == "#757575"
    assert status_empty_list.status_icon == "mdi:help-circle"
    assert status_empty_list.detail is None

    status_no_statuses = tfl_provider.adapt_line_status(raw_payload={"id": "central"})
    assert status_no_statuses.status_label == "Unknown"
    assert status_no_statuses.status_color == "#757575"
    assert status_no_statuses.status_icon == "mdi:help-circle"


def test_adapt_bus_line_arrivals(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify adapting consolidated bus line arrivals targeting Trafalgar Square."""
    arrivals_path = nelson_commute_dir / "set3_consolidated_bus" / "line_arrivals.json"
    arrivals_json = json.loads(arrivals_path.read_text(encoding="utf-8"))

    target_stop = "490013766F"  # Trafalgar Square
    predictions = tfl_provider.adapt_departures(
        raw_payload=arrivals_json,
        target_stop=target_stop,
    )

    assert len(predictions) > 0
    # Predictions should be sorted ascending by seconds_to_arrival
    assert predictions[0].seconds_to_arrival <= predictions[-1].seconds_to_arrival
    # Each prediction should have vehicle_id, destination, platform_or_bay
    assert predictions[0].vehicle_id is not None
    assert predictions[0].platform_or_bay == "F"
    assert predictions[0].is_realtime is True


def test_adapt_journey(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify adapting rail journey results from Charing Cross to London Bridge."""
    rail_path = nelson_commute_dir / "set4_consolidated_train" / "journey_results.json"
    rail_json = json.loads(rail_path.read_text(encoding="utf-8"))

    predictions = tfl_provider.adapt_journey(
        raw_payload=rail_json,
        origin="910GCHRX",
        destination="910GLNDNBDC",
        reference_time_iso="2026-09-14T12:54:57Z",
    )

    assert len(predictions) > 0
    # Predictions should be sorted by departure time / seconds_to_arrival
    assert predictions[0].expected_time is not None
    destination = predictions[0].destination
    assert "London Bridge" in destination or "Dartford" in destination


def test_adapt_tube_line_arrivals(
    tfl_provider: TfLTransitProvider, nelson_commute_dir: Path
) -> None:
    """Verify adapting tube line arrivals targeting Tottenham Court Road."""
    tube_path = nelson_commute_dir / "set6_consolidated_tube" / "line_arrivals.json"
    tube_json = json.loads(tube_path.read_text(encoding="utf-8"))

    target_stop = "940GZZLUTCR"  # Tottenham Court Road
    predictions = tfl_provider.adapt_departures(
        raw_payload=tube_json,
        target_stop=target_stop,
        line_id="central",
    )

    assert len(predictions) > 0
    assert predictions[0].seconds_to_arrival <= predictions[-1].seconds_to_arrival
    assert predictions[0].vehicle_id is not None


def test_tfl_provider_default_params_injection() -> None:
    """Verify TfL provider attaches credentials from constructor kwargs."""
    provider = TfLTransitProvider(app_id="my_app_id", app_key="my_app_key")
    params = provider.get_default_params()
    assert params["app_id"] == "my_app_id"
    assert params["app_key"] == "my_app_key"


def test_tfl_provider_clean_stop_name_method(tfl_provider: TfLTransitProvider) -> None:
    """Verify clean_stop_name instance method matches module function."""
    assert tfl_provider.clean_stop_name("Victoria Station") == "Victoria"


def test_tfl_provider_telemetry_from_snapshot(
    tfl_provider: TfLTransitProvider,
    snapshot_loader: Callable[[int], dict[str, Any]],
) -> None:
    """Verify converting snapshot 001 into RouteTelemetry for all 3 routes."""
    snapshot = snapshot_loader(1)

    bus_route = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        provider="tfl",
        boarding_walk_seconds=240,
        prep_seconds=120,
        grace_seconds=180,
        boarding_stop="490013766F",
        alighting_stop="490005524F",
        corridor_stops=[
            "490000248H",
            "490014496N",
            "490003384SA",
            "490010260SC",
            "490014495R",
            "490015048A",
            "490008376N",
            "490013766F",
        ],
    )

    telemetry = extract_snapshot_telemetry(
        provider=tfl_provider,
        route=bus_route,
        snapshot=snapshot,
    )
    assert telemetry.route_id == "bus_26"
    assert telemetry.mode == TransitMode.BUS
    assert telemetry.active_vehicle_id == "SN16OJA"
    assert len(telemetry.departures) > 0
    assert telemetry.lead_departure is not None
    assert telemetry.lead_departure.seconds_to_arrival == 326
    assert telemetry.line_status is not None


def test_tfl_provider_telemetry_no_hardcoded_fallbacks(
    tfl_provider: TfLTransitProvider,
    snapshot_loader: Callable[[int], dict[str, Any]],
) -> None:
    """Verify provider does not fall back when stop is unconfigured."""
    snapshot = snapshot_loader(1)

    unconfigured_bus = RouteConfig(
        route_id="bus_unknown",
        mode=TransitMode.BUS,
        line="999",
        boarding_stop="UNKNOWN_STOP_ID",
    )
    telemetry = extract_snapshot_telemetry(
        provider=tfl_provider,
        route=unconfigured_bus,
        snapshot=snapshot,
    )
    assert len(telemetry.departures) == 0
    assert telemetry.active_vehicle_id is None


def test_tfl_provider_tube_corridor_telemetry_extraction(
    tfl_provider: TfLTransitProvider,
    snapshot_loader: Callable[[int], dict[str, Any]],
) -> None:
    """Verify tube telemetry extracts corridor trains without direction flags."""
    snapshot = snapshot_loader(1)

    tube_route = RouteConfig(
        route_id="tube_central",
        mode=TransitMode.TUBE,
        line="central",
        boarding_stop="940GZZLUTCR",
        alighting_stop="940GZZLULVT",
        corridor_stops=[
            "940GZZLUNAN",
            "940GZZLUEAN",
            "940GZZLUWCY",
            "940GZZLUSBC",
            "940GZZLUHPK",
            "940GZZLUNHG",
            "940GZZLUQWY",
            "940GZZLULGT",
            "940GZZLUMBA",
            "940GZZLUBND",
            "940GZZLUOXC",
            "940GZZLUTCR",
        ],
    )
    telemetry = extract_snapshot_telemetry(
        provider=tfl_provider,
        route=tube_route,
        snapshot=snapshot,
    )
    assert len(telemetry.departures) > 0
    assert len(telemetry.corridor_departures) > 0
    assert len(telemetry.stop_names) > 0

    approaching = filter_approaching_departures(
        departures=telemetry.departures,
        corridor_stops=tube_route.corridor_stops,
        corridor_departures=telemetry.corridor_departures,
        boarding_stop=tube_route.boarding_stop,
    )
    assert len(approaching) > 0
    assert approaching[0].vehicle_id == "061"
    assert approaching[0].seconds_to_arrival == 333
    vids = [d.vehicle_id for d in approaching]
    assert "012" in vids
    dep_012 = next(d for d in approaching if d.vehicle_id == "012")
    assert dep_012.seconds_to_arrival == 573
    for dep in approaching:
        assert "Westbound" not in (dep.platform_or_bay or "")


class MockResponse:
    """Mock aiohttp response object for testing."""

    def __init__(self, json_data: Any, status: int = 200) -> None:
        self._json_data = json_data
        self.status = status

    async def __aenter__(self) -> "MockResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=self.status,
            )

    async def json(self) -> Any:
        return self._json_data


class MockSession:
    """Mock aiohttp client session for route URL mapping."""

    def __init__(self, routes_map: dict[str, Any]) -> None:
        self._routes_map = routes_map

    def get(self, url: str, **kwargs: Any) -> MockResponse:
        for key, val in self._routes_map.items():
            if key in url:
                return MockResponse(json_data=val)
        return MockResponse(json_data=[], status=404)


@pytest.mark.asyncio
async def test_tfl_provider_async_get_telemetry_bus(
    nelson_commute_dir: Path,
) -> None:
    """Verify live async bus telemetry fetching, status, and corridor extraction."""
    status_path = nelson_commute_dir / "set3_consolidated_bus" / "line_status.json"
    status_json = json.loads(status_path.read_text(encoding="utf-8"))
    arrivals_path = nelson_commute_dir / "set3_consolidated_bus" / "line_arrivals.json"
    arrivals_json = json.loads(arrivals_path.read_text(encoding="utf-8"))

    mock_session = MockSession(
        routes_map={
            "/Line/26/Status": status_json,
            "/Line/26/Arrivals": arrivals_json,
        }
    )
    provider = TfLTransitProvider(session=mock_session)

    route = RouteConfig(
        route_id="bus_26",
        mode=TransitMode.BUS,
        line="26",
        boarding_stop="490013766F",
        corridor_stops=["490000248H", "490015048A"],
    )

    telemetry = await provider.async_get_telemetry(route=route)

    assert telemetry.route_id == "bus_26"
    assert telemetry.line_status is not None
    assert telemetry.line_status.status_label == "Special Service"
    assert len(telemetry.departures) > 0
    assert len(telemetry.corridor_departures) == 2
    assert "490000248H" in telemetry.corridor_departures
    assert len(telemetry.stop_names) > 0


@pytest.mark.asyncio
async def test_tfl_provider_async_get_telemetry_train(
    nelson_commute_dir: Path,
    freezer: Any,
) -> None:
    """Verify live async train journey fetching and parsing."""
    freezer.move_to("2026-09-14T13:50:00+01:00")
    journey_path = (
        nelson_commute_dir / "set4_consolidated_train" / "journey_results.json"
    )
    journey_json = json.loads(journey_path.read_text(encoding="utf-8"))

    mock_session = MockSession(
        routes_map={
            "/Line/southeastern/Status": [],
            "/Journey/JourneyResults": journey_json,
        }
    )
    provider = TfLTransitProvider(session=mock_session)

    route = RouteConfig(
        route_id="train_se",
        mode=TransitMode.TRAIN,
        line="southeastern",
        boarding_stop="910GCHRX",
        alighting_stop="910GLNDNBDC",
    )

    telemetry = await provider.async_get_telemetry(route=route)

    assert telemetry.route_id == "train_se"
    assert telemetry.line_status is not None
    assert telemetry.line_status.status_label == "Unknown"
    assert len(telemetry.departures) > 0


@pytest.mark.asyncio
async def test_tfl_provider_async_get_telemetry_error_fallback() -> None:
    """Verify provider returns safe fallback telemetry when API throws 404/500."""
    mock_session = MockSession(routes_map={})
    provider = TfLTransitProvider(session=mock_session)

    route = RouteConfig(
        route_id="bus_failing",
        mode=TransitMode.BUS,
        line="999",
        boarding_stop="UNKNOWN_STOP",
    )

    telemetry = await provider.async_get_telemetry(route=route)

    assert telemetry.route_id == "bus_failing"
    assert len(telemetry.departures) == 0
    assert telemetry.line_status is not None
    assert telemetry.line_status.status_label == "Unknown"
