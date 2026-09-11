# Workflow

## 1. Red/Green TDD
All core domain logic (`engine.py`, `timeliness.py`, `providers/`) must be developed in pure Python FIRST. Unit tests against static JSON fixtures must be written and observed to fail (Red), and then the logic must be implemented to pass (Green). Only then can Home Assistant integration plumbing commence.

## 2. HACS-First Structuring
Code goes exclusively into `custom_components/commute_tracker/`. 

## 3. Entity Minimalism
Do not register intermediary API state. Stick strictly to Master Rollup and Child Route sensors. Use attributes for metadata like timeliness.

## 4. Git Workflow
- **Starting a Track:** When starting a new track, immediately create and checkout a new git branch off `main` before making any code changes.
- **Finishing a Track:** When a track is complete, push the branch to `origin` and open a Pull Request back onto `main`.
- **Never Modify Staged Status:** Agents must never stage or unstage files (`git add`, `git reset`, `git restore --staged`, etc.). The user uses git staging exclusively to track their code review progress.

## 5. Legacy PoC Reference & UI Parity
- **Proven Reference**: A fully working, highly effective (though unoptimised) YAML proof of concept is dumped in `conductor/legacy_poc/` for direct reference.
- **Python Replication**: The Python integration is designed to largely replicate that working structure in clean, type-annotated Python, replacing ad-hoc API queries with decoupled `TransitProvider` plugins and optimising intermediate calculations.
- **Strict UI Parity**: The original frontend UI was proven and must not look different. The custom Lovelace card must achieve complete visual and behavioural parity with the original PoC.

