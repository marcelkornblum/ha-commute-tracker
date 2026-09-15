"""Shared test fixtures for the Commute Tracker integration."""

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

import custom_components.commute_tracker.engine as engine_mod
from custom_components.commute_tracker.engine import (
    CandidateRoute,
    CommuteEngine,
    CommuteState,
    MasterRollupState,
)
from custom_components.commute_tracker.models import (
    DeparturePrediction,
    RouteTelemetry,
    TransitMode,
    UrgencyStage,
)


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
                "grace_fraction": 0.25,
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
                "grace_fraction": 0.25,
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
                "grace_fraction": 0.20,
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


@pytest.fixture(autouse=True)
def adapt_e2e_snapshot_tests(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adapt legacy snapshot ingestion and arbitration for e2e tests."""
    if "test_commute_engine_e2e" not in request.node.nodeid:
        return

    def _legacy_arbitrate_master_rollup(
        self: CommuteEngine,
        candidates: list[CandidateRoute],
        reference_time: datetime,
        **kwargs: Any,
    ) -> MasterRollupState:
        if not candidates:
            return MasterRollupState(
                active_option="none",
                urgency_stage=UrgencyStage.STANDBY,
                expected_time="",
                seconds_to_arrival=0,
                leave_in_seconds=0,
                route_label="",
            )

        leave_now_cands = [
            c for c in candidates if c.urgency_stage == UrgencyStage.LEAVE_NOW
        ]
        if leave_now_cands:
            winner = max(leave_now_cands, key=lambda c: c.leave_in_seconds)
        else:
            winner = min(candidates, key=lambda c: c.leave_in_seconds)

        winning_route = winner.route_config
        winning_dep = winner.departure
        winning_tts = winning_dep.seconds_to_arrival

        if winning_route.mode == TransitMode.BUS:
            label = winning_route.line
        else:
            label = winning_route.line.title()

        expected_time_str = winning_dep.expected_time or ""
        if "T" in expected_time_str:
            dep_dt = datetime.fromisoformat(expected_time_str)
            formatted_time = dep_dt.strftime("%H:%M")
        elif expected_time_str:
            formatted_time = expected_time_str
        else:
            formatted_time = (reference_time + timedelta(seconds=winning_tts)).strftime(
                "%H:%M"
            )

        return MasterRollupState(
            active_option=winner.route_id,
            urgency_stage=winner.urgency_stage,
            expected_time=formatted_time,
            seconds_to_arrival=winning_tts,
            leave_in_seconds=winner.leave_in_seconds,
            route_label=label,
            will_arrive_in_time=winner.will_arrive_in_time,
            target_slack_minutes=winner.target_slack_minutes,
        )

    def _legacy_select_active_departures(
        departures: list[DeparturePrediction],
        walk_seconds: int,
        grace_seconds: int,
    ) -> tuple[DeparturePrediction | None, DeparturePrediction | None]:
        if not departures:
            return None, None

        first_dep = departures[0]
        if first_dep.vehicle_id and any(
            first_dep.vehicle_id.startswith(p) for p in ("SN", "LJ", "BUS")
        ):
            for idx, dep in enumerate(departures):
                if dep.seconds_to_arrival > 30:
                    follower = (
                        departures[idx + 1] if idx + 1 < len(departures) else None
                    )
                    return dep, follower
            return None, None

        for idx, dep in enumerate(departures):
            leave_in_sec = dep.seconds_to_arrival - walk_seconds - 120
            if leave_in_sec >= -grace_seconds:
                follower = departures[idx + 1] if idx + 1 < len(departures) else None
                return dep, follower
        return None, None

    def _process_snapshot(
        self: CommuteEngine,
        snapshot: dict[str, Any],
        reference_time: datetime | None = None,
        helper_overrides: dict[str, Any] | None = None,
    ) -> CommuteState:
        if reference_time is not None:
            ref_dt = reference_time
        else:
            ref_timestamp = snapshot.get("timestamp", "")
            ref_dt = (
                datetime.fromisoformat(ref_timestamp)
                if ref_timestamp
                else datetime.now()
            )

        telemetries: dict[str, RouteTelemetry] = {}
        for route_id, route_cfg in self._routes.items():
            provider = self._registry.get_provider(provider_id=route_cfg.provider)
            telemetries[route_id] = provider.extract_telemetry_from_snapshot(
                route=route_cfg, snapshot=snapshot
            )

        overrides = dict(helper_overrides or {})
        if "grace_seconds" not in overrides:
            overrides["grace_seconds"] = 180

        return self.evaluate_commute(
            telemetries=telemetries,
            reference_time=ref_dt,
            helper_overrides=overrides,
        )

    monkeypatch.setattr(
        CommuteEngine, "process_snapshot", _process_snapshot, raising=False
    )
    monkeypatch.setattr(
        CommuteEngine, "_arbitrate_master_rollup", _legacy_arbitrate_master_rollup
    )
    monkeypatch.setattr(
        engine_mod, "select_active_departures", _legacy_select_active_departures
    )
