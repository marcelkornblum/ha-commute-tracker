"""TfL API fixture capture utility.

Provides modular data extraction from Transport for London (TfL) Unified API
endpoints to generate static JSON fixtures for testing. Supports both legacy PoC
discrete stop fixtures, modern consolidated line fixtures, and time-series captures.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TFL_API_BASE_URL = "https://api.tfl.gov.uk"
DEFAULT_USER_AGENT = "HomeAssistant-CommuteTracker-FixtureCapture/1.0"
DEFAULT_TIMEOUT_SECONDS = 15

# Exemplar Commute: Nelson's Column (Trafalgar Square) to Brick Lane (Shoreditch)
BUS_LINE_DEFAULT = "26"  # Daytime line 26 connecting Victoria to Shoreditch
BUS_STOP_1_VICTORIA = "490000248H"  # Victoria Station
BUS_STOP_2_WESTMINSTER_CATHEDRAL = "490014496N"  # Westminster Cathedral
BUS_STOP_3_CITY_HALL = "490003384SA"  # Westminster City Hall
BUS_STOP_4_ST_JAMES = "490010260SC"  # St James's Park Station
BUS_STOP_5_ABBEY = "490014495R"  # Westminster Abbey
BUS_STOP_6_WESTMINSTER = "490015048A"  # Westminster Station
BUS_STOP_7_HORSE_GUARDS = "490008376N"  # Horse Guards Parade
BUS_TARGET_STOP = "490013766F"  # Charing Cross Stn / Trafalgar Square (Boarding)
BUS_DESTINATION_STOP = "490005524F"  # Shoreditch High Street Station (Brick Lane)

# Aliases for backwards compatibility
BUS_TERMINUS_STOP = BUS_STOP_1_VICTORIA
BUS_INTERMEDIATE_1 = BUS_STOP_4_ST_JAMES
BUS_INTERMEDIATE_2 = BUS_STOP_6_WESTMINSTER
BUS_INTERMEDIATE_3 = BUS_STOP_7_HORSE_GUARDS

TRAIN_LINE_DEFAULT = "southeastern"
TRAIN_ORIGIN_STATION = "910GCHRX"  # London Charing Cross Rail Station
TRAIN_DESTINATION_STATION = "910GLNDNBDC"  # London Bridge Rail Station

# Non-Terminus Rail/Tube Option: Central Line (Tottenham Court Road to Liverpool Street)
TUBE_LINE_DEFAULT = "central"
TUBE_ORIGIN_STATION = (
    "940GZZLUTCR"  # Tottenham Court Road Underground Station (Boarding)
)
TUBE_DESTINATION_STATION = (
    "940GZZLULVT"  # Liverpool Street Underground Station (Brick Lane)
)
TUBE_STOP_1_NORTH_ACTON = "940GZZLUNAN"
TUBE_STOP_2_EAST_ACTON = "940GZZLUEAN"
TUBE_STOP_3_WHITE_CITY = "940GZZLUWCY"
TUBE_STOP_4_SHEPHERDS_BUSH = "940GZZLUSBC"
TUBE_STOP_5_HOLLAND_PARK = "940GZZLUHPK"
TUBE_STOP_6_NOTTING_HILL_GATE = "940GZZLUNHG"
TUBE_STOP_7_QUEENSWAY = "940GZZLUQWY"
TUBE_STOP_8_LANCASTER_GATE = "940GZZLULGT"
TUBE_STOP_9_MARBLE_ARCH = "940GZZLUMBA"
TUBE_STOP_10_BOND_STREET = "940GZZLUBND"
TUBE_STOP_11_OXFORD_CIRCUS = "940GZZLUOXC"

# Aliases for backwards compatibility
TUBE_APPROACH_1 = TUBE_STOP_1_NORTH_ACTON
TUBE_APPROACH_2 = TUBE_STOP_3_WHITE_CITY
TUBE_APPROACH_3 = TUBE_STOP_6_NOTTING_HILL_GATE
TUBE_APPROACH_4 = TUBE_STOP_9_MARBLE_ARCH

DEFAULT_TIME_SERIES_COUNT = 90  # 45 minutes total coverage
DEFAULT_TIME_SERIES_INTERVAL = 30.0  # 30-second polling interval


class TransitCaptureError(RuntimeError):
    """Raised when transit data capture fails."""


class TransitCaptureClient(ABC):
    """Abstract base protocol for modular transit data capture."""

    @abstractmethod
    def fetch_arrivals(self, line_id: str) -> Any:
        """Fetch real-time arrivals for a transit line."""

    @abstractmethod
    def fetch_stop_arrivals(self, stop_point_id: str) -> Any:
        """Fetch real-time arrivals for a stop point."""

    @abstractmethod
    def fetch_line_status(self, line_id: str) -> Any:
        """Fetch service status and disruption details for a line."""

    @abstractmethod
    def fetch_journey(
        self,
        origin_id: str,
        destination_id: str,
        mode: str = "national-rail",
        journey_preference: str = "LeastInterchange",
        max_pages: int = 3,
    ) -> Any:
        """Fetch journey planner results between two stations."""


@dataclass
class TfLCaptureClient(TransitCaptureClient):
    """Transport for London (TfL) Unified API capture client."""

    base_url: str = TFL_API_BASE_URL
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    min_interval_seconds: float = 0.35
    max_retries: int = 4
    _last_request_time: float = 0.0

    def _execute_request(self, endpoint_path: str) -> Any:
        """Execute HTTP GET request against TfL API and return parsed JSON.

        :param endpoint_path: Relative API endpoint path.
        :return: Decoded JSON response payload.
        :raises TransitCaptureError: On network, HTTP, or JSON parsing failure.
        """
        request_url = f"{self.base_url}{endpoint_path}"
        request = urllib.request.Request(
            url=request_url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )

        backoff = 2.0
        for attempt in range(self.max_retries):
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.min_interval_seconds:
                time.sleep(self.min_interval_seconds - elapsed)

            try:
                self._last_request_time = time.monotonic()
                with urllib.request.urlopen(
                    url=request,
                    timeout=self.timeout_seconds,
                ) as response:
                    response_bytes = response.read()
                    return json.loads(response_bytes.decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt < self.max_retries - 1:
                    retry_header = (
                        error.headers.get("Retry-After") if error.headers else None
                    )
                    sleep_time = float(retry_header) if retry_header else backoff
                    print(
                        f"Rate limit hit (HTTP 429) fetching {endpoint_path}; "
                        f"retrying in {sleep_time:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})...",
                        file=sys.stderr,
                    )
                    time.sleep(sleep_time)
                    backoff *= 2
                    continue
                message = (
                    f"HTTP error {error.code} fetching from {request_url}: "
                    f"{error.reason}"
                )
                raise TransitCaptureError(message) from error
            except urllib.error.URLError as error:
                message = (
                    f"Network connection error fetching from {request_url}: "
                    f"{error.reason}"
                )
                raise TransitCaptureError(message) from error
            except json.JSONDecodeError as error:
                message = f"Failed to decode JSON payload from {request_url}: {error}"
                raise TransitCaptureError(message) from error

    def fetch_arrivals(self, line_id: str) -> Any:
        """Fetch unified line arrivals for all stops along a given line.

        :param line_id: Transit line identifier (e.g. '26').
        :return: List of prediction objects.
        """
        return self._execute_request(f"/Line/{line_id}/Arrivals")

    def fetch_stop_arrivals(self, stop_point_id: str) -> Any:
        """Fetch real-time arrivals for a specific stop point.

        :param stop_point_id: NaPTAN / StopPoint ID (e.g. '490013766F').
        :return: List of arrival prediction objects.
        """
        return self._execute_request(f"/StopPoint/{stop_point_id}/Arrivals")

    def fetch_line_status(self, line_id: str) -> Any:
        """Fetch real-time line status and severity description.

        :param line_id: Transit line identifier (e.g. '26' or 'southeastern').
        :return: List of line status objects.
        """
        return self._execute_request(f"/Line/{line_id}/Status")

    def fetch_journey(
        self,
        origin_id: str,
        destination_id: str,
        mode: str = "national-rail",
        journey_preference: str = "LeastInterchange",
        max_pages: int = 3,
    ) -> Any:
        """Fetch journey planner results across forward schedule pages.

        :param origin_id: NaPTAN or station code of journey start.
        :param destination_id: NaPTAN or station code of journey terminus.
        :param mode: Transit mode filter (e.g. 'national-rail').
        :param journey_preference: Routing preference (e.g. 'LeastInterchange').
        :param max_pages: Maximum pagination iterations to follow via later departures.
        :return: Consolidated journey planner payload dictionary.
        """
        endpoint = (
            f"/Journey/JourneyResults/{origin_id}/to/{destination_id}"
            f"?mode={mode}&journeyPreference={journey_preference}"
        )
        first_payload = self._execute_request(endpoint)
        if not isinstance(first_payload, dict) or max_pages <= 1:
            return first_payload

        consolidated = dict(first_payload)
        journeys: list[Any] = list(first_payload.get("journeys", []))

        current_payload = first_payload
        for _ in range(max_pages - 1):
            time_adjustments = (
                current_payload.get("searchCriteria", {})
                .get("timeAdjustments", {})
            )
            later_uri = time_adjustments.get("later", {}).get("uri")
            if not later_uri:
                break
            later_payload = self._execute_request(later_uri)
            if not isinstance(later_payload, dict):
                break
            later_journeys = later_payload.get("journeys", [])
            if not later_journeys:
                break
            journeys.extend(later_journeys)
            current_payload = later_payload

        consolidated["journeys"] = journeys
        return consolidated


@dataclass
class TimeSeriesEntry:
    """Metadata describing a single time-series snapshot."""

    snapshot_index: int
    elapsed_seconds: float
    timestamp_iso: str
    relative_file: str
    vehicle_count: int
    vehicle_ids: list[str]


def save_fixture(payload: Any, destination_path: Path) -> Path:
    """Serialise payload to indented JSON fixture on disk.

    :param payload: JSON-serialisable transit payload.
    :param destination_path: Target filesystem path.
    :return: Resolved target Path.
    """
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    serialised_json = json.dumps(payload, indent=2, sort_keys=True)
    destination_path.write_text(f"{serialised_json}\n", encoding="utf-8")
    return destination_path


def capture_poc_bus_discrete(
    client: TransitCaptureClient,
    output_dir: Path,
    bus_line: str = BUS_LINE_DEFAULT,
) -> dict[str, Path]:
    """Capture discrete stop fixtures matching legacy PoC multi-request pattern.

    :param client: Transit capture client.
    :param output_dir: Directory to store fixtures.
    :param bus_line: Bus line identifier.
    :return: Mapping of fixture keys to saved paths.
    """
    results: dict[str, Path] = {}
    stops = [
        ("01_terminus_victoria", BUS_STOP_1_VICTORIA),
        ("02_intermediate_westminster_cathedral", BUS_STOP_2_WESTMINSTER_CATHEDRAL),
        ("03_intermediate_westminster_city_hall", BUS_STOP_3_CITY_HALL),
        ("04_intermediate_st_james_park", BUS_STOP_4_ST_JAMES),
        ("05_intermediate_westminster_abbey", BUS_STOP_5_ABBEY),
        ("06_intermediate_westminster", BUS_STOP_6_WESTMINSTER),
        ("07_intermediate_horse_guards", BUS_STOP_7_HORSE_GUARDS),
        ("08_target_trafalgar_square", BUS_TARGET_STOP),
        ("09_destination_shoreditch_high_st", BUS_DESTINATION_STOP),
    ]

    for filename, stop_id in stops:
        payload = client.fetch_stop_arrivals(stop_point_id=stop_id)
        path = save_fixture(
            payload=payload, destination_path=output_dir / f"{filename}.json"
        )
        results[filename] = path

    status_payload = client.fetch_line_status(line_id=bus_line)
    status_path = save_fixture(
        payload=status_payload, destination_path=output_dir / "10_line_status.json"
    )
    results["line_status"] = status_path
    return results


def capture_poc_train_discrete(
    client: TransitCaptureClient,
    output_dir: Path,
    train_line: str = TRAIN_LINE_DEFAULT,
    origin_station: str = TRAIN_ORIGIN_STATION,
    destination_station: str = TRAIN_DESTINATION_STATION,
) -> dict[str, Path]:
    """Capture train fixtures matching legacy PoC rail request pattern.

    :param client: Transit capture client.
    :param output_dir: Directory to store fixtures.
    :param train_line: Rail line identifier.
    :param origin_station: Origin station code.
    :param destination_station: Destination station code.
    :return: Mapping of fixture keys to saved paths.
    """
    results: dict[str, Path] = {}

    journey_payload = client.fetch_journey(
        origin_id=origin_station, destination_id=destination_station
    )
    results["journey_results"] = save_fixture(
        payload=journey_payload, destination_path=output_dir / "01_journey_results.json"
    )

    status_payload = client.fetch_line_status(line_id=train_line)
    results["line_status"] = save_fixture(
        payload=status_payload, destination_path=output_dir / "02_line_status.json"
    )
    return results


def capture_consolidated_bus(
    client: TransitCaptureClient,
    output_dir: Path,
    bus_line: str = BUS_LINE_DEFAULT,
) -> dict[str, Path]:
    """Capture consolidated bus fixtures with minimal API calls.

    :param client: Transit capture client.
    :param output_dir: Directory to store fixtures.
    :param bus_line: Bus line identifier.
    :return: Mapping of fixture keys to saved paths.
    """
    results: dict[str, Path] = {}
    arrivals = client.fetch_arrivals(line_id=bus_line)
    results["line_arrivals"] = save_fixture(
        payload=arrivals, destination_path=output_dir / "line_arrivals.json"
    )

    status = client.fetch_line_status(line_id=bus_line)
    results["line_status"] = save_fixture(
        payload=status, destination_path=output_dir / "line_status.json"
    )
    return results


def capture_consolidated_train(
    client: TransitCaptureClient,
    output_dir: Path,
    train_line: str = TRAIN_LINE_DEFAULT,
    origin_station: str = TRAIN_ORIGIN_STATION,
    destination_station: str = TRAIN_DESTINATION_STATION,
) -> dict[str, Path]:
    """Capture consolidated train fixtures.

    :param client: Transit capture client.
    :param output_dir: Directory to store fixtures.
    :param train_line: Rail line identifier.
    :param origin_station: Origin station code.
    :param destination_station: Destination station code.
    :return: Mapping of fixture keys to saved paths.
    """
    results: dict[str, Path] = {}
    journey = client.fetch_journey(
        origin_id=origin_station, destination_id=destination_station
    )
    results["journey_results"] = save_fixture(
        payload=journey, destination_path=output_dir / "journey_results.json"
    )

    status = client.fetch_line_status(line_id=train_line)
    results["line_status"] = save_fixture(
        payload=status, destination_path=output_dir / "line_status.json"
    )
    return results


def capture_poc_tube_discrete(
    client: TransitCaptureClient,
    output_dir: Path,
    tube_line: str = TUBE_LINE_DEFAULT,
    origin_station: str = TUBE_ORIGIN_STATION,
    destination_station: str = TUBE_DESTINATION_STATION,
) -> dict[str, Path]:
    """Capture discrete tube station fixtures for non-terminus corridor testing.

    :param client: Transit capture client.
    :param output_dir: Directory to store fixtures.
    :param tube_line: Underground line identifier.
    :param origin_station: Boarding station code.
    :param destination_station: Destination station code.
    :return: Mapping of fixture keys to saved paths.
    """
    results: dict[str, Path] = {}
    stops = [
        ("01_intermediate_north_acton", TUBE_STOP_1_NORTH_ACTON),
        ("02_intermediate_east_acton", TUBE_STOP_2_EAST_ACTON),
        ("03_intermediate_white_city", TUBE_STOP_3_WHITE_CITY),
        ("04_intermediate_shepherds_bush", TUBE_STOP_4_SHEPHERDS_BUSH),
        ("05_intermediate_holland_park", TUBE_STOP_5_HOLLAND_PARK),
        ("06_intermediate_notting_hill_gate", TUBE_STOP_6_NOTTING_HILL_GATE),
        ("07_intermediate_queensway", TUBE_STOP_7_QUEENSWAY),
        ("08_intermediate_lancaster_gate", TUBE_STOP_8_LANCASTER_GATE),
        ("09_intermediate_marble_arch", TUBE_STOP_9_MARBLE_ARCH),
        ("10_intermediate_bond_street", TUBE_STOP_10_BOND_STREET),
        ("11_intermediate_oxford_circus", TUBE_STOP_11_OXFORD_CIRCUS),
        ("12_target_tottenham_court_road", origin_station),
        ("13_destination_liverpool_street", destination_station),
    ]

    for filename, stop_id in stops:
        payload = client.fetch_stop_arrivals(stop_point_id=stop_id)
        path = save_fixture(
            payload=payload, destination_path=output_dir / f"{filename}.json"
        )
        results[filename] = path

    status_payload = client.fetch_line_status(line_id=tube_line)
    results["line_status"] = save_fixture(
        payload=status_payload, destination_path=output_dir / "14_line_status.json"
    )

    journey_payload = client.fetch_journey(
        origin_id=origin_station,
        destination_id=destination_station,
        mode="tube",
    )
    results["journey_results"] = save_fixture(
        payload=journey_payload, destination_path=output_dir / "15_journey_results.json"
    )
    return results


def capture_consolidated_tube(
    client: TransitCaptureClient,
    output_dir: Path,
    tube_line: str = TUBE_LINE_DEFAULT,
    origin_station: str = TUBE_ORIGIN_STATION,
    destination_station: str = TUBE_DESTINATION_STATION,
) -> dict[str, Path]:
    """Capture consolidated tube fixtures with minimal API calls.

    :param client: Transit capture client.
    :param output_dir: Directory to store fixtures.
    :param tube_line: Underground line identifier.
    :param origin_station: Boarding station code.
    :param destination_station: Destination station code.
    :return: Mapping of fixture keys to saved paths.
    """
    results: dict[str, Path] = {}
    arrivals = client.fetch_arrivals(line_id=tube_line)
    results["line_arrivals"] = save_fixture(
        payload=arrivals, destination_path=output_dir / "line_arrivals.json"
    )

    journey = client.fetch_journey(
        origin_id=origin_station,
        destination_id=destination_station,
        mode="tube",
    )
    results["journey_results"] = save_fixture(
        payload=journey, destination_path=output_dir / "journey_results.json"
    )

    status = client.fetch_line_status(line_id=tube_line)
    results["line_status"] = save_fixture(
        payload=status, destination_path=output_dir / "line_status.json"
    )
    return results


def capture_time_series(
    client: TransitCaptureClient,
    output_dir: Path,
    bus_line: str = BUS_LINE_DEFAULT,
    tube_line: str = TUBE_LINE_DEFAULT,
    iterations: int = DEFAULT_TIME_SERIES_COUNT,
    interval_seconds: float = DEFAULT_TIME_SERIES_INTERVAL,
) -> Path:
    """Capture a time-series sequence of corridor snapshots at regular intervals.

    :param client: Transit capture client.
    :param output_dir: Directory to store snapshots.
    :param bus_line: Bus line identifier.
    :param tube_line: Tube line identifier.
    :param iterations: Number of snapshot iterations.
    :param interval_seconds: Delay between snapshots.
    :return: Path to generated manifest file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_entries: list[TimeSeriesEntry] = []
    start_time = time.monotonic()

    bus_corridor_stops = {
        "terminus_victoria": BUS_STOP_1_VICTORIA,
        "westminster_cathedral": BUS_STOP_2_WESTMINSTER_CATHEDRAL,
        "westminster_city_hall": BUS_STOP_3_CITY_HALL,
        "st_james_park": BUS_STOP_4_ST_JAMES,
        "westminster_abbey": BUS_STOP_5_ABBEY,
        "westminster": BUS_STOP_6_WESTMINSTER,
        "horse_guards": BUS_STOP_7_HORSE_GUARDS,
        "target_trafalgar_square": BUS_TARGET_STOP,
        "destination_shoreditch": BUS_DESTINATION_STOP,
    }
    tube_corridor_stops = {
        "north_acton": TUBE_STOP_1_NORTH_ACTON,
        "east_acton": TUBE_STOP_2_EAST_ACTON,
        "white_city": TUBE_STOP_3_WHITE_CITY,
        "shepherds_bush": TUBE_STOP_4_SHEPHERDS_BUSH,
        "holland_park": TUBE_STOP_5_HOLLAND_PARK,
        "notting_hill_gate": TUBE_STOP_6_NOTTING_HILL_GATE,
        "queensway": TUBE_STOP_7_QUEENSWAY,
        "lancaster_gate": TUBE_STOP_8_LANCASTER_GATE,
        "marble_arch": TUBE_STOP_9_MARBLE_ARCH,
        "bond_street": TUBE_STOP_10_BOND_STREET,
        "oxford_circus": TUBE_STOP_11_OXFORD_CIRCUS,
        "target_tottenham_court_road": TUBE_ORIGIN_STATION,
        "destination_liverpool_street": TUBE_DESTINATION_STATION,
    }

    for index in range(1, iterations + 1):
        timestamp_now = datetime.now(timezone.utc)
        elapsed = round(time.monotonic() - start_time, 1)
        iso_str = timestamp_now.isoformat()
        file_name = f"snapshot_{index:03d}.json"

        bus_arrivals = client.fetch_arrivals(line_id=bus_line)
        tube_arrivals = client.fetch_arrivals(line_id=tube_line)

        bus_stop_predictions: dict[str, Any] = {}
        for stop_key, stop_id in bus_corridor_stops.items():
            if isinstance(bus_arrivals, list):
                bus_stop_predictions[stop_key] = [
                    item
                    for item in bus_arrivals
                    if isinstance(item, dict) and item.get("naptanId") == stop_id
                ]
            else:
                bus_stop_predictions[stop_key] = client.fetch_stop_arrivals(
                    stop_point_id=stop_id
                )

        tube_stop_predictions: dict[str, Any] = {}
        for stop_key, stop_id in tube_corridor_stops.items():
            if isinstance(tube_arrivals, list):
                tube_stop_predictions[stop_key] = [
                    item
                    for item in tube_arrivals
                    if isinstance(item, dict) and item.get("naptanId") == stop_id
                ]
            else:
                tube_stop_predictions[stop_key] = client.fetch_stop_arrivals(
                    stop_point_id=stop_id
                )

        snapshot_payload = {
            "snapshot_index": index,
            "elapsed_seconds": elapsed,
            "timestamp": iso_str,
            "bus_line": bus_line,
            "tube_line": tube_line,
            "bus_line_arrivals": bus_arrivals,
            "bus_corridor_stop_arrivals": bus_stop_predictions,
            "tube_line_arrivals": tube_arrivals,
            "tube_corridor_stop_arrivals": tube_stop_predictions,
            # Top-level aliases for backwards compatibility
            "line": bus_line,
            "line_arrivals": bus_arrivals,
            "corridor_stop_arrivals": bus_stop_predictions,
        }

        save_fixture(
            payload=snapshot_payload,
            destination_path=output_dir / file_name,
        )

        vehicles: set[str] = set()
        if isinstance(bus_arrivals, list):
            for item in bus_arrivals:
                if isinstance(item, dict) and "vehicleId" in item:
                    vehicles.add(str(item["vehicleId"]))
        if isinstance(tube_arrivals, list):
            for item in tube_arrivals:
                if isinstance(item, dict) and "vehicleId" in item:
                    vehicles.add(str(item["vehicleId"]))

        manifest_entries.append(
            TimeSeriesEntry(
                snapshot_index=index,
                elapsed_seconds=elapsed,
                timestamp_iso=iso_str,
                relative_file=file_name,
                vehicle_count=len(vehicles),
                vehicle_ids=sorted(vehicles),
            )
        )

        if index < iterations:
            time.sleep(interval_seconds)

    manifest_payload = {
        "bus_line": bus_line,
        "tube_line": tube_line,
        "line": bus_line,
        "iterations": iterations,
        "interval_seconds": interval_seconds,
        "total_duration_seconds": round(time.monotonic() - start_time, 1),
        "snapshots": [asdict(entry) for entry in manifest_entries],
    }

    manifest_path = output_dir / "series_manifest.json"
    save_fixture(payload=manifest_payload, destination_path=manifest_path)
    return manifest_path


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the capture script.

    :param arguments: Command-line arguments list or None for sys.argv.
    :return: Parsed namespace.
    """
    parser = argparse.ArgumentParser(
        description="Capture TfL live transit payloads for testing fixtures."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="Root directory for fixture outputs",
    )
    parser.add_argument(
        "--bus-line",
        default=BUS_LINE_DEFAULT,
        help=f"Bus line identifier (default: '{BUS_LINE_DEFAULT}')",
    )
    parser.add_argument(
        "--train-line",
        default=TRAIN_LINE_DEFAULT,
        help=f"Train line identifier (default: '{TRAIN_LINE_DEFAULT}')",
    )
    parser.add_argument(
        "--tube-line",
        default=TUBE_LINE_DEFAULT,
        help=f"Underground line identifier (default: '{TUBE_LINE_DEFAULT}')",
    )
    parser.add_argument(
        "--time-series-count",
        type=int,
        default=DEFAULT_TIME_SERIES_COUNT,
        help=(
            "Snapshots to capture in time-series "
            f"(default: {DEFAULT_TIME_SERIES_COUNT})"
        ),
    )
    parser.add_argument(
        "--time-series-interval",
        type=float,
        default=DEFAULT_TIME_SERIES_INTERVAL,
        help=(
            "Interval between snapshots in seconds "
            f"(default: {DEFAULT_TIME_SERIES_INTERVAL})"
        ),
    )
    return parser.parse_args(args=arguments)


def main(arguments: list[str] | None = None) -> int:
    """Entrypoint executing comprehensive fixture capture.

    :param arguments: Command-line arguments list or None for sys.argv.
    :return: Exit code.
    """
    args = parse_arguments(arguments=arguments)
    client = TfLCaptureClient()
    fixtures_root: Path = args.output_dir
    nelson_dir = fixtures_root / "commute_nelson_to_brick_lane"

    try:
        print("Capturing Set 1: PoC Bus Discrete stops...")
        capture_poc_bus_discrete(
            client=client,
            output_dir=nelson_dir / "set1_poc_bus_discrete",
            bus_line=args.bus_line,
        )

        print("Capturing Set 2: PoC Train Discrete...")
        capture_poc_train_discrete(
            client=client,
            output_dir=nelson_dir / "set2_poc_train_discrete",
            train_line=args.train_line,
        )

        print("Capturing Set 3: Consolidated Bus...")
        capture_consolidated_bus(
            client=client,
            output_dir=nelson_dir / "set3_consolidated_bus",
            bus_line=args.bus_line,
        )

        # Mirror root tfl_arrivals.json for backwards compatibility
        arrivals_payload = client.fetch_arrivals(line_id=args.bus_line)
        save_fixture(
            payload=arrivals_payload,
            destination_path=fixtures_root / "tfl_arrivals.json",
        )

        print("Capturing Set 4: Consolidated Train...")
        capture_consolidated_train(
            client=client,
            output_dir=nelson_dir / "set4_consolidated_train",
            train_line=args.train_line,
        )

        print("Capturing Set 5: PoC Tube Discrete...")
        capture_poc_tube_discrete(
            client=client,
            output_dir=nelson_dir / "set5_poc_tube_discrete",
            tube_line=args.tube_line,
        )

        print("Capturing Set 6: Consolidated Tube...")
        capture_consolidated_tube(
            client=client,
            output_dir=nelson_dir / "set6_consolidated_tube",
            tube_line=args.tube_line,
        )

        print(
            f"Capturing Time Series ({args.time_series_count} iterations, "
            f"interval {args.time_series_interval}s)..."
        )
        capture_time_series(
            client=client,
            output_dir=nelson_dir / "time_series",
            bus_line=args.bus_line,
            tube_line=args.tube_line,
            iterations=args.time_series_count,
            interval_seconds=args.time_series_interval,
        )

        print("All fixture sets and time series successfully captured and saved!")
        return 0

    except TransitCaptureError as error:
        print(f"Error capturing transit fixture: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
