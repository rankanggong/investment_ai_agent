# Phase 1 Price MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first local financial research loop: watchlist config, SQLite storage, price analysis, sector rotation, and a Markdown daily report.

**Architecture:** A Python CLI coordinates small modules for config loading, database setup, repository access, deterministic price analysis, and report writing. The MVP avoids network-dependent tests by accepting price CSV imports while leaving a yfinance-compatible collector boundary for later live collection.

**Tech Stack:** Python 3.11+, stdlib `argparse`, `csv`, `sqlite3`, `dataclasses`, `unittest`; optional `PyYAML` if installed with a minimal fallback YAML parser for the included config.

---

## File Structure

- Create: `pyproject.toml` for package metadata, pytest configuration, and console script.
- Create: `README.md` with Phase 1 commands and non-advice disclaimer.
- Create: `.env.example` for future data/API settings.
- Create: `config/watchlist.yaml` with core, sector, and macro proxy assets from the design doc.
- Create: `app/main.py` for the `finance-agent` CLI.
- Create: `app/config.py` for watchlist loading and asset normalization.
- Create: `app/models/*.py` for asset, price, analysis, and report dataclasses.
- Create: `app/storage/schema.sql`, `app/storage/db.py`, and repository modules for SQLite persistence.
- Create: `app/collectors/price_collector.py` for CSV price import.
- Create: `app/analyzers/price_move_analyzer.py` and `app/analyzers/sector_rotation_analyzer.py` for deterministic calculations.
- Create: `app/outputs/markdown_writer.py` for report rendering and saving.
- Create: `app/jobs/daily_market_job.py` for daily report orchestration.
- Create: focused tests under `tests/`.

## Tasks

### Task 1: Project Skeleton And Config

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `.env.example`
- Create: `config/watchlist.yaml`
- Create: `app/config.py`
- Create: `app/models/asset.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

```python
from pathlib import Path

from app.config import load_watchlist


def test_load_watchlist_expands_grouped_assets():
    watchlist = load_watchlist(Path("config/watchlist.yaml"))

    symbols = [asset.symbol for asset in watchlist.assets]

    assert "SPY" in symbols
    assert "QQQ" in symbols
    assert "XLK" in symbols
    assert watchlist.asset_by_symbol("SPY").role == "us_equity_core"
    assert watchlist.asset_by_symbol("XLK").role == "sector"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`

Expected: FAIL with missing `app.config` or `load_watchlist`.

- [ ] **Step 3: Implement config loading**

Implement dataclasses and a minimal loader that supports the included watchlist YAML shape.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`

Expected: PASS.

### Task 2: SQLite Schema And Price Repository

**Files:**
- Create: `app/storage/schema.sql`
- Create: `app/storage/db.py`
- Create: `app/storage/repositories/price_repo.py`
- Create: `app/models/price.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing repository tests**

```python
from datetime import date

from app.models.price import PriceBar
from app.storage.db import initialize_database
from app.storage.repositories.price_repo import PriceRepository


