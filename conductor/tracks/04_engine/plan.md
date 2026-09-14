# Implementation Plan

- [ ] Build Cascading Resolution logic
- [ ] Implement `engine.py` (corridor interpolation, slack math)
  - [ ] Refactor location ownership: centralise synthesis of natural language `corridor_location` (e.g. "Between X and Y") in `engine.py` and eliminate redundancy between `DeparturePrediction.location` and `RouteTelemetry.current_stop_location`
  - [ ] Implement fractional stop index interpolation for Lovelace SVG track animation (`corridor_progress`: float, e.g. 3.5)
  - [ ] Implement reachability rollover selection: decouple `active_vehicle_id` from naive lead departure (`departures[0]`), advancing to subsequent departures when `leave_in_seconds < -grace_seconds`
- [ ] Implement urgency state machine transitions
- [ ] Write unit tests for state shift boundary conditions
- [ ] Remove `xfail` from `tests/test_commute_engine_e2e.py` and verify all 7 E2E acceptance tests pass