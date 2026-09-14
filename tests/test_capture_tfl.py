"""Unit tests for the TfL fixture capture script."""

import json
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.capture_tfl import (
    BUS_LINE_DEFAULT,
    DEFAULT_TIME_SERIES_COUNT,
    DEFAULT_TIME_SERIES_INTERVAL,
    DEFAULT_TIMEOUT_SECONDS,
    TFL_API_BASE_URL,
    TRAIN_LINE_DEFAULT,
    TUBE_LINE_DEFAULT,
    TfLCaptureClient,
    TransitCaptureError,
    capture_consolidated_bus,
    capture_consolidated_train,
    capture_consolidated_tube,
    capture_poc_bus_discrete,
    capture_poc_train_discrete,
    capture_poc_tube_discrete,
    capture_time_series,
    export_fixture_sets_from_snapshot,
    main,
    parse_arguments,
    save_fixture,
)

SAMPLE_GOOD_STATUS = [{"statusSeverityDescription": "Good Service"}]


def create_mock_response(payload: object) -> MagicMock:
    """Create a mock urllib response context manager.

    :param payload: Data structure to serialise as mock response JSON.
    :return: Mock context manager yielding bytes stream.
    """
    raw_bytes = json.dumps(payload).encode("utf-8")
    mock_context = MagicMock()
    mock_context.__enter__.return_value = BytesIO(raw_bytes)
    mock_context.__exit__.return_value = None
    return mock_context


def test_tfl_client_initialisation_defaults() -> None:
    """Verify default attribute configuration on TfLCaptureClient."""
    client = TfLCaptureClient()
    assert client.base_url == TFL_API_BASE_URL
    assert client.timeout_seconds == DEFAULT_TIMEOUT_SECONDS


def test_fetch_arrivals_success() -> None:
    """Verify successful retrieval of line arrivals."""
    client = TfLCaptureClient()
    expected_data = [{"id": "1", "lineName": "26", "timeToStation": 120}]

    with patch(
        "urllib.request.urlopen", return_value=create_mock_response(expected_data)
    ) as mock_urlopen:
        result = client.fetch_arrivals(line_id="26")
        assert result == expected_data
        assert mock_urlopen.call_count == 1
        request = mock_urlopen.call_args.kwargs["url"]
        assert request.full_url == f"{TFL_API_BASE_URL}/Line/26/Arrivals"


def test_fetch_stop_arrivals_success() -> None:
    """Verify successful retrieval of stop arrivals."""
    client = TfLCaptureClient()
    expected_data = [{"id": "stop_1", "vehicleId": "VEH123"}]

    with patch(
        "urllib.request.urlopen", return_value=create_mock_response(expected_data)
    ) as mock_urlopen:
        result = client.fetch_stop_arrivals(stop_point_id="490013766F")
        assert result == expected_data
        request = mock_urlopen.call_args.kwargs["url"]
        assert request.full_url == f"{TFL_API_BASE_URL}/StopPoint/490013766F/Arrivals"


def test_fetch_line_status_success() -> None:
    """Verify successful retrieval of line status."""
    client = TfLCaptureClient()
    expected_data = [{"id": "26", "statusSeverityDescription": "Good Service"}]

    with patch(
        "urllib.request.urlopen", return_value=create_mock_response(expected_data)
    ) as mock_urlopen:
        result = client.fetch_line_status(line_id="26")
        assert result == expected_data
        request = mock_urlopen.call_args.kwargs["url"]
        assert request.full_url == f"{TFL_API_BASE_URL}/Line/26/Status"


def test_fetch_journey_success() -> None:
    """Verify successful retrieval of journey results."""
    client = TfLCaptureClient()
    expected_data = {"journeys": [{"startDateTime": "2026-09-12T08:00:00"}]}

    with patch(
        "urllib.request.urlopen", return_value=create_mock_response(expected_data)
    ) as mock_urlopen:
        result = client.fetch_journey(
            origin_id="910GCHRX",
            destination_id="910GLNDNBDC",
        )
        assert result == expected_data
        request = mock_urlopen.call_args.kwargs["url"]
        expected_url = (
            f"{TFL_API_BASE_URL}/Journey/JourneyResults/910GCHRX/to/910GLNDNBDC"
            "?mode=national-rail&journeyPreference=LeastInterchange"
        )
        assert request.full_url == expected_url


