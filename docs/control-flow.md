# Control Flow & Decision Engine

This document provides a detailed technical trace of how transit telemetry moves through `ha-commute-tracker`. It details what components call what, how responsibilities are delegated, and the mathematical rules governing vehicle direction, reachability, corridor progression, and arbitration.

---

## 1. End-to-End Control Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    participant HA as Home Assistant Coordinator
    participant Eng as CommuteEngine
    participant Reg as TransitProviderRegistry
    participant Prov as TransitProvider (e.g. TfL)
    participant Corr as corridor.py
    participant Time as timeliness.py

    HA->>Eng: async_evaluate_commute(reference_time)

    par For each Route in Commute
        Eng->>Reg: get_provider(route.provider)
        Reg-->>Eng: provider_instance
        Eng->>Prov: async_get_telemetry(route)
        Prov-->>Eng: RouteTelemetry (departures, corridor_arrivals, line_status)
    end

    Note over Eng: Calls evaluate_commute(telemetries, reference_time)

    loop For each Route in Commute
        Eng->>Time: resolve_route_thresholds(route_cfg, helpers)
        Time-->>Eng: ResolvedThresholds (boarding_walk, prep, grace, target)

        Eng->>Corr: filter_approaching_departures(departures, corridor_stops, ...)
        Note over Corr: Filters opposite direction & ghost vehicles
        Corr-->>Eng: viable_departures

        Eng->>Corr: select_active_departures(viable_departures, boarding_walk_seconds, grace_seconds, total_buffer_seconds)
        Note over Corr: Evaluates physical reachability across all modes
        Corr-->>Eng: active_departure, follower_departure

        Eng->>Time: calculate_seconds_to_leave(seconds_to_board, total_buffer_seconds)
        Time-->>Eng: seconds_to_leave

        Eng->>Time: calculate_urgency_stage(seconds_to_leave)
        Time-->>Eng: UrgencyStage (standby, relaxed, prepare, leave_now)

        Eng->>Corr: calculate_corridor_progression(active_departure, corridor_stops, ...)
        Note over Corr: Synthesises "Between X and Y" & SVG progress (e.g. 2.5)
        Corr-->>Eng: corridor_location, corridor_progress

        Note over Eng: Build ChildRouteState
    end

    Eng->>Eng: _arbitrate_master_rollup(candidates)
    Eng->>Time: calculate_destination_margin(target_destination_time, expected_dest_dt, line_status)
    Time-->>Eng: margin_seconds, will_arrive_on_time, timeliness

    Eng-->>HA: CommuteState (MasterRollupState + ChildRouteStates)
