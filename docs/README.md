# Architecture & Developer Documentation

## Documentation Index

1. **[System Architecture & Component Boundaries](./system-architecture.md)**
   - Explains the architectural split between Python domain logic and Home Assistant.
   - Details the "Internal Python State vs Strict Public Entity Minimalism" design principle.
   - Outlines the external sensor-driven Sleep/Wake polling lifecycle and custom Lovelace card integration.

2. **[Control Flow & Decision Engine](./control-flow.md)**
   - Traces the end-to-end execution path from raw API ingestion to entity state emission.
   - Explains specific algorithmic responsibilities: direction filtering, doorstep reachability, corridor interpolation, urgency state transitions, destination slack maths, and master option arbitration.

3. **[Transit Provider Architecture & Guide](./transit-providers.md)**
   - Explains the mode-agnostic `TransitProvider` plugin architecture.
   - Describes normalised domain models (`RouteTelemetry`, `DeparturePrediction`, `LineStatus`).
   - Details the `TransitProviderRegistry`, contract validation (`validate_provider`), and dynamic auto-discovery.
   - Provides a comprehensive, step-by-step walkthrough for building and registering a new transit provider.

---

## High-Level Repository Layout

```text
ha-commute-tracker/
├── custom_components/commute_tracker/   # The Home Assistant integration package
│   ├── const.py                        # Centralised configuration constants & defaults
│   ├── models.py                       # Normalised domain models (dataclasses & enums)
│   ├── timeliness.py                   # Pure Python doorstep math, slack, & urgency states
│   ├── corridor.py                     # Trajectory filtering, dwell rollover, progression
│   ├── engine.py                       # CommuteEngine & multi-option master rollup arbitration
│   └── providers/                      # Universal transit provider plugin system
│       ├── base.py                     # TransitProvider ABC, DebouncedCache, Registry, Validator
│       ├── tfl.py                      # Transport for London (Bus, Tube, Rail) implementation
│       └── template_provider.py        # Boilerplate reference provider for extension
├── docs/                               # Architectural and developer documentation
├── frontend/                           # Lovelace custom card (visual UI layer)
├── specs/                              # Formal behavioral specifications
└── tests/                              # Pytest test suite, time-series replay, & static fixtures
```
