"""Shared test fixtures for the Commute Tracker integration."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in Home Assistant tests."""
    return


@pytest.fixture
def fixtures_root_dir() -> Path:
    """Return path to the root fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def nelson_commute_dir(fixtures_root_dir: Path) -> Path:
    """Return path to the Nelson's Column commute fixtures directory."""
    return fixtures_root_dir / "commute_nelson_to_brick_lane"


@pytest.fixture
def time_series_dir(nelson_commute_dir: Path) -> Path:
    """Return path to the captured time series directory."""
    return nelson_commute_dir / "time_series"


@pytest.fixture
def series_manifest(time_series_dir: Path) -> dict[str, Any]:
    """Load and return the parsed time series manifest."""
    manifest_path = time_series_dir / "series_manifest.json"
    return cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))


@pytest.fixture
def snapshot_loader(time_series_dir: Path) -> Callable[[int], dict[str, Any]]:
    """Return a callable that loads a snapshot by 1-indexed number."""

    def _load(index: int) -> dict[str, Any]:
        snapshot_file = time_series_dir / f"snapshot_{index:03d}.json"
        return cast(
            dict[str, Any], json.loads(snapshot_file.read_text(encoding="utf-8"))
        )

    return _load


@pytest.fixture
def canonical_commute_config() -> dict[str, Any]:
    """Return standard configuration for Nelson's Column to Brick Lane commute."""
    return {
        "commute_id": "nelson_to_brick_lane",
        "commute_title": "Nelson's Column to Brick Lane",
        "person_name": "Commuter",
        "target_arrival_time": "14:45",
        "routes": [
            {
                "id": "bus_26",
                "mode": "bus",
                "line": "26",
                "walk_seconds": 240,
                "prep_seconds": 120,
                "grace_seconds": 180,
                "boarding_stop": "490013766F",
                "destination_stop": "490005524F",
                "in_vehicle_duration_seconds": 1920,
                "alighting_walk_seconds": 600,
                "corridor_stops": [
                    "490000248H",
                    "490014496N",
                    "490003384SA",
                    "490010260SC",
                    "490014495R",
                    "490015048A",
                    "490008376N",
                    "490013766F",
                ],
            },
            {
                "id": "train_southeastern",
                "mode": "train",
                "line": "southeastern",
                "walk_seconds": 240,
                "prep_seconds": 120,
                "grace_seconds": 180,
                "boarding_stop": "910GCHRX",
                "destination_stop": "910GLNDNBDC",
                "in_vehicle_duration_seconds": 480,
                "alighting_walk_seconds": 900,
            },
            {
                "id": "tube_central",
                "mode": "tube",
                "line": "central",
                "walk_seconds": 600,
                "prep_seconds": 120,
                "grace_seconds": 180,
                "boarding_stop": "940GZZLUTCR",
                "destination_stop": "940GZZLULVT",
                "in_vehicle_duration_seconds": 480,
                "alighting_walk_seconds": 480,
                "corridor_stops": [
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
            },
        ],
    }
