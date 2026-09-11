# Specification

**Goal**: Mount the Python logic into Home Assistant's DataUpdateCoordinator.

## Requirements
- Hybrid Configuration approach: Voluptuous YAML schemas parsing `configuration.yaml` (supporting `!include`), architected for future Config Flow integration.
- **API Credentials**: Configuration schemas must include a `providers:` block to securely handle future API keys (e.g. for Darwin/BODS).
- **Translations (i18n)**: Must implement standard HA `strings.json` / `en.json` translation dictionaries for entity states and errors to comply with HA standards.
- **Frontend Auto-Registration**: Setup must use native HA methods (e.g., `add_extra_html_url`) to automatically serve the frontend Lovelace card bundle, ensuring HACS compliance without requiring users to manually add UI resources.
- Sleep/Wake logic driven exclusively by tracking an external `active_sensor` state.