```

---

## 2. Understanding `CommuteEngine.async_evaluate_commute`

### Context and Purpose
[`CommuteEngine.async_evaluate_commute`](../custom_components/commute_tracker/engine.py) is the asynchronous entry point coordinating the integration:
1. Queries the registered transit provider for each route in parallel via `asyncio.gather`.
2. Isolates provider network errors so failure on one route does not compromise the arbitration of other alternatives.
3. Hands assembled [`RouteTelemetry`](../custom_components/commute_tracker/models.py) objects into `evaluate_commute(...)` for deterministic calculation.

### Pure Decision Engine (`evaluate_commute`)
[`CommuteEngine.evaluate_commute`](../custom_components/commute_tracker/engine.py) performs all synchronous domain math:
- **Input**: A dictionary of pre-fetched [`RouteTelemetry`](../custom_components/commute_tracker/models.py) instances mapped by `route_id`, an optional `reference_time`, and optional helper overrides.
- **Output**: A comprehensive [`CommuteState`](../custom_components/commute_tracker/engine.py) containing the arbitrated master state and individual child states.

This separation guarantees that whether telemetries originate from live async provider calls or offline mock fixtures in unit tests, the exact same pure arbitration logic executes.

---

## 3. Algorithmic Responsibilities & Rules

### A. Threshold Cascading Resolution ([`timeliness.py`](../custom_components/commute_tracker/timeliness.py))
Before evaluating arrival predictions, the engine determines walking, preparation, grace, and target arrival buffers for each route via `resolve_route_thresholds`:
1. **Walking & Preparation Buffers**:
   - Tier 1 (Highest): Home Assistant Input Helper runtime overrides (`boarding_walk_seconds`, `prep_seconds`).
   - Tier 2: Route-specific configuration values (`boarding_walk_seconds`, `prep_seconds`).
   - Tier 3 (Lowest): Global defaults (`DEFAULT_WALK_SECONDS = 240`, `DEFAULT_PREP_SECONDS = 120`).
2. **Grace Buffer Resolution Hierarchy**:
   - Tier 1 (Highest): HA Helper `grace_seconds`
   - Tier 2: HA Helper `grace_fraction` (fraction of `boarding_walk_seconds`)
   - Tier 3: Route config `grace_seconds`
   - Tier 4: Route config `grace_fraction` (fraction of `boarding_walk_seconds`)
   - Tier 5: Commute config `grace_seconds`
   - Tier 6: Commute config `grace_fraction` (fraction of `boarding_walk_seconds`)
   - Tier 7: Root config `grace_seconds`
   - Tier 8: Root config `grace_fraction` (fraction of `boarding_walk_seconds`)
   - Tier 9 (Lowest): Global `DEFAULT_GRACE_FRACTION = 0.25` (25% of `boarding_walk_seconds`)
   - *Mutual Exclusivity*: Within any single scope (Root, Commute, or Route), `grace_seconds` and `grace_fraction` are strictly mutually exclusive in configuration.
   - *Physical Bounding*: `grace_seconds = max(0, min(raw_grace, boarding_walk_seconds))`.
3. **Target Destination Time Resolution**:
   - Tier 1 (Highest): HA Helper `target_destination_time`
   - Tier 2: Commute config `target_destination_time`
   - Tier 3 (Lowest): None (timeliness calculations omitted if no target set)

### B. Direction & Trajectory Filtering ([`corridor.filter_approaching_departures`](../custom_components/commute_tracker/corridor.py))
*Responsibility: Discard vehicles travelling in reverse or vehicles too far away to confirm corridor presence.*

A common failure in public transit APIs is receiving departures at a boarding stop for vehicles travelling in the opposite direction, or "ghost" predictions that disappear.
1. The route configuration provides an ordered list of corridor stops leading to the boarding stop:
   `["Stop 1", "Stop 2", "Stop 3 (Boarding)"]`
2. An index is constructed mapping `(stop_id, vehicle_id) -> seconds_to_arrival`.
3. **Opposing Trajectory Filter**: If a vehicle's arrival at an upstream corridor stop (e.g. Stop 1) is *greater* than its arrival at the boarding stop (Stop 3), the vehicle is travelling away from the boarding stop into the corridor (or in reverse). It is immediately discarded.
4. **Ghost Vehicle Filter**: If a vehicle has no recorded arrivals at any upstream corridor stop and is more than 10 minutes (`CORRIDOR_UPSTREAM_HORIZON_SECONDS = 600`) away from the boarding stop, it is discarded until it enters the observable corridor.

### C. Active Departure Selection & Reachability ([`corridor.select_active_departures`](../custom_components/commute_tracker/corridor.py))
*Responsibility: Decide which departure is the active focus and identify its queue follower.*

Selection operates uniformly across all transit modes without mode-specific carve-outs:
1. **Physical Reachability ([`timeliness.is_departure_reachable`](../custom_components/commute_tracker/timeliness.py))**:
   - `seconds_to_board >= boarding_walk_seconds - grace_seconds`
   - A commuter leaving immediately requires `boarding_walk_seconds` to walk to the stop.
   - `grace_seconds` provides a leeway buffer allowing the commuter to sprint or catch the service while boarding doors are open.
   - If `seconds_to_board < boarding_walk_seconds - grace_seconds`, the vehicle is mathematically unreachable.
2. **Sequential Selection**:
   - The engine iterates through the candidate departures sorted by arrival time and selects the first departure satisfying `is_departure_reachable`.
   - The subsequent departure in the sorted list (if available) is assigned as `follower_departure` to power the "Next Bus" or "Subsequent Departure" preview.
   - If no departures are reachable, `(None, None)` is returned and the route enters `STANDBY`.

### D. Natural Language Location & Corridor Progression ([`corridor.calculate_corridor_progression`](../custom_components/commute_tracker/corridor.py))
*Responsibility: Generate glanceable position descriptions and SVG animation coordinates.*

1. **Natural Language Location**:
   - If `active_dep.seconds_to_arrival <= 45s`: Returns `"At <Stop Name>"`.
   - If the vehicle is between two stops in the corridor: Returns `"Between <Previous Stop> and <Next Stop>"`.
2. **Fractional Progress Index**:
   - For an ordered corridor of stops with indices `0, 1, 2, ..., N`:
     - When dwelling at stop `i`: Progress is `float(i)`.
     - When traversing between stop `i-1` and `i`: Progress is `float(i) - 0.5`.
   - This floating-point value is directly consumed by the Lovelace card to position the transit vehicle icon along SVG route tracks.

### E. Urgency Lifecycle Transitions ([`timeliness.calculate_urgency_stage`](../custom_components/commute_tracker/timeliness.py))
*Responsibility: Categorise the commute status into glanceable visual urgency states.*

```text
Countdown (seconds_to_leave):
     > 480s               0s < seconds_to_leave <= 480s         <= 0s
 ─────────────┬─────────────────────────────────────────┬───────────────►
   RELAXED    │                 PREPARE                 │   LEAVE NOW
  (Green UI)  │               (Amber UI)                │    (Red UI)
