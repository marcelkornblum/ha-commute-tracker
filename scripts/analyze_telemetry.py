"""Comprehensive telemetry analysis of multi-route TfL time-series snapshots.

Analyses vehicle progression along the corridor, doorstep leave thresholds,
reachability windows, and rollover events for Bus 26, Southeastern Rail,
and Central Line Tube. Outputs an empirical report to specs/telemetry_analysis.md.
"""

import json
import sys
import zoneinfo
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIME_SERIES_DIR = Path("tests/fixtures/commute_nelson_to_brick_lane/time_series")
OUTPUT_REPORT = Path("specs/telemetry_analysis.md")

# Bus 26 parameters (Nelson's Column -> Trafalgar Square Stop F)
BUS_WALK_SECONDS = 240  # 4 mins
BUS_PREP_SECONDS = 120  # 2 mins
BUS_BUFFER_SECONDS = BUS_WALK_SECONDS + BUS_PREP_SECONDS  # 360s (6 mins)
BUS_GRACE_SECONDS = 180  # 3 mins grace

# Southeastern Rail parameters (Nelson's Column -> Charing Cross)
TRAIN_WALK_SECONDS = 240  # 4 mins
TRAIN_PREP_SECONDS = 120  # 2 mins
TRAIN_BUFFER_SECONDS = TRAIN_WALK_SECONDS + TRAIN_PREP_SECONDS  # 360s (6 mins)
TRAIN_GRACE_SECONDS = 180  # 3 mins grace

# Central Line Tube parameters (Nelson's Column -> Tottenham Court Road)
TUBE_WALK_SECONDS = 600  # 10 mins
TUBE_PREP_SECONDS = 120  # 2 mins
TUBE_BUFFER_SECONDS = TUBE_WALK_SECONDS + TUBE_PREP_SECONDS  # 720s (12 mins)
TUBE_GRACE_SECONDS = 180  # 3 mins grace

EASTBOUND_DESTINATIONS = {
    "Epping",
    "Epping Underground Station",
    "Hainault",
    "Hainault Underground Station",
    "Loughton",
    "Loughton Underground Station",
    "Woodford",
    "Woodford Underground Station",
    "Newbury Park",
    "Newbury Park Underground Station",
    "Debden",
    "Debden Underground Station",
    "Liverpool Street",
    "Liverpool Street Underground Station",
}


@dataclass
class SnapshotTelemetry:
    """Parsed metrics for a single time-series snapshot across routes."""

    index: int
    elapsed_seconds: float
    timestamp: str

    # Active Bus candidate
    active_bus_id: str | None
    bus_time_to_station: int | None
    bus_leave_in_seconds: int | None
    bus_urgency_stage: str
    bus_next_id: str | None
    bus_next_tts: int | None

    # Active Train candidate
    active_train_departure: str | None
    train_time_to_station: int | None
    train_leave_in_seconds: int | None
    train_urgency_stage: str
    train_destination: str | None

    # Active Tube candidate
    active_tube_id: str | None
    tube_destination: str | None
    tube_time_to_station: int | None
    tube_leave_in_seconds: int | None
    tube_urgency_stage: str
    tube_next_id: str | None
    tube_next_tts: int | None

    # Master Route Rollup
    master_active_option: str
    master_urgency_stage: str


def compute_stage(leave_in_seconds: int | None, grace_seconds: int) -> str:
    """Compute urgency stage based on leave countdown and grace cutoff."""
    if leave_in_seconds is None:
        return "standby"
    if leave_in_seconds > 480:
        return "relaxed"
    if leave_in_seconds > 0:
        return "prepare"
    if leave_in_seconds >= -grace_seconds:
        return "leave_now"
    return "missed"


LONDON_TZ = zoneinfo.ZoneInfo("Europe/London")


def parse_iso_datetime(iso_string: str) -> datetime:
    """Parse ISO formatted timestamp string into UTC-aware datetime object."""
    clean_str = iso_string.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LONDON_TZ)
    return dt.astimezone(timezone.utc)


def calculate_train_tts(departure_iso: str, snapshot_iso: str) -> int:
    """Calculate seconds from snapshot timestamp to train departure."""
    departure_dt = parse_iso_datetime(departure_iso)
    snapshot_dt = parse_iso_datetime(snapshot_iso)
    return int((departure_dt - snapshot_dt).total_seconds())


