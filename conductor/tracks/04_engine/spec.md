# Specification

**Goal**: Construct the backend math logic for calculating slack and urgency state transitions.

## Requirements
- Pure Python `engine.py` and `timeliness.py`.
- Implement a Cascading Resolution Engine for time thresholds: overrides cascade from (1) HA Input Helpers -> (2) YAML Config -> (3) Global Defaults.