```

- **`STANDBY`**: No active departures (`seconds_to_leave is None`).
- **`RELAXED`**: Transit option is reachable and departure time is distant (`seconds_to_leave > 480`).
- **`PREPARE`**: Countdown enters the preparation threshold (`0 < seconds_to_leave <= 480`).
- **`LEAVE_NOW`**: Doorstep deadline reached or passed (`seconds_to_leave <= 0`).

### F. Destination Margin Maths & Timeliness ([`timeliness.calculate_destination_margin`](../custom_components/commute_tracker/timeliness.py))
*Responsibility: Calculate expected destination arrival and timeliness status.*

1. **Total Estimated Journey**:
   `total_journey = seconds_to_board + transit_duration_seconds + alighting_walk_seconds`
2. **Estimated Destination Arrival Time**:
   `expected_destination_dt = reference_time + timedelta(seconds=total_journey)`
3. **Midnight Rollover Correction**:
   If the target arrival time wraps past midnight relative to observation time, the engine shifts `target_dt` by `±1 day` when the gap exceeds `MIDNIGHT_WRAP_THRESHOLD_SECONDS` (12 hours).
4. **Margin Seconds**:
   `margin_seconds = round((target_dt - expected_destination_dt).total_seconds())`
   - Positive margin indicates arriving ahead of deadline.
   - Negative margin indicates arriving late.
5. **Timeliness Classifications**:
   - `cancelled`: Line or route is cancelled.
   - `late`: `margin_seconds < 0`.
   - `delayed`: Operational service delay reported on line status.
   - `early`: `margin_seconds >= 300` (5 minutes ahead).
   - `on_time`: Arriving within 0–299 seconds of target deadline.

### G. Master Rollup Arbitration ([`engine._arbitrate_master_rollup`](../custom_components/commute_tracker/engine.py))
*Responsibility: Arbitrate the winning active option across alternative single-leg commute routes (e.g. Bus vs Tube vs Train).*

1. **Timeliness Partitioning**:
   - Candidates are evaluated against the target deadline (`will_arrive_on_time`).
   - Routes arriving on time are strictly prioritised over late routes. Late routes are only considered if no candidate can arrive on time.
2. **Catchability Partitioning**:
   - Within the timeliness candidate pool, routes with non-negative departure windows (`seconds_to_leave >= 0`) are strictly prioritised over sprint routes (`seconds_to_leave < 0`).
   - Sprint routes are only selected if no positive-window alternatives exist.
3. **Arbitration Strategies ([`RollupStrategy`](../custom_components/commute_tracker/models.py))**:
   - **`soonest`**: Selects the candidate with the smallest positive `seconds_to_leave` (the soonest viable departure).
   - **`latest`**: Selects the candidate with the largest positive `seconds_to_leave` that still arrives on time.
   - **`late_with_buffer` (Default)**: Evaluates the sorted candidates by `seconds_to_leave`. If the top two latest options are within `route_late_buffer_seconds` (default: 300 seconds / 5 minutes) of each other, the engine selects the penultimate candidate so that the latest departure serves as a safety buffer/fallback. If the gap exceeds the buffer, it selects the latest candidate.
4. **Tie-Breaking**:
   - When multiple candidates have equal `seconds_to_leave`, the candidate with greater `expected_destination_margin_seconds` is selected.
5. Populates [`MasterRollupState`](../custom_components/commute_tracker/engine.py) with the winning option's identity, formatted arrival time, urgency stage, strategy used, and destination margin metrics.