def test_price_repository_upserts_and_reads_prices(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = PriceRepository(db_path)

    repo.upsert_many([
        PriceBar(symbol="SPY", date=date(2026, 5, 14), open=100, high=102, low=99, close=101, adjusted_close=101, volume=1000, source="test"),
        PriceBar(symbol="SPY", date=date(2026, 5, 15), open=101, high=104, low=100, close=103, adjusted_close=103, volume=1500, source="test"),
    ])
    repo.upsert_many([
        PriceBar(symbol="SPY", date=date(2026, 5, 15), open=101, high=104, low=100, close=104, adjusted_close=104, volume=1700, source="test"),
    ])

    bars = repo.get_prices("SPY")

    assert len(bars) == 2
    assert bars[-1].close == 104
    assert bars[-1].volume == 1700
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -v`

Expected: FAIL with missing storage implementation.

- [ ] **Step 3: Implement schema and repository**

Create the Phase 1 subset of `assets`, `prices`, and `reports`, plus upsert/read methods.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storage.py -v`

Expected: PASS.

### Task 3: Price Move Analyzer

**Files:**
- Create: `app/analyzers/price_move_analyzer.py`
- Create: `app/models/analysis.py`
- Test: `tests/test_price_move_analyzer.py`

- [ ] **Step 1: Write failing analyzer tests**

```python
from datetime import date, timedelta

from app.analyzers.price_move_analyzer import analyze_price_moves
from app.models.price import PriceBar


def make_bar(day, close, volume=1000):
    return PriceBar(symbol="GLD", date=date(2026, 1, 1) + timedelta(days=day), open=close, high=close, low=close, close=close, adjusted_close=close, volume=volume, source="test")


def test_analyze_price_moves_calculates_returns_and_flags_unusual_move():
    prices = [make_bar(i, 100 + i * 0.1) for i in range(21)]
    prices.append(make_bar(21, 108, volume=3000))

    signals = analyze_price_moves({"GLD": prices})
    signal = signals["GLD"]

    assert round(signal.return_1d, 4) == round((108 / 102 - 1), 4)
    assert signal.return_5d > 0.05
    assert signal.return_20d > 0.07
    assert signal.volume_ratio_20d == 3.0
    assert signal.is_unusual_move is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_price_move_analyzer.py -v`

Expected: FAIL with missing analyzer.

- [ ] **Step 3: Implement deterministic calculations**

Calculate 1D, 5D, 20D returns, 20D volume ratio, simple volatility z-score, and unusual-move reason.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_price_move_analyzer.py -v`

Expected: PASS.

### Task 4: Sector Rotation Analyzer

**Files:**
- Create: `app/analyzers/sector_rotation_analyzer.py`
- Test: `tests/test_sector_rotation_analyzer.py`

- [ ] **Step 1: Write failing sector tests**

```python
from app.analyzers.sector_rotation_analyzer import analyze_sector_rotation
from app.models.analysis import PriceSignal


def signal(symbol, r5, r20):
    return PriceSignal(symbol=symbol, return_1d=0.0, return_5d=r5, return_20d=r20, volume_ratio_20d=None, volatility_zscore=None, is_unusual_move=False, reason="")


def test_sector_rotation_ranks_sectors_against_spy():
    result = analyze_sector_rotation(
        {"SPY": signal("SPY", 0.02, 0.03), "XLK": signal("XLK", 0.08, 0.10), "XLU": signal("XLU", -0.01, -0.02)},
        sector_symbols=["XLK", "XLU"],
        benchmark_symbol="SPY",
    )

    assert result.strong_sectors == ["XLK"]
    assert result.weak_sectors == ["XLU"]
    assert result.risk_on_score > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sector_rotation_analyzer.py -v`

Expected: FAIL with missing analyzer.

- [ ] **Step 3: Implement sector ranking**

Rank sector symbols by 5D relative return versus SPY and derive a small risk-on score.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sector_rotation_analyzer.py -v`

Expected: PASS.

### Task 5: Markdown Daily Report And CLI

**Files:**
- Create: `app/outputs/markdown_writer.py`
- Create: `app/jobs/daily_market_job.py`
- Create: `app/main.py`
- Test: `tests/test_markdown_writer.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing report and CLI tests**

```python
from datetime import date

from app.models.analysis import PriceSignal, SectorRotation
from app.outputs.markdown_writer import render_daily_report


def test_render_daily_report_includes_required_sections():
    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={"SPY": PriceSignal("SPY", 0.01, 0.02, 0.03, 1.2, 0.5, False, "")},
        sector_rotation=SectorRotation(strong_sectors=["XLK"], weak_sectors=["XLU"], risk_on_score=0.5, growth_vs_value="growth_leading", cyclical_vs_defensive="unknown", notes=[]),
    )

    assert "# Daily Market Brief - 2026-05-16" in content
    assert "## 1. Market Overview" in content
    assert "## 3. Sector Rotation" in content
    assert "| SPY | 1.00% | 2.00% | 3.00% |" in content
```

```python
from app.main import build_parser


def test_cli_exposes_phase_1_commands():
    parser = build_parser()

    assert parser.parse_args(["init-db"]).command == "init-db"
    assert parser.parse_args(["collect", "prices", "--csv", "prices.csv"]).collect_command == "prices"
    assert parser.parse_args(["report", "daily"]).report_command == "daily"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_markdown_writer.py tests/test_cli.py -v`

Expected: FAIL with missing modules.

- [ ] **Step 3: Implement report rendering and CLI dispatch**

Add commands for database initialization, CSV price import, and daily report generation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_markdown_writer.py tests/test_cli.py -v`

Expected: PASS.

### Task 6: Full Verification

**Files:**
- Modify only if verification exposes gaps.

- [ ] **Step 1: Run the full suite**

Run: `python -m pytest -v`

Expected: all tests pass.

- [ ] **Step 2: Exercise CLI help**

Run: `python -m app.main --help`

Expected: command help lists `init-db`, `collect`, and `report`.

- [ ] **Step 3: Review diff**

Run: `git diff --stat`

Expected: changes are limited to Phase 1 project files, config, tests, and plan.
