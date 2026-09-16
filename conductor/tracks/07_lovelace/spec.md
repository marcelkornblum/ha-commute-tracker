# Phase 7 Specification: Lovelace Custom Card

**Goal**: Build the frontend Web Component (`commute-tracker-card`) to render the commute dashboard with exact visual parity to the proven prototype, accompanied by a standalone development preview harness and automated component test suite.

## 1. Core Card Requirements
- **Technology**: LitElement + TypeScript built with Vite.
- **Visual Parity**: Strict 1:1 visual design and styling port from the running prototype (`conductor/legacy_poc/commute_card.json`). The card aesthetics, spacing, typography, colours, and layout are proven and must achieve exact visual parity.
- **Entity Binding**: Card configuration binds strictly to the Master Rollup entity (`sensor.commute_<commute_id>`). Child route entities are resolved dynamically via the `child_entities` attribute; raw transit API sensors are never directly queried.
- **Card Lifecycle**: Standard Home Assistant custom card contract (`setConfig(config)`, `set hass(hass)`).

## 2. Standalone Visual Verification Harness (No HA Dependency)
- **Local Dev Server**: Standalone Vite preview harness (`frontend/index.html`) executed via `npm run dev` to inspect and interact with the card in real-time in any standard browser without requiring a running Home Assistant instance.
- **Mock State Fixtures**: Standardised Home Assistant state store providing realistic fixtures derived directly from `specs/commute_contract.md`.
- **Interactive Scenarios**: The harness must provide an interactive scenario selector allowing immediate switching between canonical lifecycle states:
  1. *Standby / Inactive*: Commute outside operating window (`urgency_stage: standby`, `is_relevant: false`).
  2. *Relaxed (Multiple Options)*: Comfortable departure window with multiple options (Bus 26 recommended on top, Southeastern rail alternative underneath, Good Service).
  3. *Prepare Window*: Countdown within preparation threshold ($\le 8\text{m}$ to leave, amber badge).
  4. *Leave Now*: Doorstep departure deadline reached ($\le 0\text{m}$ to leave, urgent red pulsing badge).
  5. *Line Disruption*: Live delays or cancellations reported by transit provider (warning indicators and colours).
  6. *Late Arrival*: Destination arrival after target deadline (negative margin, red warning highlight on destination pill).
- **Dynamic Parameter Controls**: Interactive controls (e.g. corridor progress slider, seconds to leave) to observe vehicle animation along the schematic track and badge state transitions.

## 3. Automated Testing & Verification Suite
- **Component Test Framework**: Vitest with `happy-dom` configured in `frontend/` to run headless component tests via `npm test`.
- **Shadow DOM Testing**: Instantiation of `<commute-tracker-card>` verifying:
  - Configuration parsing and error handling for missing/invalid entities.
  - Correct rendering of header (avatar, title, urgency status pill colours and text).
  - Proper route module hierarchy (recommended `active_option` ordered first).
  - SVG corridor schematic geometry (stop circle distribution, target stop emphasis, dynamic vehicle marker translation).
  - Live timing footers (doorstep leave pill, transit departure/arrival, destination pill styling).
  - Navigation event dispatching (`location-changed` event and history push).
- **Snapshot Regression Testing**: DOM snapshot tests capturing the rendered shadow root across all canonical scenarios to catch unintended layout or CSS regressions.