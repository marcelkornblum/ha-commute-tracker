# TfL Transit Fixture Capture Guide

This guide details how and when to capture real-time Transport for London (TfL) live transit fixtures for the `ha-commute-tracker` integration test suite.

---

## Exemplar Journey: Nelson's Column to Brick Lane

To ensure reproducibility while maintaining commuter privacy, all integration tests and sample fixtures model an anonymous canonical London commute with three multi-modal options:

- **Origin**: Nelson's Column, Trafalgar Square (`51.5078, -0.1280`)
- **Destination**: Brick Lane, London E1 (`51.5215, -0.0715`)

### Multiple Route Options

1. **Surface Bus Option**: Daytime TfL Bus Line **26** (Victoria $\rightarrow$ Waterloo $\rightarrow$ Shoreditch High Street)
   - **Boarding Stop**: Charing Cross Stn / Trafalgar Square (`490013766F`, Stop F)
   - **Alighting Stop**: Shoreditch High Street Station (`490005524F`, Stop L)
   - **Headway / Frequency**: ~8–10 minutes
   - **Approach Corridor Stops**: Victoria (`490000248H`), Westminster Cathedral (`490014496N`), Westminster City Hall (`490003384SA`), St James's Park (`490010260SC`), Westminster Abbey (`490014495R`), Westminster (`490015048A`), Horse Guards (`490008376N`)

2. **Terminus Rail Option**: Southeastern National Rail (Charing Cross $\rightarrow$ London Bridge)
   - **Boarding Station**: London Charing Cross Rail Station (`910GCHRX`, rail terminus)
   - **Alighting Station**: London Bridge Rail Station (`910GLNDNBDC`)
   - **Headway / Frequency**: ~15 minutes
   - **Corridor Tracking Model**: Originates from terminus buffer stops at London Charing Cross without upstream intermediate stations; tracking observes scheduled platform departure countdowns and gate status rather than multi-station progression. Follows forward schedule pagination (`timeAdjustments.later`) to secure a 45–60 minute departure horizon (8–10 scheduled services).

3. **Through-Corridor Tube Option**: London Underground Central Line (North Acton $\rightarrow$ Liverpool Street)
   - **Boarding Station**: Tottenham Court Road Underground Station (`940GZZLUTCR`, through-station)
   - **Alighting Station**: Liverpool Street Underground Station (`940GZZLULVT`, foot of Brick Lane / Spitalfields)
   - **Headway / Frequency**: ~2–3 minutes (24–30 trains/hour)
   - **Approach Corridor Stations**: North Acton (`940GZZLUNAN`), East Acton (`940GZZLUEAN`), White City (`940GZZLUWCY`), Shepherd's Bush (`940GZZLUSBC`), Holland Park (`940GZZLUHPK`), Notting Hill Gate (`940GZZLUNHG`), Queensway (`940GZZLUQWY`), Lancaster Gate (`940GZZLULGT`), Marble Arch (`940GZZLUMBA`), Bond Street (`940GZZLUBND`), Oxford Circus (`940GZZLUOXC`)

---

## When to Capture Fixtures

Live TfL arrival predictions are generated strictly from active vehicle Automatic Vehicle Location (AVL) GPS transponders and signaling blocks. Fixtures must be captured when the service is actively operating with vehicles on the route.

### Recommended Timing Windows
- **Optimal Daytime Window**: **Monday to Saturday between 10:00 and 16:00 BST**
  - Continuous headway across all 3 routes (Central line ~2-3m, Bus 26 ~8-10m, Southeastern ~15m).
  - Regular Southeastern train departures from Charing Cross to London Bridge.
  - Stable progression along both Oxford Street/Central and Whitehall/Bus corridors without excessive disruption.
- **Alternative Peak Windows**:
  - **Morning Peak**: **07:30 – 09:30 BST** (high frequency, multiple vehicles simultaneously approaching the target stops).
  - **Evening Peak**: **16:30 – 18:30 BST** (heavy traffic and variable transit progression testing).

### Times to Avoid
- **Night Hours (00:30 – 05:45 BST)**: Daytime Route 26 does not run overnight. Calling `/Line/26/Arrivals` during these hours returns empty arrays (`[]`).
- **Major Network Closures**: National rail strikes or planned engineering closures on the active corridors.

---

## How to Capture Fixtures

Run the automated capture script using `uv`:

```bash
uv run python scripts/capture_tfl.py --time-series-count 90 --time-series-interval 30.0
```

### Execution Details
- **Duration**: ~45 minutes total.
- **Poll Interval**: 30 seconds.
- **Snapshot Count**: 90 multi-modal snapshots capturing multiple full vehicle arrival cycles, doorstep reachability rollovers, approach progression, and multi-vehicle headway tracking for both surface road and underground rail corridors.

---

## Generated Fixture Layout

Running the script populates `tests/fixtures/` with the following structure:

```
tests/fixtures/
├── README.md                                  # This guide
├── tfl_arrivals.json                          # Root backwards-compatibility snapshot
└── commute_nelson_to_brick_lane/
    ├── set1_poc_bus_discrete/                 # PoC multi-request stop arrivals
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
    ├── set2_poc_train_discrete/               # Legacy PoC rail journey results (terminus)
    │   ├── 01_journey_results.json
    │   └── 02_line_status.json
    ├── set3_consolidated_bus/                 # Optimised line-wide bus arrivals
    │   ├── line_arrivals.json
    │   └── line_status.json
    ├── set4_consolidated_train/               # Consolidated rail journey results (terminus)
    │   ├── journey_results.json
    │   └── line_status.json
    ├── set5_poc_tube_discrete/                # Discrete tube station arrivals (non-terminus)
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
    ├── set6_consolidated_tube/                # Consolidated tube line arrivals & journey
    │   ├── line_arrivals.json
    │   ├── journey_results.json
    │   └── line_status.json
    └── time_series/                           # 45-minute multi-modal corridor progression
        ├── snapshot_001.json                  # Combined bus + tube corridor snapshot
        ├── ...
        ├── snapshot_090.json
        └── series_manifest.json               # Index of all snapshots and vehicle IDs
```

---

## Post-Capture Verification

After completing a capture run, verify that the payloads contain active transit data and that tests pass:

```bash
# 1. Verify that line arrivals payload contains active vehicles
python -c "import json; data=json.load(open('tests/fixtures/commute_nelson_to_brick_lane/set3_consolidated_bus/line_arrivals.json')); print(f'Active buses: {len(data)}'); assert len(data) > 0"
python -c "import json; data=json.load(open('tests/fixtures/commute_nelson_to_brick_lane/set6_consolidated_tube/line_arrivals.json')); print(f'Active trains: {len(data)}'); assert len(data) > 0"

# 2. Run test suite
uv run pytest tests/test_capture_tfl.py

# 3. Verify code style and formatting
uv run ruff check scripts/ tests/
uv run mypy scripts/ tests/
```
