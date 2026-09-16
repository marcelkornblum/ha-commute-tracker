# Commute Tracker (`ha-commute-tracker`)

[![CI](https://github.com/marcelkornblum/ha-commute-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/marcelkornblum/ha-commute-tracker/actions/workflows/ci.yml)
[![HACS Default](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration and companion dashboard card that removes the stress of timing your daily journeys. It monitors multiple transit options simultaneously, compares route options in real time, and provides clear, glanceable urgency stages so you always leave at the right moment.

Whether your commute involves choosing between buses or trains, Commute Tracker tracks live departures, computes your arrival time, and distils complex transit feeds into simple, actionable guidance: *Standby*, *Get Ready*, or *Leave Now*.

---

## Key Features

- **Compare your options**: See buses, trains, and trams side by side to take the quickest way.
- **Live journey view**: See where your train is right now and how close it is to your stop.
- **Know when to walk out**: Set your arrival time; it factors in walking time and live progress so you never need to rush.
- **Simple countdown stages**: Clear states that can trigger smart lights, wall displays, or voice alerts.
- **Quiet when not needed**: Automatically sleeps outside commute times or once you arrive, saving system resources and API calls.
- **Glanceable card**: A purpose-built dashboard card designed for wall displays, tablets, and phones.

---

## Architectural Principles

1. **Entity Minimalism**: Intermediary raw API polling sensors are kept within internal Python state, eliminating entity clutter. Only the Master Rollup and Child Route sensors are registered with Home Assistant.
2. **Universal Transit Provider Architecture**: Decoupled, mode-agnostic provider interfaces supporting buses, trains, trams, tube, and ferries.
3. **External Polling Triggers (Sleep/Wake)**: Polling intervals are strictly driven by observing the state of a user-configured binary sensor. No internal cron loops or polling while idle.
4. **Red/Green Test-Driven Development**: Domain logic is written in pure Python first, verified against frozen API response fixtures before Home Assistant plumbing is introduced.
5. **Integrated Frontend**: Comes with a dedicated Lovelace custom card (`commute-tracker-card`) built with Lit and TypeScript.

---

## Installation

### Via HACS (Custom Repository)

1. Ensure [HACS](https://hacs.xyz) is installed and configured in Home Assistant.
2. Navigate to **HACS** -> **Integrations** -> **Custom repositories** (three dots top right).
3. Add repository URL: `https://github.com/marcelkornblum/ha-commute-tracker` with category `Integration`.
4. Click **Download**, then restart Home Assistant.

### Manual Installation

Copy the `custom_components/commute_tracker` directory into your Home Assistant `<config_dir>/custom_components/` directory and restart Home Assistant.

The companion custom card (`commute-tracker-card`) is bundled with the integration and registered automatically with Home Assistant's frontend at `/commute_tracker/commute-tracker-card.js`.

---

## Configuration & Documentation

Configure your commutes directly in `configuration.yaml`. For complete option specifications, units, cascading hierarchy, and annotated YAML examples, see:

- **[Lovelace Custom Card Guide](docs/lovelace-card.md)**: Installation, card YAML options, corridor schematics, and in-card details overlay.
- **[Configuration Reference & Schema Guide](docs/configuration.md)**: Exhaustive reference of all Root, Commute, and Route options.
- **[System Architecture & Component Boundaries](docs/system-architecture.md)**: Entity model and platform split.
- **[Control Flow & Decision Engine](docs/control-flow.md)**: Reachability math, arbitration, and timeliness stages.
- **[Transit Provider Architecture & Plugin Guide](docs/transit-providers.md)**: Universal provider plugin framework.
- **[Public Entity & Sensor Contract](specs/commute_contract.md)**: Sensor states and attributes specification.

---

## Development & Testing

This project uses [`uv`](https://docs.astral.sh/uv/) for Python dependency management and Node.js for frontend card builds.

### Python Environment

```bash
# Sync dependencies
uv sync

# Run test suite
uv run pytest

# Run linting and formatting checks
uv run ruff check .
uv run ruff format --check .

# Run static type checking
uv run mypy
```

### Frontend Card

```bash
cd frontend
npm install
npm run build
```

---

## Licence

Distributed under the [MIT Licence](LICENSE).