def test_fetch_journey_pagination_success() -> None:
    """Verify fetch_journey consolidates multiple schedule pages."""
    client = TfLCaptureClient()
    page1 = {
        "journeys": [{"startDateTime": "2026-09-12T08:00:00"}],
        "searchCriteria": {"timeAdjustments": {"later": {"uri": "/Journey/LaterPage"}}},
    }
    page2 = {
        "journeys": [{"startDateTime": "2026-09-12T08:15:00"}],
    }

    mock_responses = [create_mock_response(page1), create_mock_response(page2)]
    with patch("urllib.request.urlopen", side_effect=mock_responses) as mock_urlopen:
        result = client.fetch_journey(
            origin_id="910GCHRX",
            destination_id="910GLNDNBDC",
            max_pages=2,
        )
        assert len(result["journeys"]) == 2
        assert result["journeys"][0]["startDateTime"] == "2026-09-12T08:00:00"
        assert result["journeys"][1]["startDateTime"] == "2026-09-12T08:15:00"
        assert mock_urlopen.call_count == 2


def test_execute_request_http_error() -> None:
    """Verify HTTPError is captured and wrapped into TransitCaptureError."""
    client = TfLCaptureClient()
    mock_error = urllib.error.HTTPError(
        url="https://api.tfl.gov.uk/Line/26/Arrivals",
        code=404,
        msg="Not Found",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=mock_error):
        with pytest.raises(TransitCaptureError) as exc_info:
            client.fetch_arrivals(line_id="26")
        assert "HTTP error 404" in str(exc_info.value)


def test_execute_request_network_error() -> None:
    """Verify URLError is captured and wrapped into TransitCaptureError."""
    client = TfLCaptureClient(max_retries=1)
    mock_error = urllib.error.URLError(reason="Name resolution failure")

    with patch("urllib.request.urlopen", side_effect=mock_error):
        with pytest.raises(TransitCaptureError) as exc_info:
            client.fetch_arrivals(line_id="26")
        assert "Network connection error" in str(exc_info.value)


def test_execute_request_timeout_error() -> None:
    """Verify TimeoutError is captured and wrapped into TransitCaptureError."""
    client = TfLCaptureClient(max_retries=1)
    mock_error = TimeoutError("The read operation timed out")

    with patch("urllib.request.urlopen", side_effect=mock_error):
        with pytest.raises(TransitCaptureError) as exc_info:
            client.fetch_arrivals(line_id="26")
        assert "Timeout error" in str(exc_info.value)


def test_execute_request_invalid_json() -> None:
    """Verify invalid JSON payload raises TransitCaptureError."""
    client = TfLCaptureClient()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = BytesIO(b"Not Valid JSON {")
    mock_context.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_context):
        with pytest.raises(TransitCaptureError) as exc_info:
            client.fetch_arrivals(line_id="26")
        assert "Failed to decode JSON payload" in str(exc_info.value)


def test_save_fixture_creates_file_and_directories(tmp_path: Path) -> None:
    """Verify save_fixture creates parent directory and outputs formatted JSON."""
    target_file = tmp_path / "nested" / "fixtures" / "test.json"
    payload = {"key": "value", "numbers": [1, 2, 3]}

    output_path = save_fixture(payload=payload, destination_path=target_file)
    assert output_path == target_file
    assert target_file.exists()

    loaded = json.loads(target_file.read_text(encoding="utf-8"))
    assert loaded == payload


def test_capture_poc_bus_discrete(tmp_path: Path) -> None:
    """Verify capture_poc_bus_discrete creates all 8 stop fixtures and status."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_stop_arrivals.return_value = [{"id": "arr"}]
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS

    results = capture_poc_bus_discrete(
        client=mock_client,
        output_dir=tmp_path,
        bus_line="26",
    )

    assert len(results) == 10
    assert (tmp_path / "01_terminus_victoria.json").exists()
    assert (tmp_path / "08_target_trafalgar_square.json").exists()
    assert (tmp_path / "09_destination_shoreditch_high_st.json").exists()
    assert (tmp_path / "10_line_status.json").exists()


def test_capture_poc_train_discrete(tmp_path: Path) -> None:
    """Verify capture_poc_train_discrete creates journey and status fixtures."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_journey.return_value = {"journeys": [{"duration": 8}]}
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS

    results = capture_poc_train_discrete(
        client=mock_client,
        output_dir=tmp_path,
        train_line="southeastern",
    )

    assert len(results) == 2
    assert (tmp_path / "01_journey_results.json").exists()
    assert (tmp_path / "02_line_status.json").exists()


def test_capture_consolidated_bus(tmp_path: Path) -> None:
    """Verify capture_consolidated_bus creates unified arrivals and status."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_arrivals.return_value = [{"vehicleId": "VEH1"}]
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS

    results = capture_consolidated_bus(
        client=mock_client,
        output_dir=tmp_path,
        bus_line="26",
    )

    assert len(results) == 2
    assert (tmp_path / "line_arrivals.json").exists()
    assert (tmp_path / "line_status.json").exists()


def test_capture_consolidated_train(tmp_path: Path) -> None:
    """Verify capture_consolidated_train creates journey and status."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_journey.return_value = {"journeys": [{"duration": 8}]}
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS

    results = capture_consolidated_train(
        client=mock_client,
        output_dir=tmp_path,
        train_line="southeastern",
    )

    assert len(results) == 2
    assert (tmp_path / "journey_results.json").exists()
    assert (tmp_path / "line_status.json").exists()


