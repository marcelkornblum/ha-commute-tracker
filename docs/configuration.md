# Configuration Reference & Schema Guide

This document is the definitive reference for configuring `ha-commute-tracker` in Home Assistant's `configuration.yaml`. It details all configuration options across the **Root**, **Commute**, and **Route** scopes, explaining their purposes, units, defaults, cascading inheritance rules, and mutual exclusivity constraints.

---

## 1. Domain Terminology & Concepts

Before configuring journeys, it is helpful to understand the core terminology used throughout the integration:

- **Doorstep**: The journey origin (the commuter's front door when departing from home).
- **Destination**: The final journey destination (e.g. office, school, or home on return).
- **Boarding Stop (`boarding_stop`)**: The physical stop or station where the commuter boards transit.
- **Alighting Stop (`alighting_stop`)**: The stop or station where the commuter alights from transit.
- **Boarding Walk (`boarding_walk_seconds`)**: Walking duration from doorstep to the boarding stop.
- **Preparation Buffer (`prep_seconds`)**: Time required inside the home before leaving (e.g. finding keys, putting on coat/shoes).
- **Doorstep Countdown (`seconds_to_leave`)**: Seconds remaining until the commuter must step out of the front door:
  $$\text{seconds\_to\_leave} = \text{seconds\_to\_board} - (\text{boarding\_walk\_seconds} + \text{prep\_seconds})$$
- **Grace Leeway (`grace_seconds` / `grace_fraction`)**: Rushing buffer allowing the commuter to catch a vehicle after the comfortable doorstep leave deadline has expired.
- **Physical Reachability**: A vehicle is reachable if and only if:
  $$\text{seconds\_to\_board} \ge \text{boarding\_walk\_seconds} - \text{grace\_seconds}$$
  When a vehicle fails this condition, it is marked **missed** and the engine rolls over to track the next departure.
- **Transit Duration (`transit_duration_seconds`)**: Scheduled or in-vehicle transit time between the boarding stop and alighting stop.
- **Alighting Walk (`alighting_walk_seconds`)**: Walking duration from the alighting stop to the final destination.
- **Expected Destination Margin (`expected_destination_margin_seconds`)**: Spare seconds between the expected arrival time at the final destination and the planned deadline (`target_destination_time`). Positive values indicate arriving early; negative values indicate arriving late.

---

## 2. Configuration Scopes & Cascading Inheritance

Options can be defined at three hierarchical scopes. Lower scopes inherit and override higher scopes:

```text
Root Scope (commute_tracker:)
  │  ├── Providers credentials (TfL, etc.)
  │  ├── Global poll_interval
  │  ├── Global grace_seconds / grace_fraction
  │  ├── Global rollup_strategy / route_late_buffer_seconds
  │  ├── Global prep_seconds / boarding_walk_seconds
  │  └── Commutes list (commutes:)
  │
  └── Commute Scope (commutes:)
        │  ├── Commute identity (id, name, person)
        │  ├── Active wake sensor (active_sensor)
        │  ├── Target arrival deadline (target_destination_time)
        │  ├── Arbitration strategy (rollup_strategy, route_late_buffer_seconds)
        │  ├── Commute poll_interval
        │  ├── Commute grace_seconds / grace_fraction
        │  ├── Commute prep_seconds / boarding_walk_seconds
        │  └── Route options list (routes:)
        │
        └── Route Scope (routes:)
              ├── Transit mode & line (mode, line, provider, direction)
              ├── Stops & destination (boarding_stop, alighting_stop, destination)
              ├── Walking & transit buffers (boarding_walk_seconds, prep_seconds, etc.)
              ├── Route-level grace_seconds / grace_fraction
              ├── Corridor stops for approach tracking (corridor_stops)
              └── Route colour & labels (route_color, name)
```

### Cascading Resolution Hierarchy

When the calculation engine evaluates thresholds for a route, it resolves values using the following strict precedence:

| Parameter | Tier 1 (Highest) | Tier 2 | Tier 3 | Tier 4 | Tier 5 (Lowest) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`boarding_walk_seconds`** | HA Helper `boarding_walk_seconds` | Route config | Commute config | Root config | Default: `240` (4m) |
| **`prep_seconds`** | HA Helper `prep_seconds` | Route config | Commute config | Root config | Default: `120` (2m) |
| **`grace_seconds`** | HA Helper `grace_seconds` | HA Helper `grace_fraction` | Route config (`seconds` / `fraction`) | Commute config (`seconds` / `fraction`) | Root config / Default: `25%` |
| **`target_destination_time`** | HA Helper `target_destination_time` | Commute config | — | — | None (untimed) |
| **`rollup_strategy`** | — | — | Commute config | Root config | Default: `"late_with_buffer"` |
| **`route_late_buffer_seconds`** | — | — | Commute config | Root config | Default: `300` (5m) |
| **`poll_interval`** | — | — | Commute config | Root config | Default: `30` (30s) |

---

## 3. Mutual Exclusivity: `grace_seconds` vs `grace_fraction`

Within any single configuration block (**Root**, **Commute**, or **Route**), you may configure **either** `grace_seconds` **or** `grace_fraction`, but **never both**.

### Why They Are Mutually Exclusive
- `grace_seconds` specifies a **fixed, absolute number of seconds** (e.g. `120` seconds).
- `grace_fraction` specifies a **relative proportion** of the route's walking duration (e.g. `0.25` = 25% of `boarding_walk_seconds`).

Specifying both in the same configuration block creates an ambiguous definition of leeway. The schema validator enforces `vol.Exclusive` and will reject the configuration if both keys are present in the same block.

---

## 4. Root-Level Options (`commute_tracker:`)

The root block defines shared provider credentials and global defaults.

| Option | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `providers` | `dict` | Optional | `{}` | Credentials for transit authority APIs. Keyed by provider ID (e.g. `tfl`). |
| `grace_seconds` | `positive_int` | Optional | — | Global fallback grace leeway in seconds. Mutually exclusive with `grace_fraction`. |
| `grace_fraction` | `small_float` | Optional | `0.25` | Global fallback grace proportion of walking time (between `0.0` and `1.0`). Mutually exclusive with `grace_seconds`. |
| `rollup_strategy` | `enum` | Optional | `"late_with_buffer"` | Global default arbitration strategy for all commutes (`"late_with_buffer"`, `"soonest"`, `"latest"`). |
| `route_late_buffer_seconds` | `positive_int` | Optional | `300` | Global default buffer in seconds for `"late_with_buffer"` strategy. |
| `prep_seconds` | `positive_int` | Optional | `120` | Global default preparation buffer in seconds before doorstep departure. |
| `boarding_walk_seconds` | `positive_int` | Optional | `240` | Global default walking duration in seconds from doorstep to transit boarding stop. |
| `poll_interval` | `positive_int` | Optional | `30` | Default polling interval in seconds for all commutes while awake. |
| `commutes` | `list` | **Required** | — | List of one or more commute definitions. |

### Provider Credentials (`providers:`)

#### `tfl`
Credentials for Transport for London's Unified API. Register at [api.tfl.gov.uk](https://api.tfl.gov.uk/).
- `app_id` (`str`, optional): TfL Application ID.
- `app_key` (`str`, optional): TfL Primary Application Key.

```yaml
commute_tracker:
  providers:
    tfl:
      app_id: "your_tfl_app_id"
      app_key: "your_tfl_app_key"
```

---

## 5. Commute-Level Options (`commutes:`)

Each entry in `commutes` represents a distinct daily journey (e.g. "Morning Commute", "Evening Return"). It produces a Master Rollup sensor (`sensor.commute_<id>`).

| Option | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `name` | `str` | **Required** | — | Human-readable title for the commute (e.g. `"Morning Commute to Work"`). |
| `id` / `unique_id` | `str` | Optional | Slug of `name` | Unique slug identifier. Determines entity ID: `sensor.commute_<id>`. |
| `active_sensor` | `entity_id` | **Required** | — | Entity ID of a Home Assistant binary sensor or schedule helper (e.g. `binary_sensor.morning_commute_window`). When `on`, polling is active; when `off`, the commute idles and polling stops. |
| `target_destination_time` | `str` | Optional | `None` | Target arrival deadline at final destination in `HH:MM` or ISO timestamp format (e.g. `"09:00"`). Used to compute destination margins and timeliness. |
| `person_name` | `str` | Optional | `None` | Commuter's display name, shown in the Lovelace card header badge. |
| `person_picture` | `str` | Optional | `None` | Image URL or local path (`/local/...`) for commuter avatar on the card. |
| `rollup_strategy` | `enum` | Optional | `"late_with_buffer"` | Strategy used to arbitrate the active route promoted to the Master Rollup. Choices: `"late_with_buffer"`, `"soonest"`, `"latest"`. |
| `route_late_buffer_seconds` | `positive_int` | Optional | `300` | Safety buffer in seconds used by `"late_with_buffer"` strategy (5 minutes default). |
| `prep_seconds` | `positive_int` | Optional | Inherited / `120` | Commute-wide preparation buffer in seconds before doorstep departure. |
| `boarding_walk_seconds` | `positive_int` | Optional | Inherited / `240` | Commute-wide walking duration in seconds from doorstep to transit boarding stop. |
| `grace_seconds` | `positive_int` | Optional | — | Commute-wide grace buffer in seconds. Overrides root settings; mutually exclusive with `grace_fraction`. |
| `grace_fraction` | `small_float` | Optional | — | Commute-wide grace fraction of walk time (`0.0` to `1.0`). Overrides root settings; mutually exclusive with `grace_seconds`. |
| `poll_interval` | `positive_int` | Optional | `30` | Polling cycle in seconds for this commute, overriding the root default. |
| `routes` | `list` | **Required** | — | List of one or more transit route options available for this commute. |

### Rollup Strategies Explained (`rollup_strategy`)

When multiple routes are active, the Master Rollup promotes one route as the recommended option:

1. **`late_with_buffer` (Default)**:
   - Sorts viable on-time routes by departure deadline (`seconds_to_leave`).
   - If the top two latest options are within `route_late_buffer_seconds` (default: 300s / 5m) of each other, the engine selects the **earlier** candidate so that the later departure serves as a comfortable safety buffer/fallback.
   - If the gap exceeds the buffer, it selects the latest candidate.
2. **`soonest`**:
   - Strictly promotes the route that departs the soonest (`min(seconds_to_leave)` where positive). Ideal when you want to leave immediately.
3. **`latest`**:
   - Strictly promotes the route that departs latest while still arriving at the destination on time. Maximises your time at home.

---

## 6. Route-Level Options (`routes:`)

Each entry in `routes` defines an alternative transit option (e.g. Bus 26 vs Southeastern Rail vs Central Line Tube). It produces a Child Route sensor (`sensor.commute_<commute_id>_<route_id>`).

| Option | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `mode` | `enum` | **Required** | — | Transit mode. Choices: `"bus"`, `"train"`, `"tube"`, `"tram"`, `"ferry"`. |
| `line` | `str` | **Required** | — | Line identifier or service code (e.g. `"26"`, `"southeastern"`, `"central"`). |
| `provider` | `str` | Optional | `"tfl"` | Transit provider plugin ID. Defaults to `"tfl"`. |
| `direction` | `enum` | Optional | `"from_home"` | Direction of journey relative to home origin. Choices: `"from_home"`, `"to_home"`. |
| `name` | `str` | Optional | Derived | Human-readable label (e.g. `"Bus 26 via Shoreditch"`). If omitted, derived from mode and line. |
| `id` / `unique_id` | `str` | Optional | Slug of `line` | Unique route slug (e.g. `"bus_26"`). Determines child entity ID. |
| `route_color` | `str` | Optional | Mode colour | Primary branding colour hex code for badges, tracks, and UI icons (e.g. `"#DC241F"`). |
| `boarding_stop` | `str` | Optional | `None` | NaPTAN or station code where commuter boards (e.g. `"490013766F"`). |
| `alighting_stop` | `str` | Optional | `None` | NaPTAN or station code where commuter alights (e.g. `"490005524F"`). |
| `destination` | `str` | Optional | `None` | Transit vehicle terminal destination string for filtering or display (e.g. `"Shoreditch"`). |
| `boarding_walk_seconds` | `positive_int` | Optional | `240` | Walking duration in seconds from doorstep to `boarding_stop` (default: 4m). |
| `prep_seconds` | `positive_int` | Optional | `120` | Preparation buffer in seconds before stepping out the door (default: 2m). |
| `grace_seconds` | `positive_int` | Optional | — | Route-specific grace buffer in seconds. Mutually exclusive with `grace_fraction`. |
| `grace_fraction` | `small_float` | Optional | — | Route-specific grace fraction of walk time (`0.0` to `1.0`). Mutually exclusive with `grace_seconds`. |
| `transit_duration_seconds`| `positive_int` | Optional | `None` | In-transit travel duration in seconds between boarding and alighting stops (e.g. `1920` for 32m). |
| `alighting_walk_seconds` | `positive_int` | Optional | `None` | Walking duration in seconds from alighting stop to final destination (e.g. `600` for 10m). |
| `corridor_stops` | `list[str]` | Optional | `[]` | Ordered list of upstream stop/station IDs leading to the boarding stop for approach tracking. |

---

## 7. Complete Configuration Examples

### Minimal Single-Route Commute

A simple morning bus commute tracking Bus 73 to work:

```yaml
commute_tracker:
  commutes:
    - name: "Morning Bus"
      active_sensor: binary_sensor.morning_commute_active
      target_destination_time: "08:45"
      routes:
        - mode: "bus"
          line: "73"
          boarding_stop: "490010478N"
          destination: "Victoria"
          boarding_walk_seconds: 300
          prep_seconds: 120
          transit_duration_seconds: 1200
          alighting_walk_seconds: 360
```

---

### Multi-Option Exemplar: Nelson's Column to Brick Lane

A complete configuration setup replicating the canonical reference commute with three route options (Bus 26, Southeastern Rail, and Central Line Tube):

```yaml
commute_tracker:
  providers:
    tfl:
      app_id: !secret tfl_app_id
      app_key: !secret tfl_app_key
  poll_interval: 30
  grace_fraction: 0.25

  commutes:
    - name: "Nelson's Column to Brick Lane"
      id: "nelson_to_brick_lane"
      person_name: "Commuter"
      active_sensor: binary_sensor.commute_nelson_to_brick_lane_relevant
      target_destination_time: "09:00"
      rollup_strategy: "late_with_buffer"
      route_late_buffer_seconds: 300

      routes:
        # Route 1: Daytime Bus 26
        - id: "bus_26"
          name: "Bus 26 to Shoreditch"
          mode: "bus"
          line: "26"
          provider: "tfl"
          direction: "from_home"
          route_color: "#DC241F"
          boarding_stop: "490013766F"
          alighting_stop: "490005524F"
          destination: "Shoreditch"
          boarding_walk_seconds: 240      # 4 minutes walk
          prep_seconds: 120              # 2 minutes prep
          grace_seconds: 180             # 3 minutes sprint leeway
          transit_duration_seconds: 1920 # 32 minutes in-bus
          alighting_walk_seconds: 600    # 10 minutes walk to Brick Lane
          corridor_stops:
            - "490000248H"   # Victoria Station (Terminus)
            - "490014496N"   # Westminster Cathedral
            - "490003384SA"  # Westminster City Hall
            - "490010260SC"  # St James's Park Station
            - "490014495R"   # Westminster Abbey
            - "490015048A"   # Westminster Station
            - "490008376N"   # Horse Guards Parade
            - "490013766F"   # Charing Cross Stn / Trafalgar Square (Boarding)

        # Route 2: Southeastern Rail
        - id: "train_southeastern"
          name: "Southeastern to London Bridge"
          mode: "train"
          line: "southeastern"
          provider: "tfl"
          direction: "from_home"
          route_color: "#0019A8"
          boarding_stop: "910GCHRX"
          alighting_stop: "910GLNDNBDC"
          destination: "London Bridge"
          boarding_walk_seconds: 240     # 4 minutes walk to concourse
          prep_seconds: 120             # 2 minutes prep
          grace_seconds: 360            # 6 minutes concourse leeway
          transit_duration_seconds: 480 # 8 minutes scheduled rail transit
          alighting_walk_seconds: 900   # 15 minutes walk to Brick Lane

        # Route 3: Central Line Tube
        - id: "tube_central"
          name: "Central Line to Liverpool Street"
          mode: "tube"
          line: "central"
          provider: "tfl"
          direction: "from_home"
          route_color: "#E32017"
          boarding_stop: "940GZZLUTCR"
          alighting_stop: "940GZZLULVT"
          destination: "Liverpool Street"
          boarding_walk_seconds: 600     # 10 minutes walk to TCR concourse
          prep_seconds: 120             # 2 minutes prep
          grace_fraction: 0.20          # 20% leeway (120s)
          transit_duration_seconds: 480 # 8 minutes tube transit
          alighting_walk_seconds: 480   # 8 minutes walk to Brick Lane
          corridor_stops:
            - "940GZZLUNAN"  # North Acton
            - "940GZZLUEAN"  # East Acton
            - "940GZZLUWCY"  # White City
            - "940GZZLUSBC"  # Shepherd's Bush
            - "940GZZLUHPK"  # Holland Park
            - "940GZZLUNHG"  # Notting Hill Gate
            - "940GZZLUQWY"  # Queensway
            - "940GZZLULGT"  # Lancaster Gate
            - "940GZZLUMBA"  # Marble Arch
            - "940GZZLUBND"  # Bond Street
            - "940GZZLUOXC"  # Oxford Circus
            - "940GZZLUTCR"  # Tottenham Court Road (Boarding)
```

---

### Return Commute (`direction: "to_home"`)

When travelling back home, set `direction: "to_home"` and designate your home doorstep as the destination:

```yaml
commute_tracker:
  commutes:
    - name: "Evening Commute Home"
      id: "office_to_home"
      active_sensor: binary_sensor.evening_commute_active
      target_destination_time: "18:30"
      routes:
        - id: "bus_26_home"
          mode: "bus"
          line: "26"
          direction: "to_home"
          boarding_stop: "490005524F"    # Shoreditch High St
          alighting_stop: "490013766F"   # Trafalgar Square
          destination: "Home"
          boarding_walk_seconds: 300     # 5m walk from office to Shoreditch stop
          prep_seconds: 180             # 3m pack-up buffer at desk
          transit_duration_seconds: 1920
          alighting_walk_seconds: 240   # 4m walk from Trafalgar Sq to front door
```
