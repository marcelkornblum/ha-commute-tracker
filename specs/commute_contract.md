# Commute Tracker Public Entity & Sensor Contract

This contract defines the public entity interfaces, sensor states, attributes, data structures, and exemplar test fixtures exposed by `ha-commute-tracker` to Home Assistant and the Lovelace frontend card (`commute-tracker-card.js`).

---

## 1. Architectural Principles

1. **Strict Entity Minimalism**:
   - Only **Master Rollup** sensors (`sensor.commute_<commute_id>`) and **Child Route** sensors (`sensor.commute_<commute_id>_<route_id>`) are registered in the Home Assistant Entity Registry.
   - All intermediary API responses (intermediate stop arrivals, raw predictions, line statuses) remain exclusively in the `DataUpdateCoordinator`'s internal memory.
2. **External Polling Triggers**:
   - Polling is driven by the state of an external binary sensor (`active_sensor`).
   - When the active sensor is `off`, the coordinator suspends polling and all sensors transition to the `idle` state.
3. **No Standalone Timeliness Sensors**:
   - Timeliness status (`timeliness`, `target_slack_minutes`, `will_arrive_in_time`) is exposed directly as attributes on both Master and Child sensors.
4. **Exact Lovelace Card Parity**:
   - All attribute names and value formats maintain 100% compatibility with the Lovelace card interface developed in the legacy proof of concept.

---

## 2. Standard Exemplar Commute: Nelson's Column to Brick Lane

To protect user privacy and eliminate personal commute data from the test suite and documentation, the repository uses a standard London commuter journey as the canonical reference implementation:

- **Commute ID**: `nelson_to_brick_lane`
- **Commute Title**: `"Nelson's Column to Brick Lane"`
- **Commuter Name**: `"Commuter"`
- **Origin**: Nelson's Column, Trafalgar Square (`51.5078, -0.1280`)
- **Destination**: Brick Lane, London E1 (`51.5215, -0.0715`)
- **Target Destination Arrival**: `09:00`
- **Active Binary Sensor**: `binary_sensor.commute_nelson_to_brick_lane_relevant`

```
                                Nelson's Column
                                (Trafalgar Sq)
                                      |
                     +----------------+----------------+
                     | (4m walk + 2m) | (4m walk + 2m) | (10m walk + 2m)
                     v                v                v
              [Bus Line 26]   [Southeastern Rail] [Central Line Tube]
           Victoria->Trafalgar Charing X->London Bdg North Acton->Tottenham Ct Rd
                     |                |                |
                 (32m bus)        (8m train)       (8m tube)
                     v                v                v
               Shoreditch Stn    London Bridge     Liverpool Street
                     |                |                |
                 (10m walk)       (15m walk)       (8m walk)
                     +----------------+----------------+
                                      v
                                  Brick Lane
```

### Route 1: Daytime Bus 26 (Victoria to Hackney Wick / Shoreditch)
- **Mode**: `bus` (vehicle type: `bus`)
- **Line Code**: `"26"` (Daytime service)
- **Operator**: `"TfL"`
- **Route Colour**: `"#DC241F"` (London Bus Red)
- **Headway / Frequency**: ~8–10 minutes
- **Boarding Stop**: `Charing Cross Stn / Trafalgar Square` (Stop F, NaPTAN `490013766F`)
- **Destination / Alighting Stop**: `Shoreditch High Street Station` (Stop F, NaPTAN `490005524F`)
- **Walking Offsets**:
  - Walk from Nelson's Column to Stop F: `4` minutes
  - Prep buffer: `2` minutes
  - Doorstep leave threshold: $\text{timeToStation} - (4 + 2) \times 60$ seconds
  - Walk from Shoreditch High St to Brick Lane: `10` minutes
  - In-bus journey duration: `32` minutes
- **Corridor Stop Geometry** (approaching boarding stop):
  1. Terminus: Victoria Station (`490000248H`, `"Victoria"`, ~20–25m transit to target, ~14–19m advance warning before doorstep threshold)
  2. Intermediate 1: Westminster Cathedral (`490014496N`, `"Westminster Cathedral"`)
  3. Intermediate 2: Westminster City Hall (`490003384SA`, `"Westminster City Hall"`)
  4. Intermediate 3: St James's Park Station (`490010260SC`, `"St James"`)
  5. Intermediate 4: Westminster Abbey (`490014495R`, `"Westminster Abbey"`)
  6. Intermediate 5: Westminster Stn / Parliament Square (`490015048A`, `"Westminster"`)
  7. Intermediate 6: Horse Guards Parade (`490008376N`, `"Horse Guards"`)
  8. Boarding Target: Charing Cross Stn / Trafalgar Square (`490013766F`, `"Trafalgar Sq"`, `is_target: true`)

