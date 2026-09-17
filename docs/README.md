# Architecture & Developer Documentation

## Documentation Index

1. **[System Architecture & Component Boundaries](./system-architecture.md)**
   - Explains the architectural split between Python domain logic and Home Assistant.
   - Details the "Internal Python State vs Strict Public Entity Minimalism" design principle.
   - Outlines the external sensor-driven Sleep/Wake polling lifecycle and custom Lovelace card integration.

2. **[Control Flow & Decision Engine](./control-flow.md)**
   - Traces the end-to-end execution path from raw API ingestion to entity state emission.
   - Explains specific algorithmic responsibilities: direction filtering, doorstep reachability, corridor interpolation, urgency state transitions, destination margin maths, and master option arbitration.

3. **[Transit Provider Architecture & Guide](./transit-providers.md)**
   - Explains the mode-agnostic `TransitProvider` plugin architecture.
   - Describes normalised domain models (`RouteTelemetry`, `DeparturePrediction`, `LineStatus`).
   - Details the `TransitProviderRegistry`, contract validation (`validate_provider`), and dynamic auto-discovery.
   - Provides a comprehensive, step-by-step walkthrough for building and registering a new transit provider.

4. **[Configuration Reference & Schema Guide](./configuration.md)**
   - Comprehensive guide to all configuration options across Root, Commute, and Route scopes.
   - Details option purposes, types, defaults, units, cascading inheritance rules, and mutual exclusivity.
   - Provides fully annotated YAML configuration examples for single-route and multiple single-leg route options.

5. **[Lovelace Custom Card Guide](./lovelace-card.md)**
   - Instructions for installing, configuring, and styling the companion `<commute-tracker-card>`.
   - Explains the corridor schematic rendering, real-time vehicle positioning, and in-card details overlay.
   - Includes standalone preview harness instructions and Vitest automated testing guides.

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
├── specs/                              # Formal behavioural specifications
└── tests/                              # Pytest test suite, time-series replay, & static fixtures
```

---

## Architectural Principles

1. **Strict Entity Minimalism**: Intermediary raw API polling sensors are kept strictly within internal Python memory, preventing Home Assistant entity clutter. Only the Master Rollup and Child Route sensors are registered with Home Assistant.
2. **Universal Transit Provider Architecture**: Decoupled, mode-agnostic provider interfaces supporting buses, trains, trams, tube, and ferries with uniform telemetry models.
3. **External Polling Triggers (Sleep/Wake)**: Polling intervals are strictly driven by observing the state of a user-configured binary sensor (e.g. presence, schedule, or calendar). The integration avoids internal cron loops or polling while idle.
4. **Red/Green Test-Driven Development**: Domain logic is authored in pure Python first, verified against frozen API response fixtures before Home Assistant plumbing is introduced.
5. **Integrated Frontend**: Comes with a dedicated Lovelace custom card (`commute-tracker-card`) built with Lit and TypeScript, auto-registered into Lovelace resources.

---

## Development & Testing

This project uses [`uv`](https://docs.astral.sh/uv/) for Python dependency management and Node.js for frontend card builds.

### Python Environment

```bash
# Sync dependencies
uv sync

# Run pytest suite
uv run pytest

# Run linting and formatting checks
uv run ruff check .
uv run ruff format --check .

# Run static type checking
uv run mypy
```

### Frontend Card Environment

```bash
cd frontend

# Install dependencies
npm install

# Run component and snapshot tests
npm test

# Build production card bundle
npm run build

# Launch standalone visual verification preview harness
npm run dev
```
