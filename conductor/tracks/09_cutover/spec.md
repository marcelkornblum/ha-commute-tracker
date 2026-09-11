# Specification

**Goal**: Safely deploy the integration to live HA and test against the legacy YAML.

## Requirements
- Add a `staging_mode: true` config flag that artificially appends `_staging` to all generated Entity IDs.
- Deploy via HACS Custom Repository.
- Parallel testing before legacy YAML teardown.