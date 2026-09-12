# Specification

**Goal**: Implement Home Assistant Config Flow to provide a fully UI-driven setup wizard.

## Requirements
- Users must be able to configure commute routes, API credentials, and target arrival times via the HA Integrations UI.
- Must implement `options_flow` to allow users to tweak walk times or thresholds after initial setup without deleting the commute.
- **Corridor Configuration Helper**: The wizard must include an automated corridor discovery helper. Once the user selects a route/line and boarding target stop, the wizard queries the provider's route sequence API (e.g. `/Line/{id}/Route/Sequence`) to automatically discover, order, and populate the complete upstream corridor stops and NaPTAN IDs, eliminating the manual overhead of looking up dozens of intermediate station IDs.
- UI strings and descriptions must be localised in `translations/en.json`.
