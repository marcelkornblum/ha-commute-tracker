# Contributing to Commute Tracker

Thanks for your interest in contributing to Commute Tracker! Whether you are fixing a typo, reporting a bug, improving documentation, or adding support for a new transit provider, I really appreciate your help.

## Ways to Contribute

- **Report a Bug**: If something isn't working as expected, please [open an issue](https://github.com/marcelkornblum/ha-commute-tracker/issues/new?template=bug_report.md) with details on your Home Assistant version and steps to reproduce.
- **Suggest an Idea or Transit Provider**: Have a transit agency you would like supported (trains, ferries, trams, buses)? [Open a feature request](https://github.com/marcelkornblum/ha-commute-tracker/issues/new?template=feature_request.md).
- **Submit Code**: Pick up an open issue or submit a pull request with your improvements.

## Getting Started

I use [`uv`](https://docs.astral.sh/uv/) for Python development and `npm` for the frontend Lovelace card.

### 1. Set up your environment

1. [Fork the repository](https://github.com/marcelkornblum/ha-commute-tracker/fork) to your GitHub account (or run `gh repo fork marcelkornblum/ha-commute-tracker --clone`).
2. Clone your fork locally:

```bash
git clone https://github.com/<your-username>/ha-commute-tracker.git
cd ha-commute-tracker

# Install Python dependencies
uv sync
```

### 2. Run tests and checks

Before opening a pull request, please check that tests and formatting pass:

```bash
# Run tests
uv run pytest

# Run linting and type checks
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

If you are working on the Lovelace custom card in `frontend/`:

```bash
cd frontend
npm install
npm run build
```

## Pull Request Guidelines

1. **Keep it focused**: One bug fix or feature per pull request helps me review and merge quickly.
2. **Include tests**: If you are adding logic or a new transit provider, please include unit tests.
3. **Conventions**: I use British English for documentation and comments (e.g. `behaviour`, `optimise`), and keep all code type-annotated.
4. **Questions welcome**: If you are unsure about the best approach, feel free to open an issue or draft PR first—I'm very happy to collaborate and discuss ideas.
