# Specification

**Goal**: Implement Home Assistant Config Flow to provide a fully UI-driven setup wizard.

## Requirements
- Users must be able to configure commute routes, API credentials, and target arrival times via the HA Integrations UI.
- Must implement `options_flow` to allow users to tweak walk times or thresholds after initial setup without deleting the commute.
- UI strings and descriptions must be localized in `translations/en.json`.