### Route 2: Train (Southeastern Rail)
- **Mode**: `train` (vehicle type: `train`)
- **Line Code**: `"southeastern"`
- **Operator**: `"Southeastern"`
- **Route Colour**: `"#0019A8"` (Southeastern Blue)
- **Headway / Frequency**: ~15 minutes
- **Boarding Station**: `London Charing Cross Rail Station` (NaPTAN `910GCHRX`, terminus station)
- **Alighting Station**: `London Bridge Rail Station` (NaPTAN `910GLNDNBDC`)
- **Walking Offsets**:
  - Walk from Nelson's Column to station concourse: `4` minutes
  - Prep buffer: `2` minutes
  - Doorstep leave threshold: $\text{departureCountdown} - (4 + 2) \times 60$ seconds
  - Scheduled rail transit duration: `8` minutes
  - Walk / transfer from London Bridge to Brick Lane: `15` minutes
- **Corridor Stop Geometry** (approaching boarding station):
  - *Terminus Concourse Tracking Model*: Because London Charing Cross is a buffer-stop rail terminus where trains originate from the platform, there is no upstream approach corridor of pre-boarding stations. The tracking model evaluates scheduled platform departure boards and gate status rather than multi-station progression. To ensure the commuter receives sufficient advance warning prior to the doorstep threshold (4m walk + 2m prep = 6m), the journey planner query evaluates forward schedule pagination (`timeAdjustments.later`), maintaining a 45–60 minute forward departure horizon (minimum 8–10 scheduled services).
  1. Origin & Boarding Target: London Charing Cross Rail Station (`910GCHRX`, `"Charing Cross"`, `is_target: true`, terminus concourse)
  2. Direct Rail Transit: London Charing Cross $\rightarrow$ London Bridge (non-stop direct line)
  3. Alighting Destination: London Bridge Rail Station (`910GLNDNBDC`, `"London Bridge"`)

### Route 3: Deep Underground Tube (Central Line)
- **Mode**: `tube` (vehicle type: `tube`)
- **Line Code**: `"central"`
- **Operator**: `"London Underground"`
- **Route Colour**: `"#E32017"` (Central Line Red)
- **Headway / Frequency**: ~2–3 minutes (24–30 trains/hour)
- **Boarding Station**: `Tottenham Court Road Underground Station` (NaPTAN `940GZZLUTCR`, through-station)
- **Alighting Station**: `Liverpool Street Underground Station` (NaPTAN `940GZZLULVT`)
- **Walking Offsets**:
  - Walk from Nelson's Column to Tottenham Court Road station concourse: `10` minutes (750m north via Charing Cross Road)
  - Prep buffer: `2` minutes
  - Doorstep leave threshold: $\text{departureCountdown} - (10 + 2) \times 60$ seconds
  - Scheduled transit duration: `8` minutes (5 intermediate stations direct)
  - Walk from Liverpool Street to Brick Lane: `8` minutes (650m east via Spitalfields)
- **Corridor Stop Geometry** (approaching boarding station):
  1. Approach 1: North Acton Underground Station (`940GZZLUNAN`, `"North Acton"`, trunk merge, ~24m transit to target, ~12m advance warning before doorstep threshold)
  2. Approach 2: East Acton Underground Station (`940GZZLUEAN`, `"East Acton"`, ~20m transit to target)
  3. Approach 3: White City Underground Station (`940GZZLUWCY`, `"White City"`, ~16m transit to target, ~4m advance warning)
  4. Approach 4: Shepherd's Bush (Central) Underground Station (`940GZZLUSBC`, `"Shepherd's Bush"`, ~14m transit to target)
  5. Approach 5: Holland Park Underground Station (`940GZZLUHPK`, `"Holland Park"`, ~12m transit to target, doorstep leave threshold)
  6. Approach 6: Notting Hill Gate Underground Station (`940GZZLUNHG`, `"Notting Hill Gate"`, ~10m transit to target)
  7. Approach 7: Queensway Underground Station (`940GZZLUQWY`, `"Queensway"`, ~8m transit to target)
  8. Approach 8: Lancaster Gate Underground Station (`940GZZLULGT`, `"Lancaster Gate"`, ~6.5m transit to target)
  9. Approach 9: Marble Arch Underground Station (`940GZZLUMBA`, `"Marble Arch"`, ~5m transit to target)
  10. Approach 10: Bond Street Underground Station (`940GZZLUBND`, `"Bond Street"`, ~3.5m transit to target)
  11. Approach 11: Oxford Circus Underground Station (`940GZZLUOXC`, `"Oxford Circus"`, ~1.5m transit to target)
  12. Boarding Target: Tottenham Court Road Underground Station (`940GZZLUTCR`, `"Tottenham Court Rd"`, `is_target: true`)

