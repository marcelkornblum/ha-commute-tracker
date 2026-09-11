# Specification

**Goal**: Secure real-world transit data payloads to drive Red/Green TDD without relying on live endpoints during testing.

## Requirements
- Python capture script to pull live API data from TfL consolidated line endpoints.
- Output pure JSON responses into `tests/fixtures/`.
- Design the script to be modular for future APIs (BODS, Darwin).