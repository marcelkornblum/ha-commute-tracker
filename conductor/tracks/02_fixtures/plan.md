# Implementation Plan: Phase 2 — Spec Extraction & Data Fixtures

- [x] Implement modular `scripts/capture_tfl.py` supporting PoC discrete, consolidated, and time-series capture
- [x] Capture Set 1: PoC Bus Discrete stop arrivals and status for Daytime Bus 26 (`tests/fixtures/commute_nelson_to_brick_lane/set1_poc_bus_discrete/`)
- [x] Capture Set 2: PoC Train Discrete journey results and status for Southeastern (`tests/fixtures/commute_nelson_to_brick_lane/set2_poc_train_discrete/`)
- [x] Capture Set 3: Consolidated Bus line arrivals and status (`tests/fixtures/commute_nelson_to_brick_lane/set3_consolidated_bus/`)
- [x] Capture Set 4: Consolidated Train journey results and status (`tests/fixtures/commute_nelson_to_brick_lane/set4_consolidated_train/`)
- [x] Capture Set 5: PoC Tube Discrete stop arrivals and status for Central Line non-terminus corridor (`tests/fixtures/commute_nelson_to_brick_lane/set5_poc_tube_discrete/`)
- [x] Capture Set 6: Consolidated Tube line arrivals and status (`tests/fixtures/commute_nelson_to_brick_lane/set6_consolidated_tube/`)
- [x] Capture 45-minute multi-route corridor time-series snapshots (90 iterations @ 30s) and manifest across all 3 routes and both API paradigms (`tests/fixtures/commute_nelson_to_brick_lane/time_series/`)
- [x] Draft and finalise `specs/commute_contract.md` documenting Nelson's Column to Brick Lane exemplar, walking offsets, and sensor attributes
- [x] Detailed Multi-Route Telemetry Analysis: Perform rigorous inspection of captured time-series snapshots across all 3 routes and both paradigms; document tracked vehicle IDs, appearance timestamps, intermediate corridor traversal progressions, and doorstep reachability transitions (`relaxed` -> `prepare` -> `leave_now` -> rollover); formulate runtime expected behaviour specs for each route
- [x] Sequential 30-Second Replay Test Suite: Construct an integration test suite that feeds the 90 consecutive snapshots one by one into the tracking logic, asserting the precise sequence of vehicle tracking metrics, urgency stage changes, and rollover events against the analytical expectation
- [x] Maintain unit test suite in `tests/test_capture_tfl.py` (100% passing)