def analyse_snapshots() -> tuple[list[SnapshotTelemetry], dict[str, Any]]:
    """Parse all snapshots and calculate multi-route telemetry timelines."""
    snapshot_files = sorted(TIME_SERIES_DIR.glob("snapshot_*.json"))
    telemetry_timeline: list[SnapshotTelemetry] = []

    bus_lifecycles: dict[str, dict[str, Any]] = {}
    train_departures_seen: list[dict[str, Any]] = []
    tube_lifecycles: dict[str, dict[str, Any]] = {}

    for path in snapshot_files:
        with path.open("r", encoding="utf-8") as file_handle:
            snap: dict[str, Any] = json.load(file_handle)

        idx: int = snap["snapshot_index"]
        elapsed: float = snap["elapsed_seconds"]
        timestamp: str = snap["timestamp"]

        # 1. Bus 26 arrivals at Trafalgar Square
        bus_arrivals = snap.get("bus", {}).get("discrete_stop_arrivals", {}).get(
            "target_trafalgar_square"
        ) or snap.get("bus_corridor_stop_arrivals", {}).get(
            "target_trafalgar_square", []
        )
        sorted_buses = sorted(bus_arrivals, key=lambda x: x.get("timeToStation", 9999))

        active_bus: dict[str, Any] | None = None
        next_bus: dict[str, Any] | None = None

        for item in sorted_buses:
            vid = item.get("vehicleId")
            tts = item.get("timeToStation", 0)
            leave_in = tts - BUS_BUFFER_SECONDS
            if vid not in bus_lifecycles:
                bus_lifecycles[vid] = {
                    "first_seen_snap": idx,
                    "first_seen_tts": tts,
                    "last_seen_snap": idx,
                    "last_seen_tts": tts,
                    "min_tts": tts,
                    "snapshots": [],
                }
            bus_lifecycles[vid]["last_seen_snap"] = idx
            bus_lifecycles[vid]["last_seen_tts"] = tts
            bus_lifecycles[vid]["min_tts"] = min(bus_lifecycles[vid]["min_tts"], tts)
            bus_lifecycles[vid]["snapshots"].append((idx, elapsed, tts))

            if active_bus is None:
                if leave_in >= -BUS_GRACE_SECONDS:
                    active_bus = item
            elif next_bus is None:
                next_bus = item

        active_bus_id = active_bus.get("vehicleId") if active_bus else None
        bus_tts = active_bus.get("timeToStation") if active_bus else None
        bus_leave_in = bus_tts - BUS_BUFFER_SECONDS if bus_tts is not None else None
        bus_stage = compute_stage(bus_leave_in, BUS_GRACE_SECONDS)
        next_bus_id = next_bus.get("vehicleId") if next_bus else None
        next_bus_tts = next_bus.get("timeToStation") if next_bus else None

        # 2. Southeastern Rail Journeys
        train_journeys = snap.get("train", {}).get("journey_results", {}).get(
            "journeys", []
        ) or snap.get("train_journey_results", {}).get("journeys", [])

        active_train: dict[str, Any] | None = None
        for journey in train_journeys:
            start_iso = journey.get("startDateTime")
            if not start_iso:
                continue
            tts = calculate_train_tts(departure_iso=start_iso, snapshot_iso=timestamp)
            leave_in = tts - TRAIN_BUFFER_SECONDS
            if leave_in >= -TRAIN_GRACE_SECONDS:
                active_train = journey
                break

        train_departure: str | None = None
        train_tts: int | None = None
        train_leave_in: int | None = None
        train_stage: str = "standby"
        train_destination: str | None = None

        if active_train:
            train_departure = active_train.get("startDateTime")
            if train_departure:
                train_tts = calculate_train_tts(
                    departure_iso=train_departure, snapshot_iso=timestamp
                )
                train_leave_in = train_tts - TRAIN_BUFFER_SECONDS
                train_stage = compute_stage(train_leave_in, TRAIN_GRACE_SECONDS)
            legs = active_train.get("legs", [])
            if legs:
                train_destination = legs[0].get("instruction", {}).get("summary")

        if train_departure and not any(
            t["departure"] == train_departure for t in train_departures_seen
        ):
            train_departures_seen.append(
                {
                    "departure": train_departure,
                    "first_seen_snap": idx,
                    "destination": train_destination,
                }
            )

        # 3. Central Line Tube arrivals at Tottenham Court Road (Eastbound)
        tube_arrivals = snap.get("tube", {}).get("discrete_stop_arrivals", {}).get(
            "target_tottenham_court_road"
        ) or snap.get("tube_corridor_stop_arrivals", {}).get(
            "target_tottenham_court_road", []
        )
        eastbound_tubes = [
            t
            for t in tube_arrivals
            if t.get("destinationName") in EASTBOUND_DESTINATIONS
            or "East" in str(t.get("platformName", ""))
        ]
        sorted_tubes = sorted(
            eastbound_tubes, key=lambda x: x.get("timeToStation", 9999)
        )

        active_tube: dict[str, Any] | None = None
        next_tube: dict[str, Any] | None = None

        for item in sorted_tubes:
            vid = item.get("vehicleId")
            dest = item.get("destinationName")
            tts = item.get("timeToStation", 0)
            loc = item.get("currentLocation", "")
            leave_in = tts - TUBE_BUFFER_SECONDS

            if vid not in tube_lifecycles:
                tube_lifecycles[vid] = {
                    "destination": dest,
                    "first_seen_snap": idx,
                    "first_seen_tts": tts,
                    "first_loc": loc,
                    "last_seen_snap": idx,
                    "last_seen_tts": tts,
                    "last_loc": loc,
                    "min_tts": tts,
                    "snapshots": [],
                }
            tube_lifecycles[vid]["last_seen_snap"] = idx
            tube_lifecycles[vid]["last_seen_tts"] = tts
            tube_lifecycles[vid]["last_loc"] = loc
            tube_lifecycles[vid]["min_tts"] = min(tube_lifecycles[vid]["min_tts"], tts)
            tube_lifecycles[vid]["snapshots"].append((idx, elapsed, tts, loc))

            if active_tube is None:
                if leave_in >= -TUBE_GRACE_SECONDS:
                    active_tube = item
            elif next_tube is None:
                next_tube = item

        active_tube_id = active_tube.get("vehicleId") if active_tube else None
        tube_dest = active_tube.get("destinationName") if active_tube else None
        tube_tts = active_tube.get("timeToStation") if active_tube else None
        tube_leave_in = tube_tts - TUBE_BUFFER_SECONDS if tube_tts is not None else None
        tube_stage = compute_stage(tube_leave_in, TUBE_GRACE_SECONDS)
        next_tube_id = next_tube.get("vehicleId") if next_tube else None
        next_tube_tts = next_tube.get("timeToStation") if next_tube else None

        # 4. Master Route Arbitration
        candidates: list[tuple[str, int, str]] = []
        if bus_leave_in is not None and bus_stage in (
            "leave_now",
            "prepare",
            "relaxed",
        ):
            candidates.append(("bus_26", bus_leave_in, bus_stage))
        if train_leave_in is not None and train_stage in (
            "leave_now",
            "prepare",
            "relaxed",
        ):
            candidates.append(("train_southeastern", train_leave_in, train_stage))
        if tube_leave_in is not None and tube_stage in (
            "leave_now",
            "prepare",
            "relaxed",
        ):
            candidates.append(("tube_central", tube_leave_in, tube_stage))

        if candidates:
            leave_now_cands = [c for c in candidates if c[2] == "leave_now"]
            if leave_now_cands:
                best_cand = max(leave_now_cands, key=lambda c: c[1])
                master_option = best_cand[0]
                master_stage = best_cand[2]
            else:
                best_cand = min(candidates, key=lambda c: c[1])
                master_option = best_cand[0]
                master_stage = best_cand[2]
        else:
            master_option = "none"
            master_stage = "standby"

        telemetry_timeline.append(
            SnapshotTelemetry(
                index=idx,
                elapsed_seconds=elapsed,
                timestamp=timestamp,
                active_bus_id=active_bus_id,
                bus_time_to_station=bus_tts,
                bus_leave_in_seconds=bus_leave_in,
                bus_urgency_stage=bus_stage,
                bus_next_id=next_bus_id,
                bus_next_tts=next_bus_tts,
                active_train_departure=train_departure,
                train_time_to_station=train_tts,
                train_leave_in_seconds=train_leave_in,
                train_urgency_stage=train_stage,
                train_destination=train_destination,
                active_tube_id=active_tube_id,
                tube_destination=tube_dest,
                tube_time_to_station=tube_tts,
                tube_leave_in_seconds=tube_leave_in,
                tube_urgency_stage=tube_stage,
                tube_next_id=next_tube_id,
                tube_next_tts=next_tube_tts,
                master_active_option=master_option,
                master_urgency_stage=master_stage,
            )
        )

    summary_metadata = {
        "total_snapshots": len(telemetry_timeline),
        "bus_lifecycles": bus_lifecycles,
        "train_departures": train_departures_seen,
        "tube_lifecycles": tube_lifecycles,
    }
    return telemetry_timeline, summary_metadata


