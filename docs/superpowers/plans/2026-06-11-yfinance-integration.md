# yfinance Price Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add live six-month daily-price collection from yfinance for the configured watchlist or explicit symbols.

**Architecture:** A dedicated collector isolates yfinance-specific conversion and per-symbol failure handling. The existing CLI selects CSV or yfinance input and persists normalized `PriceBar` values through the existing repository.

**Tech Stack:** Python 3.11+, yfinance, argparse, pytest

---

### Task 1: yfinance Collector

**Files:**
- Create: `tests/test_yfinance_price_collector.py`
- Create: `app/collectors/yfinance_price_collector.py`

- [ ] Write failing tests for normalization and partial failures using an injected history loader.
- [ ] Run `python -m pytest tests/test_yfinance_price_collector.py -v` and confirm missing collector failure.
- [ ] Implement `collect_yfinance_prices(symbols, period="6mo", history_loader=None)`.
- [ ] Run `python -m pytest tests/test_yfinance_price_collector.py -v` and confirm passing tests.

### Task 2: CLI Integration

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `app/main.py`

- [ ] Write failing parser and dispatch tests for `--yfinance`, default watchlist symbols, explicit symbols, and failure reporting.
- [ ] Run `python -m pytest tests/test_cli.py -v` and confirm expected failures.
- [ ] Add mutually exclusive `--csv` and `--yfinance` modes, `--symbols`, `--watchlist`, and live collection dispatch.
- [ ] Run `python -m pytest tests/test_cli.py -v` and confirm passing tests.

### Task 3: Dependency, Documentation, And Verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] Add the yfinance runtime dependency and document live collection commands.
- [ ] Run `python -m pytest -v`.
- [ ] Run `python -m app.main collect prices --help`.
- [ ] Review the final diff for scope and correctness.

