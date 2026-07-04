# Data Coverage Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top-of-report data coverage diagnostics section that explains missing or insufficient data.

**Architecture:** Introduce a small data coverage model and analyzer that consumes existing watchlist groups, price history, and stored news count. Render the model immediately after Section 0 and pass it from the daily report job.

**Tech Stack:** Python dataclasses, pytest, existing report generation pipeline.

---

### Task 1: Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/data_coverage_analyzer.py`
- Test: `tests/test_data_coverage_analyzer.py`

- [ ] **Step 1: Write failing analyzer tests**

Add tests for available/missing/insufficient price coverage, macro proxy requirements, news coverage, and impact notes.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_data_coverage_analyzer.py -v`

Expected: fail because `app.analyzers.data_coverage_analyzer` does not exist.

- [ ] **Step 3: Implement model and analyzer**

Add `DataCoverageRow` and `DataCoverage` dataclasses. Implement `analyze_data_coverage(...)`.

- [ ] **Step 4: Verify analyzer tests pass**

Run: `python -m pytest tests/test_data_coverage_analyzer.py -v`

Expected: pass.

### Task 2: Rendering And Job Wiring

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `app/jobs/daily_market_job.py`
- Test: `tests/test_markdown_writer.py`

- [ ] **Step 1: Write failing rendering test**

Add a test that passes `DataCoverage` into `render_daily_report(...)` and asserts the section renders between Section 0 and Section 1.

- [ ] **Step 2: Verify rendering test fails**

Run: `python -m pytest tests/test_markdown_writer.py -v`

Expected: fail because rendering does not accept `data_coverage`.

- [ ] **Step 3: Implement rendering and job wiring**

Render `## Data Coverage` after Section 0 and call `analyze_data_coverage(...)` from the daily report job.

- [ ] **Step 4: Run full verification**

Run: `git diff --check` and `python -m pytest -v`

Expected: no whitespace errors and all tests pass.
