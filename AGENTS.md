# Repository Guidelines

## Project Structure & Module Organization

Application code lives in `app/`. The CLI entry point is `app/main.py`; collectors
fetch market inputs, analyzers derive signals, storage repositories persist data,
and outputs render reports. Portfolio-specific importing, reconciliation, and
reporting are isolated under `app/steward/`. Runtime settings belong in `config/`,
SQL definitions in `app/storage/schema.sql`, and design notes in `docs/`. Tests
mirror application behavior in `tests/test_*.py`. Treat files under
`data/steward/reports/` as generated output; use
`data/steward/templates/steward_state_template.csv` as the import example.

## Build, Test, and Development Commands

Create an isolated Python 3.11+ environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Use `pytest` for the full suite or `pytest tests/test_cli.py -q` for a focused
run. Exercise the CLI with `python -m app.main --help`. Common workflows include:

```bash
python -m app.main init-db
python -m app.main collect prices --yfinance
python -m app.main report daily
python -m app.main steward init-db
python -m app.main steward import --csv path/to/state.csv
```

Live collection requires network access. Bedrock features additionally require
AWS credentials, `AWS_REGION`, and optionally
`FINANCE_AGENT_BEDROCK_MODEL_ID`.

## Coding Style & Naming Conventions

Follow standard Python conventions: four-space indentation, `snake_case` for
modules/functions/variables, and `PascalCase` for classes. Add type hints to
public interfaces and use dataclasses for structured domain values where
appropriate. Keep collectors, analysis, persistence, and rendering concerns in
their existing layers. No formatter or linter is configured, so match nearby
code and keep imports organized.

Use the terminology defined in `CONTEXT.md`, especially “cash position,”
“holding snapshot,” and “FX conversion.” Do not imply transaction history,
market value, or trading advice when the supplied data supports only state or
cost.

## Testing Guidelines

Tests use pytest and should be deterministic, offline by default, and named
`test_<behavior>.py` with functions named `test_<expected_result>`. Add or update
tests with every behavior change, including failure and data-quality paths.
Mock external services such as Yahoo Finance and Bedrock. There is no enforced
coverage percentage; protect the changed behavior with focused assertions.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Fix usd/cny ticker` and
`Integrate yfinance`. Keep each commit scoped to one coherent change. Pull
requests should explain the motivation, summarize behavioral and schema/config
changes, list verification commands, and link relevant issues or design notes.
Include a sample report excerpt when output formatting changes; never include
credentials or private portfolio data.