def generate_markdown_report(
    timeline: list[SnapshotTelemetry], metadata: dict[str, Any]
) -> str:
    """Format analysis into an exhaustive markdown document."""
    lines: list[str] = [
        "# Detailed Telemetry & Reachability Analysis: Multi-Route Live Capture",
        "",
        "Empirical analysis of the time-series snapshots captured across "
        "the canonical Nelson's Column to Brick Lane commute corridor.",
        "",
        "---",
        "",
        "## 1. Executive Summary & Key Milestones",
        "",
        (
            f"- **Dataset Duration**: {len(timeline)} snapshots "
            "at 30.0s intervals spanning ~45 minutes."
        ),
        (
            "- **Bus 26 (Trafalgar Square Stop F `490013766F`)**: "
            f"{len(metadata['bus_lifecycles'])} distinct vehicles tracked."
        ),
        (
            "- **Southeastern Rail (Charing Cross `910GCHRX`)**: "
            f"{len(metadata['train_departures'])} distinct departures tracked."
        ),
        (
            "- **Central Line Tube (Tottenham Court Road `940GZZLUTCR`)**: "
            f"{len(metadata['tube_lifecycles'])} distinct services tracked."
        ),
        "",
        "---",
        "",
        "## 2. Bus 26 Fleet Tracking & Lifecycles",
        "",
        "| Vehicle ID | First Seen | Initial TTS | Min TTS | Last Seen | Final TTS |",
        "|:-----------|:-----------|:------------|:--------|:----------|:----------|",
    ]

    for vid, data in metadata["bus_lifecycles"].items():
        lines.append(
            f"| `{vid}` | Snap {data['first_seen_snap']} | "
            f"{data['first_seen_tts']}s | {data['min_tts']}s | "
            f"Snap {data['last_seen_snap']} | {data['last_seen_tts']}s |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Southeastern Rail Departures",
            "",
            "| Scheduled Departure | First Observed Snap | Destination / Line |",
            "|:--------------------|:--------------------|:-------------------|",
        ]
    )

    for train in metadata["train_departures"]:
        lines.append(
            f"| `{train['departure']}` | Snap {train['first_seen_snap']} | "
            f"{train['destination'] or 'Southeastern to London Bridge'} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Central Line Underground Progression",
            "",
            (
                "| Train Set ID | Destination | Initial Location | "
                "Initial TTS | Final Location | Last Seen |"
            ),
            (
                "|:-------------|:------------|:-----------------|"
                ":------------|:---------------|:----------|"
            ),
        ]
    )

    for vid, data in list(metadata["tube_lifecycles"].items())[:15]:
        lines.append(
            f"| `{vid}` | {data['destination']} | {data['first_loc']} | "
            f"{data['first_seen_tts']}s | {data['last_loc']} | "
            f"Snap {data['last_seen_snap']} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Master Rollup Arbitration Timeline (Every 5th Snapshot)",
            "",
            (
                "| Snap | Elapsed | Bus Active | Train Departure | "
                "Tube Active | Master Route | Master Stage |"
            ),
            (
                "|:-----|:--------|:-----------|:----------------|"
                ":------------|:-------------|:-------------|"
            ),
        ]
    )

    for t in timeline[::5]:
        bus_info = (
            f"`{t.active_bus_id}` ({t.bus_time_to_station}s / {t.bus_urgency_stage})"
            if t.active_bus_id
            else "None"
        )
        train_info = (
            f"`{t.active_train_departure}` "
            f"({t.train_time_to_station}s / {t.train_urgency_stage})"
            if t.active_train_departure
            else "None"
        )
        tube_info = (
            f"`{t.active_tube_id}` ({t.tube_time_to_station}s / {t.tube_urgency_stage})"
            if t.active_tube_id
            else "None"
        )
        lines.append(
            f"| {t.index:02d} | {t.elapsed_seconds:5.1f}s | {bus_info} | "
            f"{train_info} | {tube_info} | "
            f"`{t.master_active_option}` | `{t.master_urgency_stage}` |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Execute analysis and write output markdown report."""
    if not TIME_SERIES_DIR.exists():
        print(f"Directory {TIME_SERIES_DIR} does not exist.")
        return 1

    timeline, metadata = analyse_snapshots()
    if not timeline:
        print("No snapshots found to analyse.")
        return 1

    report_content = generate_markdown_report(timeline=timeline, metadata=metadata)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(report_content, encoding="utf-8")
    print(
        f"Report generated successfully: {OUTPUT_REPORT} "
        f"({len(timeline)} snapshots analysed)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
