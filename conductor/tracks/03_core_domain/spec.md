# Specification

**Goal**: Build the mode-agnostic domain models and the dynamic provider registry in pure Python.

## Requirements
- `TransitProviderRegistry` must use Dynamic Discovery (auto-loading subclasses from the `providers/` directory).
- **API Caching Layer**: The registry must implement a debounced caching layer to prevent duplicate API calls for the same transit line across multiple concurrent commutes.
- Implement `TfLTransitProvider`.
- Include a `template_provider.py` boilerplate to make adding future APIs easy for the open-source community.