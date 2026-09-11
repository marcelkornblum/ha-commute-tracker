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
                     | (4m walk + 2m) | (4m walk + 2m) | (6m walk + 2m)
                     v                v                v
              [Bus Line 26]   [Southeastern Rail] [District Line Tube]
           Victoria->Trafalgar Charing X->London Bdg Victoria->Embankment
                     |                |                |
                 (32m bus)        (8m train)       (13m tube)
                     v                v                v
               Shoreditch Stn    London Bridge     Aldgate East Stn
                     |                |                |
                 (10m walk)       (15m walk)       (3m walk)
                     +----------------+----------------+
                                      v
                                  Brick Lane
```

### Route 1: Daytime Bus 26 (Victoria to Hackney Wick / Shoreditch)
- **Mode**: `bus` (vehicle type: `bus`)
- **Line Code**: `"26"` (Daytime service)
- **Operator**: `"TfL"`
- **Route Colour**: `"#DC241F"` (London Bus Red)
- **Boarding Stop**: `Charing Cross Stn / Trafalgar Square` (Stop F, NaPTAN `490013766F`)
- **Destination / Alighting Stop**: `Shoreditch High Street Station` (Stop F, NaPTAN `490005524F`)
- **Walking Offsets**:
  - Walk from Nelson's Column to Stop F: `4` minutes
  - Prep buffer: `2` minutes
  - Doorstep leave threshold: $\text{timeToStation} - (4 + 2) \times 60$ seconds
  - Walk from Shoreditch High St to Brick Lane: `10` minutes
  - In-bus journey duration: `32` minutes
- **Corridor Stop Geometry** (approaching boarding stop):
  1. Terminus: Victoria Station (`490000248H`, `"Victoria"`)
  2. Intermediate 1: St James's Park Station (`490010260SC`, `"St James"`)
  3. Intermediate 2: Westminster Station (`490015048A`, `"Westminster"`)
  4. Intermediate 3: Horse Guards Parade (`490008376N`, `"Horse Guards"`)
  5. Boarding Target: Charing Cross Stn / Trafalgar Square (`490013766F`, `"Trafalgar Sq"`, `is_target: true`)

### Route 2: Train (Southeastern Rail)
- **Mode**: `train` (vehicle type: `train`)
- **Line Code**: `"southeastern"`
- **Operator**: `"Southeastern"`
- **Route Colour**: `"#0019A8"` (Southeastern Blue)
- **Boarding Station**: `London Charing Cross Rail Station` (NaPTAN `910GCHRX`, terminus station)
- **Alighting Station**: `London Bridge Rail Station` (NaPTAN `910GLNDNBDC`)
- **Headway / Frequency**: ~15 minutes
- **Walking Offsets**:
  - Walk from Nelson's Column to station concourse: `4` minutes
  - Prep buffer: `2` minutes
  - Doorstep leave threshold: $\text{departureCountdown} - (4 + 2) \times 60$ seconds
  - Scheduled rail transit duration: `8` minutes
  - Walk / transfer from London Bridge to Brick Lane: `15` minutes

### Route 3: Sub-Surface Rail / Tube (District Line)
- **Mode**: `tube` (vehicle type: `tube`)
- **Line Code**: `"district"`
- **Operator**: `"London Underground"`
- **Route Colour**: `"#00782A"` (District Line Green)
- **Boarding Station**: `Embankment Underground Station` (NaPTAN `940GZZLUEMB`, through-station)
- **Alighting Station**: `Aldgate East Underground Station` (NaPTAN `940GZZLUADE`)
- **Headway / Frequency**: ~4–5 minutes (12–14 trains/hour)
- **Rationale for Inclusion**:
  1. **Non-Terminus Corridor Tracking**: Unlike Charing Cross rail station which terminates at the concourse, Embankment is a through-running station. Trains approach along an active underground tunnel corridor from upstream stations (`Victoria` $\rightarrow$ `St James's Park` $\rightarrow$ `Westminster` $\rightarrow$ `Embankment`), allowing the corridor tracking engine to observe multi-station train progress.
  2. **Distinct Frequency Profile**: Operates with a rapid 4–5 minute headway, distinct from Bus 26 (~8–10 min) and Southeastern rail (~15 min).
  3. **Direct Alighting at Brick Lane**: Aldgate East station sits directly at the southern entrance of Brick Lane (Osborn Street / Whitechapel High Street).
