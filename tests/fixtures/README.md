# TfL Transit Fixture Capture Guide

This guide details how and when to capture real-time Transport for London (TfL) live transit fixtures for the `ha-commute-tracker` integration test suite.

---

## Exemplar Journey: Nelson's Column to Brick Lane

To ensure reproducibility while maintaining commuter privacy, all integration tests and sample fixtures model an anonymous canonical London commute with three multi-modal options:

- **Origin**: Nelson's Column, Trafalgar Square (`51.5078, -0.1280`)
- **Destination**: Brick Lane, London E1 (`51.5215, -0.0715`)

### Multiple Route Options

1. **Primary Bus Option**: Daytime TfL Bus Line **26** (Victoria $\rightarrow$ Waterloo $\rightarrow$ Shoreditch High Street)
   - **Boarding Stop**: Charing Cross Stn / Trafalgar Square (`490013766F`, Stop F)
   - **Alighting Stop**: Shoreditch High Street Station (`490005524F`, Stop L)
   - **Approach Corridor Stops**: Victoria (`490000248H`), St James's Park (`490010260SC`), Westminster (`490015048A`), Horse Guards (`490008376N`)
   - **Headway / Frequency**: ~8–10 minutes

2. **Terminus Rail Option**: Southeastern National Rail
   - **Boarding Station**: London Charing Cross Rail Station (`910GCHRX`, rail terminus)
   - **Alighting Station**: London Bridge Rail Station (`910GLNDNBDC`)
   - **Headway / Frequency**: ~15 minutes

3. **Non-Terminus Rail / Tube Option**: London Underground District Line
   - **Boarding Station**: Embankment Underground Station (`940GZZLUEMB`, through-station)
   - **Alighting Station**: Aldgate East Underground Station (`940GZZLUADE`, foot of Brick Lane)
   - **Approach Corridor Stations**: Victoria (`940GZZLUVIC`), St James's Park (`940GZZLUSJP`), Westminster (`940GZZLUWSM`)
   - **Headway / Frequency**: ~4–5 minutes (12–14 trains/hour)
   - **Why this route was added**:
     - Unlike Charing Cross which terminates at the station buffers, Embankment is a through-running station. Trains approach along an active underground tunnel corridor from upstream stations (`Victoria` $\rightarrow$ `St James` $\rightarrow$ `Westminster` $\rightarrow$ `Embankment`), allowing the corridor tracking engine to observe multi-station train progress.
     - Operates with a high-frequency headway (~4–5 min) distinct from both Bus 26 (~8–10 min) and Southeastern rail (~15 min).

---

## When to Capture Fixtures

Live TfL arrival predictions are generated strictly from active vehicle Automatic Vehicle Location (AVL) GPS transponders and signaling blocks. Fixtures must be captured when the service is actively operating with vehicles on the route.

### Recommended Timing Windows
- **Optimal Daytime Window**: **Monday to Saturday between 10:00 and 16:00 BST**
  - Continuous headway across all 3 routes (District line ~4-5m, Bus 26 ~8-10m, Southeastern ~15m).
  - Regular Southeastern train departures from Charing Cross to London Bridge.
  - Stable progression along the Westminster corridor without excessive disruption.
- **Alternative Peak Windows**:
  - **Morning Peak**: **07:30 – 09:30 BST** (high frequency, multiple vehicles simultaneously approaching the target stops).
  - **Evening Peak**: **16:30 – 18:30 BST** (heavy traffic and variable transit progression testing).

### Times to Avoid
- **Night Hours (00:30 – 05:45 BST)**: Daytime Route 26 does not run overnight. Calling `/Line/26/Arrivals` during these hours returns empty arrays (`[]`).
- **Major Network Closures**: National rail strikes or planned weekend engineering closures on the Charing Cross or District line corridors.

---

## How to Capture Fixtures

Run the automated capture script using `uv`:

```bash
uv run python scripts/capture_tfl.py --time-series-count 30 --time-series-interval 30.0
```

### Execution Details
- **Duration**: ~15 minutes total.
- **Poll Interval**: 30 seconds.
- **Snapshot Count**: 30 multi-modal snapshots capturing real-time approach progression, ETA evolution, and vehicle arrivals for both surface road and underground rail corridors.

---

## Generated Fixture Layout

Running the script populates `tests/fixtures/` with the following structure:

```
tests/fixtures/
├── README.md                                  # This guide
├── tfl_arrivals.json                          # Root backwards-compatibility snapshot
└── commute_nelson_to_brick_lane/
    ├── set1_poc_bus_discrete/                 # Legacy PoC multi-request stop arrivals
    │   ├── 01_terminus_victoria.json
    │   ├── 02_intermediate_st_james_park.json
    │   ├── 03_intermediate_westminster.json
    │   ├── 04_intermediate_horse_guards.json
    │   ├── 05_target_trafalgar_square.json
    │   ├── 06_destination_shoreditch_high_st.json
    │   └── 07_line_status.json
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
    │   ├── 01_intermediate_victoria.json
    │   ├── 02_intermediate_st_james_park.json
    │   ├── 03_intermediate_westminster.json
    │   ├── 04_target_embankment.json
    │   ├── 05_destination_aldgate_east.json
    │   ├── 06_line_status.json
    │   └── 07_journey_results.json
    ├── set6_consolidated_tube/                # Consolidated tube line arrivals & journey
    │   ├── line_arrivals.json
    │   ├── journey_results.json
    │   └── line_status.json
    └── time_series/                           # 15-minute multi-modal corridor progression
        ├── snapshot_001.json                  # Combined bus + tube corridor snapshot
        ├── ...
        ├── snapshot_030.json
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