---

## 3. Master Rollup Sensor (`sensor.commute_<commute_id>`)

The Master Rollup sensor represents the overall commute. It dynamically arbitrates between available child routes, promoting the optimal route's telemetry to the top level while providing overall commute badges and summaries.

### Entity Identifier
- Pattern: `sensor.commute_<commute_id>`
- Canonical Exemplar: `sensor.commute_nelson_to_brick_lane`

### State
String representation of the current urgency stage, matching the architectural specification to enable direct state triggers for Home Assistant automations:
- `"standby"`: Commute is inactive or outside tracking window (`active_sensor` is `off` or no service scheduled).
- `"relaxed"`: Transit service is active with comfortable buffer before the preparation window (e.g. $> 8$ minutes to leave).
- `"prepare"`: Commuter preparation window active (e.g. $\le 8$ minutes to leave).
- `"leave_now"`: Doorstep departure deadline reached ($\text{leave\_in\_seconds} \le 0$).

> [!IMPORTANT]
> **Reachability Rollover (Pre-Departure Miss Detection)**:
> Rollover occurs **before the vehicle departs**, governed strictly by physical reachability from the commuter's doorstep:
> 1. **Comfortable Departure Target**: Calculated as $\text{leave\_by\_time} = \text{departure\_time} - (\text{walk} + \text{prep})$.
> 2. **Leeway / Grace Window**: Once $\text{leave\_in\_seconds} \le 0$, the state transitions to `"leave_now"`. The vehicle remains the active candidate for a configurable leeway window ($\text{grace\_seconds}$, typically $180\text{s}$ for buses, $360\text{s}$ for trains) allowing the commuter to rush or run to the stop.
> 3. **Unreachable / Missed Cutoff**: Once $\text{leave\_in\_seconds} < -\text{grace\_seconds}$, the commuter has mathematically **no chance** of reaching the stop before the vehicle leaves. At that moment, the vehicle is discarded as **missed** and removed from the active plan, regardless of its actual physical location along the corridor or whether it has arrived at the boarding stop yet.
> 4. **Rollover Transition**: The engine immediately advances to track the subsequent scheduled transit service. If a next vehicle exists, urgency rolls back to `"relaxed"` (or `"prepare"` if close behind). If no reachable service remains or the active window closes, the state transitions to `"standby"`.

All departure times and countdown metrics are provided via attributes (`expected_time`, `leave_by_time`, `seconds_to_arrival`, `leave_in_seconds`).

### Attributes Table