- **Walking Offsets**:
  - Walk from Nelson's Column to Embankment station concourse: `6` minutes (450m via Villiers Street)
  - Prep buffer: `2` minutes
  - Doorstep leave threshold: $\text{departureCountdown} - (6 + 2) \times 60$ seconds
  - Scheduled transit duration: `13` minutes (7 intermediate stations direct)
  - Walk from Aldgate East to Brick Lane: `3` minutes (250m up Osborn Street)
- **Corridor Stop Geometry** (approaching boarding station):
  1. Approach 1: Victoria Underground Station (`940GZZLUVIC`, `"Victoria"`)
  2. Approach 2: St James's Park Underground Station (`940GZZLUSJP`, `"St James"`)
  3. Approach 3: Westminster Underground Station (`940GZZLUWSM`, `"Westminster"`)
  4. Boarding Target: Embankment Underground Station (`940GZZLUEMB`, `"Embankment"`, `is_target: true`)

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
| `options` | `list[str]` | List of all configured child route option IDs | `["bus_26", "train_southeastern"]` |
| `is_relevant` | `bool` | Whether the commute is currently active | `true` |
| `urgency_stage` | `str` | Commute urgency lifecycle phase | `"standby"` \| `"relaxed"` \| `"prepare"` \| `"leave_now"` |
| `pill_label` | `str` | Header badge text | `"Standby"` \| `"Leave in 4m"` \| `"🚨 LEAVE NOW"` |
| `pill_color` | `str` | Hex colour code for badge text and accent | `"#4CAF50"` \| `"#FF9800"` \| `"#FF5252"` \| `"#8E8E93"` |
| `pill_bg` | `str` | RGBA colour for badge background | `"rgba(76, 175, 80, 0.15)"` |
| `pill_border` | `str` | Border colour for badge | `"#4CAF50"` |
| `route_label` | `str` | Line or route short identifier | `"26"` \| `"Southeastern"` |
| `route_color` | `str` | Primary branding colour of active route | `"#DC241F"` \| `"#0019A8"` |
| `route_destination` | `str` | Final destination of active route transit | `"Shoreditch"` \| `"London Bridge"` |
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

### State & Additional Attributes
Same format as Master Rollup, plus:
- `option_id`: `"bus_26"` or `"train_southeastern"`
- `mode`: `"bus"` or `"train"`
- `vehicle_type`: `"bus"` or `"train"`
- `journey_duration_minutes`: `32` (bus) or `8` (train)
- `estimated_transit_arrival`: `"08:56"` (Shoreditch) or `"08:38"` (London Bridge)
- `estimated_destination_arrival`: `"09:06"` (Brick Lane via bus) or `"08:53"` (Brick Lane via rail)
- `corridor_stage_id`: e.g. `"transit:horse_guards_to_trafalgar"`

---

## 5. Fixture Sets & Testing Directory Layout

To support both **legacy PoC replication (discrete stop queries)** and **modernised architecture (consolidated line queries)**, `tests/fixtures/commute_nelson_to_brick_lane/` provides 4 distinct fixture sets:

```
tests/fixtures/commute_nelson_to_brick_lane/
├── set1_poc_bus_discrete/          # Mirrors PoC commute_package.yaml lines 1-140
│   ├── 01_terminus_victoria.json
│   ├── 02_intermediate_st_james_park.json
│   ├── 03_intermediate_westminster.json
│   ├── 04_intermediate_horse_guards.json
│   ├── 05_target_trafalgar_square.json
│   ├── 06_destination_shoreditch_high_st.json
│   └── 07_line_status.json
├── set2_poc_train_discrete/        # Mirrors PoC commute_package.yaml lines 141-185
│   ├── 01_journey_results.json
│   └── 02_line_status.json
├── set3_consolidated_bus/          # 2 optimised calls replacing 7 discrete calls
│   ├── line_arrivals.json          # /Line/26/Arrivals (all stops & vehicles)
│   └── line_status.json            # /Line/26/Status
├── set4_consolidated_train/        # Point-to-point journey & status
│   ├── journey_results.json        # /Journey/JourneyResults/910GCHRX/to/910GLNDNBDC
│   └── line_status.json            # /Line/southeastern/Status
└── time_series/                    # Snapshots over time showing vehicle progression
    ├── snapshot_001.json
    ├── snapshot_002.json
    ├── snapshot_003.json
    ├── snapshot_004.json
    ├── snapshot_005.json
    └── series_manifest.json
```

### Running the Live Capture Utility
The script `scripts/capture_tfl.py` can be executed during morning or evening peak hours to capture rush-hour transit dynamics:

```bash
uv run python scripts/capture_tfl.py \
  --bus-line 26 \
  --train-line southeastern \
  --time-series-count 10 \
  --time-series-interval 15.0
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

