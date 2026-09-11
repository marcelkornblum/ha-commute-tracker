# Specification: Phase 2 — Spec Extraction & Data Fixtures

**Goal**: Secure real-world transit data payloads to drive Red/Green TDD without relying on live endpoints during testing, using an anonymous public London commute exemplar.

## Exemplar Commute
- **Origin**: Nelson's Column, Trafalgar Square
- **Destination**: Brick Lane, London E1
- **Bus Option**: Daytime Bus 26 (Victoria to Shoreditch)
- **Train Option (Terminus)**: Southeastern Rail (Charing Cross to London Bridge)
- **Train Option (Non-Terminus Corridor)**: District Line Tube (Embankment to Aldgate East)

## Requirements
1. **Six Fixture Sets**:
   - `set1_poc_bus_discrete`: StopPoint arrivals for each stop on approach corridor + destination + line status (replicates PoC `commute_package.yaml`).
   - `set2_poc_train_discrete`: Point-to-point journey results + line status (replicates PoC train setup).
   - `set3_consolidated_bus`: Unified line arrivals (`/Line/{line}/Arrivals`) + line status in minimal requests.
   - `set4_consolidated_train`: Point-to-point journey results + line status.
   - `set5_poc_tube_discrete`: Discrete tube station arrivals across approach corridor + destination + line status + journey results.
   - `set6_consolidated_tube`: Unified tube arrivals (`/Line/district/Arrivals`) + journey results + line status.
2. **Time-Series Corridor Snapshots**:
   - Reusable script capable of capturing consecutive snapshots over time showing vehicle progression across both surface bus and underground rail corridors.
3. **Sensor Contract & Walking Offsets**:
   - Full documentation of walking offsets, prep buffers, corridor stops geometry, and entity attributes in `specs/commute_contract.md`.