# Specification

**Goal**: Expose the condensed data model to the HA State Machine.

## Requirements
- Strict Entity Minimalism: Only expose the Master Rollup and Child Route sensors. Embed timeliness as attributes.
- `unique_id` generation defaults to a slugified version of the YAML name, with an optional explicit YAML override.