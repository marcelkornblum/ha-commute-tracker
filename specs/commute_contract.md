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
   - Timeliness status (`timeliness`, `expected_destination_margin_seconds`, `will_arrive_on_time`) is exposed directly as attributes on both Master and Child sensors.
4. **Exact Lovelace Card Parity**:
   - All attribute names and value formats maintain 100% compatibility with the Lovelace card interface developed in the legacy proof of concept.

---

## 2. Standard Exemplar Commute: Nelson's Column to Brick Lane

To protect user privacy and eliminate personal commute data from the test suite and documentation, the repository uses a standard London commuter journey as the canonical reference implementation:

- **Commute ID**: `nelson_to_brick_lane`
- **Commute Title**: `"Nelson's Column to Brick Lane"`
- **Commuter Name**: `"Commuter"`
- **Doorstep (Origin)**: Nelson's Column, Trafalgar Square (`51.5078, -0.1280`)
- **Destination**: Brick Lane, London E1 (`51.5215, -0.0715`)
- **Target Destination Time**: `09:00`
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
- **Mode**: `bus`
- **Line**: `"26"` (Daytime service)
- **Provider**: `"tfl"`
- **Direction**: `from_home`
- **Route Colour**: `"#DC241F"` (London Bus Red)
- **Headway / Frequency**: ~8–10 minutes
- **Boarding Stop**: `Charing Cross Stn / Trafalgar Square` (Stop F, NaPTAN `490013766F`)
- **Alighting Stop**: `Shoreditch High Street Station` (Stop F, NaPTAN `490005524F`)
- **Destination**: `"Shoreditch"`
- **Journey Timings**:
  - `boarding_walk_seconds`: `240` (4 minutes from Nelson's Column doorstep to Stop F)
  - `prep_seconds`: `120` (2 minutes preparation buffer)
  - Doorstep leave countdown: $\text{seconds\_to\_leave} = \text{seconds\_to\_board} - (240 + 120)$
  - `transit_duration_seconds`: `1920` (32 minutes in-bus transit)
  - `alighting_walk_seconds`: `600` (10 minutes walk from Shoreditch High St to Brick Lane)
- **Corridor Stop Geometry** (approaching boarding stop):
  1. Terminus: Victoria Station (`490000248H`, `"Victoria"`, ~20–25m transit to target, ~14–19m advance warning before doorstep threshold)
  2. Intermediate 1: Westminster Cathedral (`490014496N`, `"Westminster Cathedral"`)
  3. Intermediate 2: Westminster City Hall (`490003384SA`, `"Westminster City Hall"`)
  4. Intermediate 3: St James's Park Station (`490010260SC`, `"St James"`)
  5. Intermediate 4: Westminster Abbey (`490014495R`, `"Westminster Abbey"`)
  6. Intermediate 5: Westminster Stn / Parliament Square (`490015048A`, `"Westminster"`)
  7. Intermediate 6: Horse Guards Parade (`490008376N`, `"Horse Guards"`)
  8. Boarding Stop: Charing Cross Stn / Trafalgar Square (`490013766F`, `"Trafalgar Sq"`, `is_target: true`)

### Route 2: Train (Southeastern Rail)
- **Mode**: `train`
- **Line**: `"southeastern"`
- **Provider**: `"tfl"`
- **Direction**: `from_home`
- **Route Colour**: `"#0019A8"` (Southeastern Blue)
- **Headway / Frequency**: ~15 minutes
- **Boarding Stop**: `London Charing Cross Rail Station` (NaPTAN `910GCHRX`, terminus station)
- **Alighting Stop**: `London Bridge Rail Station` (NaPTAN `910GLNDNBDC`)
- **Destination**: `"London Bridge"`
- **Journey Timings**:
  - `boarding_walk_seconds`: `240` (4 minutes walk from doorstep to station concourse)
  - `prep_seconds`: `120` (2 minutes preparation buffer)
  - Doorstep leave countdown: $\text{seconds\_to\_leave} = \text{seconds\_to\_board} - (240 + 120)$
  - `transit_duration_seconds`: `480` (8 minutes scheduled rail transit)
  - `alighting_walk_seconds`: `900` (15 minutes walk / transfer from London Bridge to Brick Lane)
- **Corridor Stop Geometry** (approaching boarding station):
  - *Terminus Concourse Tracking Model*: Because London Charing Cross is a buffer-stop rail terminus where trains originate from the platform, there is no upstream approach corridor of pre-boarding stations. The tracking model evaluates scheduled platform departure boards and gate status rather than multi-station progression. To ensure the commuter receives sufficient advance warning prior to the doorstep threshold (4m walk + 2m prep = 6m), the journey planner query evaluates forward schedule pagination (`timeAdjustments.later`), maintaining a 45–60 minute forward departure horizon (minimum 8–10 scheduled services).
  1. Origin & Boarding Stop: London Charing Cross Rail Station (`910GCHRX`, `"Charing Cross"`, `is_target: true`, terminus concourse)
  2. Direct Rail Transit: London Charing Cross $\rightarrow$ London Bridge (non-stop direct line)
  3. Alighting Stop: London Bridge Rail Station (`910GLNDNBDC`, `"London Bridge"`)

### Route 3: Deep Underground Tube (Central Line)
- **Mode**: `tube`
- **Line**: `"central"`
- **Provider**: `"tfl"`
- **Direction**: `from_home`
- **Route Colour**: `"#E32017"` (Central Line Red)
- **Headway / Frequency**: ~2–3 minutes (24–30 trains/hour)
- **Boarding Stop**: `Tottenham Court Road Underground Station` (NaPTAN `940GZZLUTCR`, through-station)
- **Alighting Stop**: `Liverpool Street Underground Station` (NaPTAN `940GZZLULVT`)
- **Destination**: `"Liverpool Street"`
- **Journey Timings**:
  - `boarding_walk_seconds`: `600` (10 minutes walk from Nelson's Column doorstep to Tottenham Court Road concourse)
  - `prep_seconds`: `120` (2 minutes preparation buffer)
  - Doorstep leave countdown: $\text{seconds\_to\_leave} = \text{seconds\_to\_board} - (600 + 120)$
  - `transit_duration_seconds`: `480` (8 minutes scheduled transit direct)
  - `alighting_walk_seconds`: `480` (8 minutes walk from Liverpool Street to Brick Lane)
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
- `"leave_now"`: Doorstep departure deadline reached ($\text{seconds\_to\_leave} \le 0$).

> [!IMPORTANT]
> **Reachability Rollover (Pre-Departure Miss Detection)**:
> Rollover occurs **before the vehicle departs**, governed strictly by physical reachability from the commuter's doorstep:
> 1. **Comfortable Departure Target**: Calculated as $\text{leave\_by\_time} = \text{expected\_boarding\_time} - (\text{boarding\_walk\_seconds} + \text{prep\_seconds})$.
> 2. **Leeway / Grace Window**: Once $\text{seconds\_to\_leave} \le 0$, the state transitions to `"leave_now"`. The vehicle remains the active candidate while physically reachable: $\text{seconds\_to\_board} \ge \text{boarding\_walk\_seconds} - \text{grace\_seconds}$ (or equivalently $\text{seconds\_to\_leave} \ge -(\text{prep\_seconds} + \text{grace\_seconds})$), allowing the commuter to rush or run to the stop.
> 3. **Unreachable / Missed Cutoff**: Once $\text{seconds\_to\_board} < \text{boarding\_walk\_seconds} - \text{grace\_seconds}$, the commuter has mathematically **no chance** of reaching the stop before the vehicle leaves. At that moment, the vehicle is discarded as **missed** and removed from the active plan, regardless of its actual physical location along the corridor or whether it has arrived at the boarding stop yet.
> 4. **Rollover Transition**: The engine immediately advances to track the subsequent scheduled transit service. If a next vehicle exists, urgency rolls back to `"relaxed"` (or `"prepare"` if close behind). If no reachable service remains or the active window closes, the state transitions to `"idle"`.

All departure times and countdown metrics are provided via attributes (`expected_boarding_time`, `leave_by_time`, `seconds_to_board`, `seconds_to_leave`).

### Attributes Table

| Attribute | Type | Description | Exemplar Value |
| :--- | :--- | :--- | :--- |
| `commute_id` | `str` | Unique identifier of the commute | `"nelson_to_brick_lane"` |
| `commute_title` | `str` | Display title for the card header | `"Nelson's Column to Brick Lane"` |
| `person_name` | `str` | Name of the commuter (if configured) | `"Commuter"` |
| `person_picture` | `str` | URL or local path to person image (if configured) | `""` |
| `active_option` | `str` | ID of the currently selected optimal route | `"bus_26"` |
| `options` | `list[str]` | List of all configured child route option IDs | `["bus_26", "train_southeastern", "tube_central"]` |
| `child_entities` | `list[str]` | Entity IDs of all associated child route sensors | `["sensor.commute_nelson_to_brick_lane_bus_26", ...]` |
| `is_relevant` | `bool` | Whether the commute is currently active | `true` |
| `urgency_stage` | `str` | Commute urgency lifecycle phase | `"standby"` \| `"relaxed"` \| `"prepare"` \| `"leave_now"` |
| `pill_label` | `str` | Header badge text | `"Standby"` \| `"Leave in 4m"` \| `"🚨 LEAVE NOW"` |
| `pill_color` | `str` | Hex colour code for badge text and accent | `"#4CAF50"` \| `"#FF9800"` \| `"#FF5252"` \| `"#8E8E93"` |
| `pill_bg` | `str` | RGBA colour for badge background | `"rgba(76, 175, 80, 0.15)"` |
| `pill_border` | `str` | Border colour for badge | `"#4CAF50"` |
| `route_label` | `str` | Line or route short identifier | `"26"` \| `"Southeastern"` \| `"Central"` |
| `route_color` | `str` | Primary branding colour of active route | `"#DC241F"` \| `"#0019A8"` \| `"#E32017"` |
| `destination` | `str` | Final destination of active route transit | `"Shoreditch"` \| `"London Bridge"` \| `"Liverpool Street"` |
| `line_status_label` | `str` | TfL / Operator service status description | `"Good Service"` \| `"Minor Delays"` |
| `line_status_detail` | `str` \| `None` | Disruption reasoning text if applicable | `None` |
| `line_status_color` | `str` | Status icon colour hex | `"#4CAF50"` \| `"#FF9800"` \| `"#F44336"` |
| `line_status_icon` | `str` | Status icon symbol | `"mdi:check-circle"` \| `"mdi:alert"` |
| `is_delayed` | `bool` | Boolean flag indicating operational delay | `false` |
| `is_cancelled` | `bool` | Boolean flag indicating suspension or cancellation | `false` |
| `expected_boarding_time` | `str` | Expected departure time at boarding stop (`HH:MM`) | `"08:24"` |
| `expected_destination_time` | `str` | Expected arrival time at journey destination (`HH:MM`) | `"09:06"` |
| `leave_by_time` | `str` | Recommended doorstep departure time (`HH:MM`) | `"08:18"` |
| `seconds_to_board` | `int` \| `None` | Seconds until transit arrives at boarding stop | `312` |
| `seconds_to_leave` | `int` \| `None` | Seconds until commuter must leave doorstep | `132` |
| `expected_destination_margin_seconds` | `int` \| `None` | Buffer seconds relative to target deadline | `240` |
| `will_arrive_on_time` | `bool` | Whether route arrives before target deadline | `true` |
| `timeliness` | `str` | Normalised timeliness classification | `"on_time"` \| `"early"` \| `"late"` \| `"delayed"` \| `"cancelled"` |
| `strategy` | `str` | Arbitration strategy applied | `"late_with_buffer"` \| `"soonest"` \| `"latest"` |
| `next_summary` | `str` | Formatted summary of subsequent service | `"Next at 08:36 (in 12m)"` \| `"None scheduled"` |

---

## 4. Child Route Sensor (`sensor.commute_<commute_id>_<route_id>`)

### Entity Identifiers
- Bus: `sensor.commute_nelson_to_brick_lane_bus_26`
- Train: `sensor.commute_nelson_to_brick_lane_train_southeastern`
- Tube: `sensor.commute_nelson_to_brick_lane_tube_central`

### State
Urgency stage matching the Master Rollup: `"standby"`, `"relaxed"`, `"prepare"`, `"leave_now"` (or `"idle"` when coordinator is dormant).

### Attributes Table

| Attribute | Type | Description | Exemplar Value |
| :--- | :--- | :--- | :--- |
| `commute_id` | `str` | Unique identifier of the commute | `"nelson_to_brick_lane"` |
| `route_id` | `str` | Unique route option identifier | `"bus_26"` |
| `mode` | `str` | Transit mode identifier | `"bus"` \| `"train"` \| `"tube"` |
| `line` | `str` | Line identifier or service code | `"26"` \| `"southeastern"` \| `"central"` |
| `provider` | `str` | Transit provider plugin ID | `"tfl"` |
| `direction` | `str` | Direction of travel | `"from_home"` \| `"to_home"` |
| `route_label` | `str` | Short display label | `"26"` |
| `route_color` | `str` | Branding hex colour code | `"#DC241F"` |
| `destination` | `str` | Transit vehicle destination | `"Shoreditch"` |
| `is_relevant` | `bool` | Whether route evaluation is active | `true` |
| `urgency_stage` | `str` | Route urgency lifecycle phase | `"relaxed"` |
| `leave_by_time` | `str` | Recommended doorstep departure time (`HH:MM`) | `"08:18"` |
| `expected_boarding_time` | `str` | Boarding stop expected time (`HH:MM`) | `"08:24"` |
| `expected_alighting_time` | `str` | Alighting stop expected time (`HH:MM`) | `"08:56"` |
| `expected_destination_time` | `str` | Final destination arrival time (`HH:MM`) | `"09:06"` |
| `seconds_to_leave` | `int` \| `None` | Seconds until commuter must leave | `132` |
| `seconds_to_board` | `int` \| `None` | Seconds until transit arrives at stop | `312` |
| `expected_destination_margin_seconds` | `int` \| `None` | Buffer seconds relative to target deadline | `240` |
| `will_arrive_on_time` | `bool` | Whether route arrives before target deadline | `true` |
| `timeliness` | `str` | Normalised timeliness classification | `"on_time"` |
| `vehicle_id` | `str` \| `None` | Active transit vehicle registration/identifier | `"LX11BFA"` |
| `corridor_location` | `str` \| `None` | Natural language vehicle position | `"Between Horse Guards and Trafalgar Sq"` |
| `corridor_progress` | `float` \| `None` | Fractional progression index along corridor | `6.5` |
| `corridor_stops` | `list[dict]` \| `None` | Ordered schematic corridor stops | `[{"short_name": "...", "is_target": false}]` |
| `next_vehicle_id` | `str` \| `None` | Subsequent service vehicle identifier | `"LX11BFB"` |
| `seconds_to_next_board` | `int` \| `None` | Seconds until subsequent vehicle boards | `720` |
| `next_summary` | `str` | Formatted summary of subsequent service | `"Next at 08:36 (in 12m)"` |
| `line_status_label` | `str` | Operator line status description | `"Good Service"` |
| `line_status_detail` | `str` \| `None` | Disruption reasoning text if applicable | `None` |
| `line_status_color` | `str` | Status icon colour hex | `"#4CAF50"` |
| `line_status_icon` | `str` | Status icon symbol | `"mdi:check-circle"` |
| `is_delayed` | `bool` | Operational delay indicator | `false` |
| `is_cancelled` | `bool` | Operational cancellation indicator | `false` |
| `pill_label` | `str` | Header badge text | `"Leave in 4m"` |
| `pill_color` | `str` | Hex colour code for badge text | `"#FF9800"` |
| `pill_bg` | `str` | RGBA colour for badge background | `"rgba(255, 152, 0, 0.15)"` |
| `pill_border` | `str` | Border colour for badge | `"#FF9800"` |

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
A transit departure $k$ with arrival countdown $t_k$ (`seconds_to_board` at the boarding stop) is deemed **physically reachable** from the commuter's doorstep if and only if:
$$\text{seconds\_to\_board}_k \ge \text{boarding\_walk\_seconds} - \text{grace\_seconds}$$
or in terms of the doorstep departure countdown:
$$\text{seconds\_to\_leave}_k = \text{seconds\_to\_board}_k - (\text{boarding\_walk\_seconds} + \text{prep\_seconds}) \ge -(\text{prep\_seconds} + \text{grace\_seconds})$$
- If $\text{seconds\_to\_board}_k < \text{boarding\_walk\_seconds} - \text{grace\_seconds}$, departure $k$ is mathematically unreachable and marked **missed**. The engine immediately discards it and evaluates departure $k+1$, regardless of whether vehicle $k$ is still en route.
- $\text{grace\_seconds}$ provides user leeway beyond the comfortable recommendation (e.g. running to the stop), after which reaching the stop before departure is impossible.

### Multi-Route Arbitration
When evaluating multiple routes for the Master Rollup:
1. **Filter Reachable**: Eliminate routes with no reachable services.
2. **Timeliness Partitioning**: Prioritise routes that arrive before the target deadline (`will_arrive_on_time: true`, where $\text{expected\_destination\_margin\_seconds} \ge 0$). Late routes are only considered if no reachable on-time route exists.
3. **Catchability Partitioning**: Prioritise comfortable departures ($\text{seconds\_to\_leave} \ge 0$) over sprint options ($\text{seconds\_to\_leave} < 0$).
4. **Arbitration Strategy**: Apply the configured `rollup_strategy` (`late_with_buffer`, `soonest`, or `latest`) based on `seconds_to_leave`.
5. **Tie-Breaking**: When multiple candidates have equal `seconds_to_leave`, the candidate with greater `expected_destination_margin_seconds` is selected.
6. **Idle Fallback**: If no reachable service exists across all options, the commute transitions to `"standby"` (or `"idle"` if inactive).


