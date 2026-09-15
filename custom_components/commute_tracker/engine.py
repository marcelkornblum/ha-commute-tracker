"""Pure-Python commute tracking and arbitration engine (Phases 3 and 4).

Ingests multi-modal transit payloads, evaluates corridor vehicle progress,
calculates doorstep leave thresholds, and arbitrates Master Rollup state.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from custom_components.commute_tracker.const import (
    DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
)
from custom_components.commute_tracker.corridor import (
    calculate_corridor_progression,
    filter_approaching_departures,
    select_active_departures,
)
from custom_components.commute_tracker.models import (
    CommuteConfig,
    DeparturePrediction,
    RollupStrategy,
    RouteConfig,
    RouteTelemetry,
    TransitMode,
    UrgencyStage,
)
from custom_components.commute_tracker.providers.base import (
    TransitProviderRegistry,
)
from custom_components.commute_tracker.timeliness import (
    ResolvedThresholds,
    calculate_leave_countdown,
    calculate_target_slack,
    calculate_urgency_stage,
    resolve_route_thresholds,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ChildRouteState:
    """Evaluated runtime state for a single commute child route."""

    route_id: str
    mode: str
    urgency_stage: UrgencyStage = UrgencyStage.STANDBY
    vehicle_id: str | None = None
    scheduled_departure: str | None = None
    seconds_to_arrival: int | None = None
    leave_in_seconds: int | None = None
    corridor_location: str = ""
    corridor_progress: float = 0.0
    next_vehicle_id: str | None = None
    next_seconds_to_arrival: int | None = None
    will_arrive_in_time: bool = True
    target_slack_minutes: int | None = None


@dataclass(slots=True)
class MasterRollupState:
    """Arbitrated runtime state for the master commute sensor."""

    active_option: str
    urgency_stage: UrgencyStage
    expected_time: str
    seconds_to_arrival: int
    leave_in_seconds: int
    route_label: str
    will_arrive_in_time: bool = True
    target_slack_minutes: int = 0
    strategy: RollupStrategy = RollupStrategy.LATE_WITH_BUFFER


@dataclass(slots=True, frozen=True)
class CandidateRoute:
    """Candidate child route evaluated for master sensor arbitration."""

    route_id: str
    leave_in_seconds: int
    urgency_stage: UrgencyStage
    departure: DeparturePrediction
    route_config: RouteConfig
    telemetry: RouteTelemetry
    will_arrive_in_time: bool = True
    target_slack_minutes: int = 0


@dataclass(slots=True)
class CommuteState:
    """Comprehensive snapshot evaluation output containing master and child states."""

    commute_id: str
    master_rollup: MasterRollupState
    child_routes: dict[str, ChildRouteState] = field(default_factory=dict)


class CommuteEngine:
    """Transit evaluation engine orchestrating route calculations and arbitration."""

    process_snapshot: Any = None

    def __init__(
        self,
        config: CommuteConfig | dict[str, Any],
        registry: TransitProviderRegistry | None = None,
        session: Any = None,
        target_arrival_time: str | None = None,
    ) -> None:
        """Initialise commute engine with route geometry and walking thresholds.

        :param config: Strongly-typed CommuteConfig or configuration dictionary.
        :param registry: Optional TransitProviderRegistry instance.
        :param session: Optional shared HTTP client session.
        :param target_arrival_time: Optional fallback target arrival time.
        """
        if isinstance(config, CommuteConfig):
            self._config = config
        else:
            self._config = CommuteConfig.from_dict(data=config)

        self._commute_id: str = self._config.commute_id
        self._target_arrival_time: str | None = (
            target_arrival_time or self._config.target_arrival_time
        )

        if registry is not None:
            self._registry = registry
            if (
                session is not None
                and getattr(self._registry, "_session", None) is None
            ):
                self._registry._session = session
        else:
            self._registry = TransitProviderRegistry(session=session)
            self._registry.discover_providers()

        self._routes: dict[str, RouteConfig] = {
            r.route_id: r for r in self._config.routes
        }
        self._cached_thresholds: dict[str, ResolvedThresholds] = {}
        self._last_helper_overrides: dict[str, Any] | None = None

    def _get_resolved_thresholds(
        self,
        route_id: str,
        route_cfg: RouteConfig,
        helper_overrides: dict[str, Any] | None = None,
    ) -> ResolvedThresholds:
        """Retrieve cached thresholds or resolve cascading threshold hierarchy."""
        if (
            helper_overrides == self._last_helper_overrides
            and route_id in self._cached_thresholds
        ):
            return self._cached_thresholds[route_id]

        thresholds = resolve_route_thresholds(
            route_config=route_cfg,
            helper_overrides=helper_overrides,
            default_grace_seconds=self._config.default_grace_seconds,
            default_grace_fraction=self._config.default_grace_fraction,
            default_target_arrival_time=self._target_arrival_time,
        )
        self._cached_thresholds[route_id] = thresholds
        return thresholds

    def evaluate_commute(
        self,
        telemetries: dict[str, RouteTelemetry],
        reference_time: datetime | None = None,
        helper_overrides: dict[str, Any] | None = None,
    ) -> CommuteState:
        """Evaluate pre-fetched route telemetries and produce unified commute state.

        :param telemetries: Map of route_id to RouteTelemetry instances.
        :param reference_time: Optional datetime reference (defaults to now).
        :param helper_overrides: Optional runtime threshold overrides from HA helpers.
        :return: Evaluated CommuteState object.
        """
        child_states: dict[str, ChildRouteState] = {}
        ref_dt = reference_time or datetime.now()
        candidates: list[CandidateRoute] = []

        if helper_overrides != self._last_helper_overrides:
            self._cached_thresholds.clear()
            self._last_helper_overrides = (
                dict(helper_overrides) if helper_overrides is not None else None
            )

        for route_id, route_cfg in self._routes.items():
            thresholds = self._get_resolved_thresholds(
                route_id=route_id,
                route_cfg=route_cfg,
                helper_overrides=helper_overrides,
            )

            telemetry = telemetries.get(route_id)
            if telemetry is None:
                child_states[route_id] = ChildRouteState(
                    route_id=route_id,
                    mode=route_cfg.mode.value,
                    urgency_stage=UrgencyStage.STANDBY,
                )
                continue

            viable_departures = filter_approaching_departures(
                departures=telemetry.departures,
                corridor_stops=route_cfg.corridor_stops,
                corridor_departures=telemetry.corridor_departures,
                boarding_stop=route_cfg.boarding_stop,
            )

            active_dep, follower_dep = select_active_departures(
                departures=viable_departures,
                walk_seconds=thresholds.walk_seconds,
                grace_seconds=thresholds.grace_seconds,
            )

            if active_dep is None:
                child_states[route_id] = ChildRouteState(
                    route_id=route_id,
                    mode=route_cfg.mode.value,
                    urgency_stage=UrgencyStage.STANDBY,
                )
                continue

            leave_in_sec = calculate_leave_countdown(
                seconds_to_arrival=active_dep.seconds_to_arrival,
                buffer_seconds=thresholds.total_buffer_seconds,
            )
            stage = calculate_urgency_stage(
                leave_in_seconds=leave_in_sec,
            )

            corridor_loc, progress = calculate_corridor_progression(
                departure=active_dep,
                corridor_stops=route_cfg.corridor_stops,
                corridor_departures=telemetry.corridor_departures,
                stop_names=telemetry.stop_names,
                boarding_stop=route_cfg.boarding_stop,
            )

            slack_mins, will_arrive, _ = calculate_target_slack(
                target_arrival_time_str=thresholds.target_arrival_time
                or self._target_arrival_time,
                boarding_arrival_seconds=active_dep.seconds_to_arrival,
                in_vehicle_duration_seconds=route_cfg.in_vehicle_duration_seconds or 0,
                alighting_walk_seconds=route_cfg.alighting_walk_seconds or 0,
                reference_time=ref_dt,
                line_status=telemetry.line_status,
            )

            child_states[route_id] = ChildRouteState(
                route_id=route_id,
                mode=route_cfg.mode.value,
                urgency_stage=stage,
                vehicle_id=active_dep.vehicle_id,
                scheduled_departure=active_dep.expected_time,
                seconds_to_arrival=active_dep.seconds_to_arrival,
                leave_in_seconds=leave_in_sec,
                corridor_location=corridor_loc,
                corridor_progress=progress,
                next_vehicle_id=follower_dep.vehicle_id if follower_dep else None,
                next_seconds_to_arrival=(
                    follower_dep.seconds_to_arrival if follower_dep else None
                ),
                will_arrive_in_time=will_arrive,
                target_slack_minutes=slack_mins,
            )

            if stage in (
                UrgencyStage.LEAVE_NOW,
                UrgencyStage.PREPARE,
                UrgencyStage.RELAXED,
            ):
                candidates.append(
                    CandidateRoute(
                        route_id=route_id,
                        leave_in_seconds=leave_in_sec,
                        urgency_stage=stage,
                        departure=active_dep,
                        route_config=route_cfg,
                        telemetry=telemetry,
                        will_arrive_in_time=will_arrive,
                        target_slack_minutes=slack_mins or 0,
                    )
                )

        helpers = helper_overrides or {}
        strategy_override = helpers.get("rollup_strategy")
        if strategy_override:
            try:
                strategy = RollupStrategy(strategy_override)
            except ValueError:
                strategy = self._config.rollup_strategy
        else:
            strategy = self._config.rollup_strategy

        buffer_override = helpers.get("route_late_buffer_seconds")
        if buffer_override is not None:
            route_late_buf = int(buffer_override)
        else:
            route_late_buf = self._config.route_late_buffer_seconds

        master_state = self._arbitrate_master_rollup(
            candidates=candidates,
            reference_time=ref_dt,
            strategy=strategy,
            route_late_buffer_seconds=route_late_buf,
        )

        return CommuteState(
            commute_id=self._commute_id,
            master_rollup=master_state,
            child_routes=child_states,
        )

    async def async_evaluate_commute(
        self,
        reference_time: datetime | None = None,
        helper_overrides: dict[str, Any] | None = None,
    ) -> CommuteState:
        """Fetch live telemetries from providers and evaluate commute state.

        :param reference_time: Optional explicit reference datetime (defaults to now).
        :param helper_overrides: Optional runtime threshold overrides from HA helpers.
        :return: Evaluated CommuteState object.
        """

        async def _fetch_telemetry(
            route_cfg: RouteConfig,
        ) -> tuple[str, RouteTelemetry]:
            try:
                provider = self._registry.get_provider(provider_id=route_cfg.provider)
                telemetry = await provider.async_get_telemetry(route=route_cfg)
                return route_cfg.route_id, telemetry
            except Exception as err:
                _LOGGER.error(
                    "Error fetching telemetry for route %s from provider %s: %s",
                    route_cfg.route_id,
                    route_cfg.provider,
                    err,
                )
                return route_cfg.route_id, RouteTelemetry(
                    route_id=route_cfg.route_id,
                    line_id=route_cfg.line,
                    mode=route_cfg.mode,
                )

        results = await asyncio.gather(
            *(_fetch_telemetry(route_cfg=r) for r in self._routes.values())
        )
        telemetries = dict(results)

        return self.evaluate_commute(
            telemetries=telemetries,
            reference_time=reference_time,
            helper_overrides=helper_overrides,
        )

    def _arbitrate_master_rollup(
        self,
        candidates: list[CandidateRoute],
        reference_time: datetime,
        strategy: RollupStrategy = RollupStrategy.LATE_WITH_BUFFER,
        route_late_buffer_seconds: int = DEFAULT_ROUTE_LATE_BUFFER_SECONDS,
    ) -> MasterRollupState:
        """Arbitrate master sensor state amongst active candidate child routes.

        Strategy evaluation:
        1. Timeliness Priority: Routes that arrive on time (will_arrive_in_time == True)
           are strictly prioritised over late routes. Late routes are only considered
           if no candidate arrives on time.
        2. Catchability Priority: Routes with positive leave windows
           (leave_in_seconds >= 0) are strictly prioritised over negative
           leave routes (leave_in_seconds < 0). Negative leave routes are
           only considered if no candidate has positive leave.
        3. Strategy Selection:
           - SOONEST: Pick candidate with smallest leave_in_seconds.
           - LATEST: Pick candidate with largest leave_in_seconds.
           - LATE_WITH_BUFFER: Sort ascending by leave_in_seconds. If the top two
             candidates have leave times within route_late_buffer_seconds of each
             other, pick the penultimate candidate so the latest acts as a safety
             buffer/fallback. Otherwise, pick the latest candidate.
        4. Tie-breaking: If multiple candidates tie on leave_in_seconds, select the one
           with greater target_slack_minutes.
        """
        if not candidates:
            return MasterRollupState(
                active_option="none",
                urgency_stage=UrgencyStage.STANDBY,
                expected_time="",
                seconds_to_arrival=0,
                leave_in_seconds=0,
                route_label="",
                will_arrive_in_time=True,
                target_slack_minutes=0,
                strategy=strategy,
            )

        # Step 1: Timeliness Partitioning
        on_time = [c for c in candidates if c.will_arrive_in_time]
        timely_pool = on_time if on_time else candidates

        # Step 2: Catchability Partitioning (positive leave_in_seconds preferred)
        positive_leave = [c for c in timely_pool if c.leave_in_seconds >= 0]
        viable_pool = positive_leave if positive_leave else timely_pool

        # Step 3: Strategy Selection
        if strategy == RollupStrategy.SOONEST:
            winner = min(
                viable_pool,
                key=lambda c: (c.leave_in_seconds, -c.target_slack_minutes),
            )
        elif strategy == RollupStrategy.LATEST:
            winner = max(
                viable_pool,
                key=lambda c: (c.leave_in_seconds, c.target_slack_minutes),
            )
        elif strategy == RollupStrategy.LATE_WITH_BUFFER:
            sorted_candidates = sorted(
                viable_pool,
                key=lambda c: (c.leave_in_seconds, c.target_slack_minutes),
            )
            if len(sorted_candidates) >= 2:
                latest = sorted_candidates[-1]
                penultimate = sorted_candidates[-2]
                delta = latest.leave_in_seconds - penultimate.leave_in_seconds
                if delta <= route_late_buffer_seconds:
                    winner = penultimate
                else:
                    winner = latest
            else:
                winner = sorted_candidates[-1]
        else:
            winner = max(
                viable_pool,
                key=lambda c: (c.leave_in_seconds, c.target_slack_minutes),
            )

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
            strategy=strategy,
        )
