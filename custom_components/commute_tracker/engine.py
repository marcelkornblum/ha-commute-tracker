"""Pure-Python commute tracking and arbitration engine (Phases 3 and 4).

Ingests multi-modal transit payloads, evaluates corridor vehicle progress,
calculates doorstep leave thresholds, and arbitrates Master Rollup state.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
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
    LineStatus,
    PillBadge,
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
    calculate_destination_margin,
    calculate_leave_by_time,
    calculate_milestone_times,
    calculate_pill_badge,
    calculate_seconds_to_leave,
    calculate_urgency_stage,
    format_next_summary,
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
    leave_by_time: str | None = None
    expected_boarding_time: str | None = None
    expected_alighting_time: str | None = None
    expected_destination_time: str | None = None
    seconds_to_leave: int | None = None
    seconds_to_board: int | None = None
    expected_destination_margin_seconds: int | None = None
    will_arrive_on_time: bool = True
    timeliness: str = "on_time"
    corridor_location: str = ""
    corridor_progress: float = 0.0
    corridor_stops: list[dict[str, Any]] = field(default_factory=list)
    next_vehicle_id: str | None = None
    seconds_to_next_board: int | None = None
    next_summary: str = "None scheduled"
    line_status: LineStatus | None = None
    route_label: str = ""
    destination: str = ""
    pill_badge: PillBadge | None = None
    is_active: bool = True


@dataclass(slots=True)
class MasterRollupState:
    """Arbitrated runtime state for the master commute sensor."""

    active_option: str
    urgency_stage: UrgencyStage
    leave_by_time: str = ""
    expected_boarding_time: str = ""
    expected_destination_time: str = ""
    seconds_to_leave: int = 0
    seconds_to_board: int = 0
    expected_destination_margin_seconds: int = 0
    route_label: str = ""
    route_color: str | None = None
    destination: str = ""
    will_arrive_on_time: bool = True
    timeliness: str = "on_time"
    strategy: RollupStrategy = RollupStrategy.LATE_WITH_BUFFER
    line_status: LineStatus | None = None
    next_summary: str = "None scheduled"
    pill_badge: PillBadge | None = None
    is_active: bool = True


@dataclass(slots=True, frozen=True)
class CandidateRoute:
    """Candidate child route evaluated for master sensor arbitration."""

    route_id: str
    seconds_to_leave: int
    seconds_to_board: int
    urgency_stage: UrgencyStage
    departure: DeparturePrediction
    route_config: RouteConfig
    telemetry: RouteTelemetry
    will_arrive_on_time: bool = True
    expected_destination_margin_seconds: int = 0
    timeliness: str = "on_time"
    expected_boarding_time: str = ""
    expected_destination_time: str = ""
    leave_by_time: str = ""
    next_summary: str = "None scheduled"
    pill_badge: PillBadge | None = None


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
        target_destination_time: str | None = None,
    ) -> None:
        """Initialise commute engine with route geometry and walking thresholds.

        :param config: Strongly-typed CommuteConfig or configuration dictionary.
        :param registry: Optional TransitProviderRegistry instance.
        :param session: Optional shared HTTP client session.
        :param target_destination_time: Optional fallback target destination time.
        """
        if isinstance(config, CommuteConfig):
            self._config = config
        else:
            self._config = CommuteConfig.from_dict(data=config)

        self._commute_id: str = self._config.commute_id
        self._target_destination_time: str | None = (
            target_destination_time or self._config.target_destination_time
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

        kwargs: dict[str, Any] = {
            "route_config": route_cfg,
            "helper_overrides": helper_overrides,
            "default_grace_seconds": self._config.grace_seconds,
            "default_grace_fraction": self._config.grace_fraction,
            "default_target_destination_time": self._target_destination_time,
        }
        if self._config.boarding_walk_seconds is not None:
            kwargs["default_boarding_walk_seconds"] = self._config.boarding_walk_seconds
        if self._config.prep_seconds is not None:
            kwargs["default_prep_seconds"] = self._config.prep_seconds

        thresholds = resolve_route_thresholds(**kwargs)
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

            if route_cfg.mode == TransitMode.BUS:
                route_label = route_cfg.line
            else:
                route_label = route_cfg.line.title()

            corridor_stops_data = [
                {
                    "stop_id": sid,
                    "short_name": (
                        telemetry.stop_names.get(sid, sid)
                        if telemetry is not None
                        else sid
                    ),
                    "is_target": sid == route_cfg.boarding_stop,
                }
                for sid in route_cfg.corridor_stops
            ]

            route_destination = route_cfg.destination or ""

            if telemetry is None:
                child_states[route_id] = ChildRouteState(
                    route_id=route_id,
                    mode=route_cfg.mode.value,
                    urgency_stage=UrgencyStage.STANDBY,
                    route_label=route_label,
                    destination=route_destination,
                    corridor_stops=corridor_stops_data,
                    pill_badge=calculate_pill_badge(urgency_stage=UrgencyStage.STANDBY),
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
                boarding_walk_seconds=thresholds.boarding_walk_seconds,
                grace_seconds=thresholds.grace_seconds,
                total_buffer_seconds=thresholds.total_buffer_seconds,
            )

            if active_dep is None:
                child_states[route_id] = ChildRouteState(
                    route_id=route_id,
                    mode=route_cfg.mode.value,
                    urgency_stage=UrgencyStage.STANDBY,
                    line_status=telemetry.line_status,
                    route_label=route_label,
                    destination=route_destination,
                    corridor_stops=corridor_stops_data,
                    pill_badge=calculate_pill_badge(urgency_stage=UrgencyStage.STANDBY),
                )
                continue

            seconds_to_leave = calculate_seconds_to_leave(
                departure_seconds=active_dep.seconds_to_arrival,
                total_buffer_seconds=thresholds.total_buffer_seconds,
            )
            stage = calculate_urgency_stage(
                seconds_to_leave=seconds_to_leave,
            )

            corridor_loc, progress = calculate_corridor_progression(
                departure=active_dep,
                corridor_stops=route_cfg.corridor_stops,
                corridor_departures=telemetry.corridor_departures,
                stop_names=telemetry.stop_names,
                boarding_stop=route_cfg.boarding_stop,
            )

            margin_sec, will_arrive, timeliness_label = calculate_destination_margin(
                target_destination_time_str=thresholds.target_destination_time
                or self._target_destination_time,
                seconds_to_board=active_dep.seconds_to_arrival,
                transit_duration_seconds=route_cfg.transit_duration_seconds or 0,
                alighting_walk_seconds=route_cfg.alighting_walk_seconds or 0,
                reference_time=ref_dt,
                line_status=telemetry.line_status,
            )

            leave_by = calculate_leave_by_time(
                seconds_to_leave=seconds_to_leave,
                reference_time=ref_dt,
            )

            board_time, alight_time, dest_time = calculate_milestone_times(
                seconds_to_board=active_dep.seconds_to_arrival,
                transit_duration_seconds=route_cfg.transit_duration_seconds or 0,
                alighting_walk_seconds=route_cfg.alighting_walk_seconds or 0,
                reference_time=ref_dt,
                expected_boarding_time_str=active_dep.expected_time,
            )

            next_summary = format_next_summary(
                seconds_to_next_board=(
                    follower_dep.seconds_to_arrival if follower_dep else None
                ),
                next_expected_time=(
                    follower_dep.expected_time if follower_dep else None
                ),
                reference_time=ref_dt,
            )

            pill_badge = calculate_pill_badge(
                urgency_stage=stage,
                seconds_to_leave=seconds_to_leave,
            )

            dep_destination = active_dep.destination or route_destination

            child_states[route_id] = ChildRouteState(
                route_id=route_id,
                mode=route_cfg.mode.value,
                urgency_stage=stage,
                vehicle_id=active_dep.vehicle_id,
                leave_by_time=leave_by,
                expected_boarding_time=board_time,
                expected_alighting_time=alight_time,
                expected_destination_time=dest_time,
                seconds_to_leave=seconds_to_leave,
                seconds_to_board=active_dep.seconds_to_arrival,
                expected_destination_margin_seconds=margin_sec,
                will_arrive_on_time=will_arrive,
                timeliness=timeliness_label,
                corridor_location=corridor_loc,
                corridor_progress=progress,
                corridor_stops=corridor_stops_data,
                next_vehicle_id=follower_dep.vehicle_id if follower_dep else None,
                seconds_to_next_board=(
                    follower_dep.seconds_to_arrival if follower_dep else None
                ),
                next_summary=next_summary,
                line_status=telemetry.line_status,
                route_label=route_label,
                destination=dep_destination,
                pill_badge=pill_badge,
            )

            if stage in (
                UrgencyStage.LEAVE_NOW,
                UrgencyStage.PREPARE,
                UrgencyStage.RELAXED,
            ):
                candidates.append(
                    CandidateRoute(
                        route_id=route_id,
                        seconds_to_leave=seconds_to_leave,
                        seconds_to_board=active_dep.seconds_to_arrival,
                        urgency_stage=stage,
                        departure=active_dep,
                        route_config=route_cfg,
                        telemetry=telemetry,
                        will_arrive_on_time=will_arrive,
                        expected_destination_margin_seconds=margin_sec or 0,
                        timeliness=timeliness_label,
                        expected_boarding_time=board_time,
                        expected_destination_time=dest_time,
                        leave_by_time=leave_by,
                        next_summary=next_summary,
                        pill_badge=pill_badge,
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
        1. Timeliness Priority: Routes that arrive on time (will_arrive_on_time == True)
           are strictly prioritised over late routes. Late routes are only considered
           if no candidate arrives on time.
        2. Catchability Priority: Routes with positive leave windows
           (seconds_to_leave >= 0) are strictly prioritised over negative
           leave routes (seconds_to_leave < 0). Negative leave routes are
           only considered if no candidate has positive leave.
        3. Strategy Selection:
           - SOONEST: Pick candidate with smallest seconds_to_leave.
           - LATEST: Pick candidate with largest seconds_to_leave.
           - LATE_WITH_BUFFER: Sort ascending by seconds_to_leave. If the top two
             candidates have leave times within route_late_buffer_seconds of each
             other, pick the penultimate candidate so the latest acts as a safety
             buffer/fallback. Otherwise, pick the latest candidate.
        4. Tie-breaking: If multiple candidates tie on seconds_to_leave, select the one
           with greater expected_destination_margin_seconds.
        """
        if not candidates:
            return MasterRollupState(
                active_option="none",
                urgency_stage=UrgencyStage.STANDBY,
                leave_by_time="",
                expected_boarding_time="",
                expected_destination_time="",
                seconds_to_leave=0,
                seconds_to_board=0,
                expected_destination_margin_seconds=0,
                route_label="",
                route_color=None,
                destination="",
                will_arrive_on_time=True,
                timeliness="on_time",
                strategy=strategy,
                line_status=None,
                next_summary="None scheduled",
                pill_badge=calculate_pill_badge(urgency_stage=UrgencyStage.STANDBY),
            )

        on_time = [c for c in candidates if c.will_arrive_on_time]
        timely_pool = on_time if on_time else candidates

        positive_leave = [c for c in timely_pool if c.seconds_to_leave >= 0]
        viable_pool = positive_leave if positive_leave else timely_pool

        if strategy == RollupStrategy.SOONEST:
            winner = min(
                viable_pool,
                key=lambda c: (
                    c.seconds_to_leave,
                    -c.expected_destination_margin_seconds,
                ),
            )
        elif strategy == RollupStrategy.LATEST:
            winner = max(
                viable_pool,
                key=lambda c: (
                    c.seconds_to_leave,
                    c.expected_destination_margin_seconds,
                ),
            )
        elif strategy == RollupStrategy.LATE_WITH_BUFFER:
            sorted_candidates = sorted(
                viable_pool,
                key=lambda c: (
                    c.seconds_to_leave,
                    c.expected_destination_margin_seconds,
                ),
            )
            if len(sorted_candidates) >= 2:
                latest = sorted_candidates[-1]
                penultimate = sorted_candidates[-2]
                delta = latest.seconds_to_leave - penultimate.seconds_to_leave
                if delta <= route_late_buffer_seconds:
                    winner = penultimate
                else:
                    winner = latest
            else:
                winner = sorted_candidates[-1]
        else:
            winner = max(
                viable_pool,
                key=lambda c: (
                    c.seconds_to_leave,
                    c.expected_destination_margin_seconds,
                ),
            )

        winning_route = winner.route_config

        if winning_route.mode == TransitMode.BUS:
            label = winning_route.line
        else:
            label = winning_route.line.title()

        return MasterRollupState(
            active_option=winner.route_id,
            urgency_stage=winner.urgency_stage,
            leave_by_time=winner.leave_by_time,
            expected_boarding_time=winner.expected_boarding_time,
            expected_destination_time=winner.expected_destination_time,
            seconds_to_leave=winner.seconds_to_leave,
            seconds_to_board=winner.seconds_to_board,
            expected_destination_margin_seconds=winner.expected_destination_margin_seconds,
            route_label=label,
            route_color=winning_route.route_color,
            destination=winner.departure.destination
            or (winning_route.destination or ""),
            will_arrive_on_time=winner.will_arrive_on_time,
            timeliness=winner.timeliness,
            strategy=strategy,
            line_status=winner.telemetry.line_status,
            next_summary=winner.next_summary,
            pill_badge=winner.pill_badge,
        )
