# ha-commute-tracker Agent Rules

To ensure any agent working on this repository adheres to the established architectural decisions, the repository will enforce the following local AI rules:

1. **British English**: All documentation, logs, variable names, and code comments must use British English (e.g., `colour`, `behaviour`, `minimise`).
2. **Red/Green TDD Mandate**: The core logic (`engine.py`, `timeliness.py`, `providers/`) MUST be developed in pure Python first, writing unit tests against static JSON fixtures. Do not introduce Home Assistant dependencies or mocking until the raw data logic is proven to pass (Green).
3. **Strict Entity Minimalism**: The integration is forbidden from registering intermediary API state as Home Assistant entities. Only the Master Rollup and Child Route sensors may be registered. All raw transit arrivals must remain in the `DataUpdateCoordinator`'s internal memory.
4. **External Polling Triggers**: Agents must not implement internal `asyncio.sleep` loops or standalone cron jobs for the polling interval. Sleep/Wake behaviour MUST be entirely driven by observing the state of the user-provided `active_sensor` from Home Assistant.
5. **HACS-First Structure**: All integration code must be placed strictly within the `custom_components/commute_tracker/` directory structure.
6. **No Device IDs**: Any generated Home Assistant automations or entity references must use HA Area names or `entity_id` strings, never hardcoded hardware `device_id`s.
7. **Never Modify Git Staging Status**: Agents must never stage or unstage files (`git add`, `git rm --cached`, `git restore --staged`, `git reset`). The user uses git staging exclusively to track their own code review progress.

