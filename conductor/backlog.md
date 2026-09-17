# Future Backlog & Enhancements

This document tracks features and enhancements that are deliberately out of scope for the initial implementation but are planned for future phases.

- [ ] **Additional Transit Providers:** Build provider plugins for BODS, National Rail / Darwin (covering Southern & Thameslink), and GTFS-RT.
- [ ] **Live Activities / Mobile Widgets:** Integrate with Home Assistant Companion App's Live Activities feature to surface live commute urgency and ETAs directly on iOS/Android lock screens.
- [ ] **Multi-Modal Journeys & Dynamic Arrival Times:** Support multi-leg, multi-modal commutes (e.g., Bus to Tube, Train to Bus) with dynamic `expected_arrival_time` calculations instead of static leg durations:
  - **Dynamic Vehicle Arrival Tracking:** Where vehicles are tracked in real time (e.g., via TfL vehicle IDs or stop arrival feeds), derive downstream arrival times dynamically from the vehicle's live progress at the alighting stop.
  - **Journey Planner API Integration:** Support routing via provider journey planners (e.g., TfL Journey Results API, National Rail, OpenTripPlanner) to fetch live end-to-end itineraries and dynamic arrival times reflecting real-time traffic and service disruptions.
  - **Connection Feasibility & Transfer Slack:** Dynamically propagate delays across legs, recalculating whether subsequent connections will be made and updating destination slack and urgency accordingly.
  - **Minimalist Entity & Lovelace Schema:** Expose multi-leg breakdown within child route sensor attributes to preserve strict entity minimalism while supporting rich visualisations on the custom Lovelace card.
- [ ] **Built-in Schedule & Commute Active Window:** Add an integrated UI schedule or time window selector directly within the integration configuration, removing the mandatory requirement for an external `active_sensor` entity and automatically generating internal sleep/wake triggers based on user-defined morning/evening commute hours.


