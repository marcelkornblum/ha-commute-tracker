# Product Guidelines

## Core Principles

1. **Working PoC as Ground Truth**:
   - A fully functional, proven proof of concept exists in `conductor/legacy_poc/` for review and architectural reference.
   - The specifications and Python custom integration are designed to largely replicate that working data structure, timeliness logic, and urgency states.
   - The architectural modernisation replaces ad-hoc polling with the decoupled `TransitProvider` plugin architecture (supporting bus, train, tram, ferry) and keeps all raw intermediate stop arrivals inside internal Python memory (`DataUpdateCoordinator`).

2. **Strict UI Parity Mandate**:
   - The original Lovelace dashboard UI was effective, well-designed, and loved. It **must not look different**.
   - The companion custom Lovelace card (`commute-tracker-card`) must match the original card layout, corridor schematics, progress markers, countdown states, and urgency colourations precisely.
   - Do not re-invent or alter the visual design language of the commute card.

3. **Glanceable & Actionable Urgency**:
   - Transit data must always be distilled into intuitive, glanceable urgency states: *Standby*, *Get Ready* / *Prepare*, and *Leave Now*.
   - Countdown timers and corridor progress must be immediately readable at a distance on wall-mounted displays and tablets.

4. **Resource Minimalism & Sleep/Wake**:
   - No wasteful background polling when commutes are inactive. The integration's lifecycle is strictly governed by external binary sensors (e.g. `binary_sensor.commute_relevant`).
