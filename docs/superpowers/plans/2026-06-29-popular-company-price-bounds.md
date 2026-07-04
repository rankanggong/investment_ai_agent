# Popular Company Price Bounds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Section 9 with price-derived review bands for popular company symbols.

**Architecture:** Add a small analyzer that consumes existing price history, extend analysis models, render Section 9 in the markdown report, and pass configured `popular_companies` symbols from the daily job.

**Tech Stack:** Python dataclasses, pytest, existing SQLite price history and markdown report pipeline.

---

### Task 1: Price Bounds Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/company_price_bounds_analyzer.py`
- Test: `tests/test_company_price_bounds_analyzer.py`

- [ ] **Step 1: Write failing analyzer tests**

Add tests for bound calculation and insufficient-history notes.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_company_price_bounds_analyzer.py -v`

Expected: fail because `app.analyzers.company_price_bounds_analyzer` does not exist.

- [ ] **Step 3: Implement models and analyzer**

Add `CompanyPriceBound` and `CompanyPriceBounds` dataclasses. Implement deterministic price-derived review bands.

- [ ] **Step 4: Verify analyzer tests pass**

Run: `python -m pytest tests/test_company_price_bounds_analyzer.py -v`

Expected: pass.

### Task 2: Report Rendering And Wiring

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `app/jobs/daily_market_job.py`
- Modify: `config/watchlist.yaml`
- Test: `tests/test_markdown_writer.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing rendering/config tests**

Add tests for Section 9 rendering and `popular_companies` watchlist group.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_markdown_writer.py tests/test_config.py -v`

Expected: fail because Section 9 and the watchlist group are missing.

- [ ] **Step 3: Implement rendering, job wiring, and config group**

Render `CompanyPriceBounds`, compute it from daily job price history, and add popular company symbols to the watchlist.

- [ ] **Step 4: Run full verification**

Run: `git diff --check` and `python -m pytest -v`

Expected: no whitespace errors and all tests pass.