def test_capture_poc_tube_discrete(tmp_path: Path) -> None:
    """Verify capture_poc_tube_discrete creates discrete tube stop fixtures."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_stop_arrivals.return_value = [{"vehicleId": "T1"}]
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS
    mock_client.fetch_journey.return_value = {"journeys": [{"duration": 8}]}

    results = capture_poc_tube_discrete(
        client=mock_client,
        output_dir=tmp_path,
        tube_line="central",
    )

    assert len(results) == 15
    assert (tmp_path / "01_intermediate_north_acton.json").exists()
    assert (tmp_path / "11_intermediate_oxford_circus.json").exists()
    assert (tmp_path / "12_target_tottenham_court_road.json").exists()
    assert (tmp_path / "13_destination_liverpool_street.json").exists()
    assert (tmp_path / "14_line_status.json").exists()
    assert (tmp_path / "15_journey_results.json").exists()


def test_capture_consolidated_tube(tmp_path: Path) -> None:
    """Verify capture_consolidated_tube creates arrivals, journey, and status."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_arrivals.return_value = [{"vehicleId": "T1"}]
    mock_client.fetch_journey.return_value = {"journeys": [{"duration": 8}]}
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS

    results = capture_consolidated_tube(
        client=mock_client,
        output_dir=tmp_path,
        tube_line="central",
    )

    assert len(results) == 3
    assert (tmp_path / "line_arrivals.json").exists()
    assert (tmp_path / "journey_results.json").exists()
    assert (tmp_path / "line_status.json").exists()