| Attribute | Type | Description | Exemplar Value |
| :--- | :--- | :--- | :--- |
| `commute_id` | `str` | Unique identifier of the commute | `"nelson_to_brick_lane"` |
| `commute_title` | `str` | Display title for the card header | `"Nelson's Column to Brick Lane"` |
| `person_name` | `str` | Name of the commuter | `"Commuter"` |
| `person_picture` | `str` | URL or local path to person image | `""` |
| `active_option` | `str` | ID of the currently selected optimal route | `"bus_26"` |
| `options` | `list[str]` | List of all configured child route option IDs | `["bus_26", "train_southeastern", "tube_central"]` |
| `is_relevant` | `bool` | Whether the commute is currently active | `true` |
| `urgency_stage` | `str` | Commute urgency lifecycle phase | `"standby"` \| `"relaxed"` \| `"prepare"` \| `"leave_now"` |
| `pill_label` | `str` | Header badge text | `"Standby"` \| `"Leave in 4m"` \| `"🚨 LEAVE NOW"` |
| `pill_color` | `str` | Hex colour code for badge text and accent | `"#4CAF50"` \| `"#FF9800"` \| `"#FF5252"` \| `"#8E8E93"` |
| `pill_bg` | `str` | RGBA colour for badge background | `"rgba(76, 175, 80, 0.15)"` |
| `pill_border` | `str` | Border colour for badge | `"#4CAF50"` |
| `route_label` | `str` | Line or route short identifier | `"26"` \| `"Southeastern"` \| `"Central"` |
| `route_color` | `str` | Primary branding colour of active route | `"#DC241F"` \| `"#0019A8"` \| `"#E32017"` |
| `route_destination` | `str` | Final destination of active route transit | `"Shoreditch"` \| `"London Bridge"` \| `"Liverpool Street"` |
| `line_status` | `str` | TfL / Operator service status description | `"Good Service"` \| `"Minor Delays"` |
| `line_status_icon` | `str` | Status icon symbol | `"✓"` \| `"⚠"` |
| `line_status_color` | `str` | Status icon colour hex | `"#4CAF50"` \| `"#FF9800"` \| `"#F44336"` |
| `line_status_reason` | `str` | Disruption reasoning text if applicable | `""` |
| `detail_navigation_path` | `str` | Optional Lovelace sub-view navigation path | `"/lovelace/commute-detail-26"` |
| `expected_time` | `str` | Expected departure time at boarding stop | `"08:24"` \| `"none"` |
| `minutes_to_arrival` | `int` \| `str` | Minutes until transit arrives at boarding stop | `5` \| `"none"` |
| `seconds_to_arrival` | `int` \| `str` | Seconds until transit arrives at boarding stop | `312` \| `"none"` |
| `leave_by_time` | `str` | Recommended doorstep departure time (`HH:MM`) | `"08:18"` \| `"none"` |
| `leave_in_minutes` | `int` \| `str` | Minutes until commuter must leave | `2` \| `"none"` |
| `leave_in_seconds` | `int` \| `str` | Seconds until commuter must leave | `132` \| `"none"` |
| `corridor_location` | `str` | Natural language vehicle position | `"Between Horse Guards and Trafalgar Sq"` |
| `corridor_stops` | `list[dict]` | Ordered schematic corridor stops | `[{"short_name": "...", "is_target": false}]` |
| `corridor_progress` | `float` | Fractional progression index along corridor | `3.5` |
| `target_arrival_time` | `str` | Planned destination arrival deadline | `"09:00"` |
| `target_slack_minutes` | `int` \| `str` | Buffer minutes relative to deadline | `4` \| `"-3"` \| `"none"` |
| `will_arrive_in_time` | `bool` | Whether route arrives before target deadline | `true` |
| `timeliness` | `str` | Normalised timeliness classification | `"on_time"` \| `"early"` \| `"late"` \| `"delayed"` \| `"cancelled"` |
| `next_summary` | `str` | Formatted summary of subsequent service | `"Next at 08:36 (in 12m)"` \| `"None scheduled"` |

---

## 4. Child Route Sensor (`sensor.commute_<commute_id>_<route_id>`)

### Entity Identifiers
- Bus: `sensor.commute_nelson_to_brick_lane_bus_26`
- Train: `sensor.commute_nelson_to_brick_lane_train_southeastern`
- Tube: `sensor.commute_nelson_to_brick_lane_tube_central`

### State & Additional Attributes
Same format as Master Rollup, plus:
- `option_id`: `"bus_26"`, `"train_southeastern"`, or `"tube_central"`
- `mode`: `"bus"`, `"train"`, or `"tube"`
- `vehicle_type`: `"bus"`, `"train"`, or `"tube"`
- `journey_duration_minutes`: `32` (bus), `8` (train), or `8` (tube)
- `estimated_transit_arrival`: `"08:56"` (Shoreditch), `"08:38"` (London Bridge), or `"08:38"` (Liverpool Street)
- `estimated_destination_arrival`: `"09:06"` (Brick Lane via bus), `"08:53"` (Brick Lane via rail), or `"08:46"` (Brick Lane via tube)
- `corridor_stage_id`: e.g. `"transit:horse_guards_to_trafalgar"` or `"transit:oxford_circus_to_tottenham_court_road"`

---

## 5. Fixture Sets & Testing Directory Layout

To support both **legacy PoC replication (discrete stop queries)** and **modernised architecture (consolidated line queries)** across all three transit modes, `tests/fixtures/commute_nelson_to_brick_lane/` provides 6 distinct fixture sets:

