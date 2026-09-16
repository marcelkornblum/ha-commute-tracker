# Future Backlog & Enhancements

This document tracks features and enhancements that are deliberately out of scope for the initial implementation but are planned for future phases.

- [ ] **Additional Transit Providers:** Build provider plugins for BODS, National Rail / Darwin (covering Southern & Thameslink), and GTFS-RT.
- [ ] **Live Activities / Mobile Widgets:** Integrate with Home Assistant Companion App's Live Activities feature to surface live commute urgency and ETAs directly on iOS/Android lock screens.
- [ ] **Dynamic Arrival Times for Single-Leg Route Options:** Support dynamic `expected_arrival_time` calculations for single-leg transit options instead of static transit durations:
  - **Dynamic Vehicle Arrival Tracking:** Where vehicles are tracked in real time (e.g., via TfL vehicle IDs or stop arrival feeds), derive downstream arrival times dynamically from the vehicle's live progress at the alighting stop.
  - **Journey Planner API Integration:** Support querying provider journey planners (e.g., TfL Journey Results API, National Rail, OpenTripPlanner) for live travel durations reflecting real-time traffic and service disruptions across single-leg route options.