def test_capture_time_series(tmp_path: Path) -> None:
    """Verify capture_time_series generates snapshots containing all 3 routes."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_arrivals.return_value = [
        {"vehicleId": "V1"},
        {"vehicleId": "V2"},
    ]
    mock_client.fetch_stop_arrivals.return_value = [{"vehicleId": "V1"}]
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS
    mock_client.fetch_journey.return_value = {"journeys": [{"duration": 8}]}

    manifest_path = capture_time_series(
        client=mock_client,
        output_dir=tmp_path,
        bus_line="26",
        train_line="southeastern",
        tube_line="central",
        iterations=3,
        interval_seconds=0.01,
    )

    assert manifest_path.exists()
    assert (tmp_path / "snapshot_001.json").exists()
    assert (tmp_path / "snapshot_002.json").exists()
    assert (tmp_path / "snapshot_003.json").exists()

    snap1 = json.loads((tmp_path / "snapshot_001.json").read_text(encoding="utf-8"))
    assert "bus" in snap1
    assert "train" in snap1
    assert "tube" in snap1
    assert "discrete_stop_arrivals" in snap1["bus"]
    assert "journey_results" in snap1["train"]
    assert "discrete_stop_arrivals" in snap1["tube"]

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["iterations"] == 3
    assert len(manifest_data["snapshots"]) == 3
    assert manifest_data["bus_line"] == "26"
    assert manifest_data["train_line"] == "southeastern"
    assert manifest_data["tube_line"] == "central"


def test_export_fixture_sets_from_snapshot(tmp_path: Path) -> None:
    """Verify export_fixture_sets_from_snapshot extracts all sets consistently."""
    fake_snapshot = {
        "snapshot_index": 1,
        "elapsed_seconds": 0.0,
        "timestamp": "2026-09-14T12:00:00Z",
        "bus": {
            "line": "26",
            "line_arrivals": [{"vehicleId": "BUS_A", "timeToStation": 100}],
            "line_status": [{"statusSeverityDescription": "Good Service"}],
            "discrete_stop_arrivals": {
                "terminus_victoria": [{"vehicleId": "BUS_A"}],
                "target_trafalgar_square": [{"vehicleId": "BUS_A"}],
            },
        },
        "train": {
            "line": "southeastern",
            "journey_results": {"journeys": [{"duration": 10}]},
            "line_status": [{"statusSeverityDescription": "Good Service"}],
        },
        "tube": {
            "line": "central",
            "line_arrivals": [{"vehicleId": "TUBE_1", "timeToStation": 60}],
            "line_status": [{"statusSeverityDescription": "Good Service"}],
            "journey_results": {"journeys": [{"duration": 12}]},
            "discrete_stop_arrivals": {
                "north_acton": [{"vehicleId": "TUBE_1"}],
                "target_tottenham_court_road": [{"vehicleId": "TUBE_1"}],
            },
        },
    }

    nelson_dir = tmp_path / "commute_nelson_to_brick_lane"
    export_fixture_sets_from_snapshot(
        snapshot_payload=fake_snapshot,
        nelson_dir=nelson_dir,
        fixtures_root=tmp_path,
    )

    # Set 1
    poc_bus_dir = nelson_dir / "set1_poc_bus_discrete"
    assert (poc_bus_dir / "01_terminus_victoria.json").exists()
    assert (poc_bus_dir / "08_target_trafalgar_square.json").exists()
    # Set 2
    assert (nelson_dir / "set2_poc_train_discrete" / "01_journey_results.json").exists()
    # Set 3
    assert (nelson_dir / "set3_consolidated_bus" / "line_arrivals.json").exists()
    # Root mirror
    assert (tmp_path / "tfl_arrivals.json").exists()
    # Set 4
    assert (nelson_dir / "set4_consolidated_train" / "journey_results.json").exists()
    # Set 5
    poc_tube_dir = nelson_dir / "set5_poc_tube_discrete"
    assert (poc_tube_dir / "01_intermediate_north_acton.json").exists()
    assert (poc_tube_dir / "12_target_tottenham_court_road.json").exists()
    # Set 6
    assert (nelson_dir / "set6_consolidated_tube" / "line_arrivals.json").exists()
    assert (nelson_dir / "set6_consolidated_tube" / "journey_results.json").exists()


def test_parse_arguments_defaults() -> None:
    """Verify default CLI argument values."""
    args = parse_arguments(arguments=[])
    assert args.output_dir == Path("tests/fixtures")
    assert args.bus_line == BUS_LINE_DEFAULT
    assert args.train_line == TRAIN_LINE_DEFAULT
    assert args.train_origin == "910GCHRX"
    assert args.train_destination == "910GLNDNBDC"
    assert args.tube_line == TUBE_LINE_DEFAULT
    assert args.tube_origin == "940GZZLUTCR"
    assert args.tube_destination == "940GZZLULVT"
    assert args.time_series_count == DEFAULT_TIME_SERIES_COUNT
    assert args.time_series_interval == DEFAULT_TIME_SERIES_INTERVAL


def test_main_success_flow(tmp_path: Path) -> None:
    """Verify main execution runs full 6-set and time-series capture successfully."""
    mock_client = MagicMock(spec=TfLCaptureClient)
    mock_client.fetch_arrivals.return_value = [{"vehicleId": "V1"}]
    mock_client.fetch_stop_arrivals.return_value = [{"vehicleId": "V1"}]
    mock_client.fetch_line_status.return_value = SAMPLE_GOOD_STATUS
    mock_client.fetch_journey.return_value = {"journeys": [{"duration": 8}]}

    with patch("scripts.capture_tfl.TfLCaptureClient", return_value=mock_client):
        exit_code = main(
            arguments=[
                "--output-dir",
                str(tmp_path),
                "--time-series-count",
                "2",
                "--time-series-interval",
                "0.01",
            ]
        )
        assert exit_code == 0
        nelson_dir = tmp_path / "commute_nelson_to_brick_lane"
        poc_bus = nelson_dir / "set1_poc_bus_discrete"
        assert (poc_bus / "01_terminus_victoria.json").exists()
        assert (poc_bus / "08_target_trafalgar_square.json").exists()
        assert (poc_bus / "10_line_status.json").exists()
        poc_train = nelson_dir / "set2_poc_train_discrete"
        assert (poc_train / "01_journey_results.json").exists()
        assert (nelson_dir / "set3_consolidated_bus" / "line_arrivals.json").exists()
        train_con = nelson_dir / "set4_consolidated_train"
        assert (train_con / "journey_results.json").exists()
        poc_tube = nelson_dir / "set5_poc_tube_discrete"
        assert (poc_tube / "01_intermediate_north_acton.json").exists()
        assert (poc_tube / "12_target_tottenham_court_road.json").exists()
        assert (poc_tube / "15_journey_results.json").exists()
        tube_con = nelson_dir / "set6_consolidated_tube"
        assert (tube_con / "line_arrivals.json").exists()
        assert (nelson_dir / "time_series" / "series_manifest.json").exists()
        assert (tmp_path / "tfl_arrivals.json").exists()


def test_main_handles_transit_capture_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify main traps TransitCaptureError and exits with code 1."""
    with patch(
        "scripts.capture_tfl.capture_time_series",
        side_effect=TransitCaptureError("Outage detected"),
    ):
        exit_code = main(arguments=[])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error capturing transit fixture: Outage detected" in captured.err