```
tests/fixtures/commute_nelson_to_brick_lane/
├── set1_poc_bus_discrete/                 # PoC discrete stop arrivals across full approach corridor
│   ├── 01_terminus_victoria.json
│   ├── 02_intermediate_westminster_cathedral.json
│   ├── 03_intermediate_westminster_city_hall.json
│   ├── 04_intermediate_st_james_park.json
│   ├── 05_intermediate_westminster_abbey.json
│   ├── 06_intermediate_westminster.json
│   ├── 07_intermediate_horse_guards.json
│   ├── 08_target_trafalgar_square.json
│   ├── 09_destination_shoreditch_high_st.json
│   └── 10_line_status.json
├── set2_poc_train_discrete/               # Legacy PoC rail journey results (terminus model)
│   ├── 01_journey_results.json
│   └── 02_line_status.json
├── set3_consolidated_bus/                 # Optimised line-wide arrivals (replaces discrete calls)
│   ├── line_arrivals.json                 # /Line/26/Arrivals (all stops & vehicles)
│   └── line_status.json                   # /Line/26/Status
├── set4_consolidated_train/               # Consolidated rail journey results (45m+ forward horizon)
│   ├── journey_results.json               # /Journey/JourneyResults/910GCHRX/to/910GLNDNBDC
│   └── line_status.json                   # /Line/southeastern/Status
├── set5_poc_tube_discrete/                # Discrete tube station arrivals across full approach corridor
│   ├── 01_intermediate_north_acton.json
│   ├── 02_intermediate_east_acton.json
│   ├── 03_intermediate_white_city.json
│   ├── 04_intermediate_shepherds_bush.json
│   ├── 05_intermediate_holland_park.json
│   ├── 06_intermediate_notting_hill_gate.json
│   ├── 07_intermediate_queensway.json
│   ├── 08_intermediate_lancaster_gate.json
│   ├── 09_intermediate_marble_arch.json
│   ├── 10_intermediate_bond_street.json
│   ├── 11_intermediate_oxford_circus.json
│   ├── 12_target_tottenham_court_road.json
│   ├── 13_destination_liverpool_street.json
│   ├── 14_line_status.json
│   └── 15_journey_results.json
├── set6_consolidated_tube/                # Consolidated tube arrivals, status & journey
│   ├── line_arrivals.json                 # /Line/central/Arrivals
│   ├── journey_results.json
│   └── line_status.json
└── time_series/                           # 45-minute multi-modal corridor snapshots (90 iterations @ 30s)
    ├── snapshot_001.json                  # Multi-modal bus + tube corridor snapshot
    ├── ...
    ├── snapshot_090.json
    └── series_manifest.json               # Index of all snapshots and tracked vehicle IDs
```

### Running the Live Capture Utility
The script `scripts/capture_tfl.py` captures all 6 fixture sets and executes the 45-minute time-series capture:

```bash
uv run python scripts/capture_tfl.py \
  --bus-line 26 \
  --train-line southeastern \
  --tube-line central \
  --time-series-count 90 \
  --time-series-interval 30.0
```

---

## 6. Reachability & Optimal Route Arbitration

### Reachability Filter
A transit departure $k$ with arrival countdown $t_k$ (seconds to arrive at boarding stop) is deemed **reachable** if and only if:
$$\text{leave\_in\_seconds}_k = t_k - (\text{walk\_minutes} + \text{prep\_minutes}) \times 60 \ge -\text{grace\_seconds}$$
- If $\text{leave\_in\_seconds}_k < -\text{grace\_seconds}$, departure $k$ is mathematically unreachable and marked **missed**. The engine immediately discards it and evaluates departure $k+1$, regardless of whether vehicle $k$ is still en route.
- $\text{grace\_seconds}$ provides user leeway beyond the comfortable recommendation (e.g. running to the stop), after which reaching the stop is impossible.

### Multi-Route Arbitration
When evaluating multiple routes for the Master Rollup:
1. **Filter Reachable**: Eliminate routes with no reachable services.
2. **Timeliness Priority**: Prioritise routes that arrive before the target deadline ($\text{target\_slack\_minutes} \ge 0$).
3. **Immediacy Priority**: Between multiple on-time (or multiple late) routes, promote the route requiring departure soonest ($\text{leave\_in\_seconds}$).
4. **Standby Fallback**: If no reachable service exists across all options, the commute transitions to `"standby"`.

