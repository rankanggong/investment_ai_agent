# Plan Impact Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Section 7's placeholder with a deterministic, position-agnostic plan impact review.

**Architecture:** Add plan impact dataclasses and a focused analyzer that scores watchlist symbols from existing report inputs. Wire the analyzer into the daily job and render the result in Section 7 without buy/sell instruction wording.

**Tech Stack:** Python dataclasses, pytest, existing analyzer and markdown report pipeline.

---

### Task 1: Plan Impact Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/plan_impact_analyzer.py`
- Test: `tests/test_plan_impact_analyzer.py`

- [ ] **Step 1: Write failing tests**

Create analyzer tests for accumulation review, de-risk review, and no clear impact.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_plan_impact_analyzer.py -v`

Expected: fail because `app.analyzers.plan_impact_analyzer` does not exist.

- [ ] **Step 3: Implement model and analyzer**

Add `PlanImpactItem` and `PlanImpact` dataclasses. Implement `analyze_plan_impact(...)` with deterministic scoring and evidence strings.

- [ ] **Step 4: Verify analyzer tests pass**

Run: `python -m pytest tests/test_plan_impact_analyzer.py -v`

Expected: all analyzer tests pass.

### Task 2: Section 7 Rendering And Daily Job Wiring

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `app/jobs/daily_market_job.py`
- Test: `tests/test_markdown_writer.py`

- [ ] **Step 1: Write failing rendering test**

Add a test that passes a `PlanImpact` value into `render_daily_report(...)` and asserts Section 7 renders review buckets instead of `Deferred to Phase 5.`

- [ ] **Step 2: Verify rendering test fails**

Run: `python -m pytest tests/test_markdown_writer.py -v`

Expected: fail because `render_daily_report(...)` does not accept or render `plan_impact`.

- [ ] **Step 3: Implement rendering and job wiring**

Import `PlanImpact`, render the Section 7 tables, and call `analyze_plan_impact(...)` in the daily report job.

- [ ] **Step 4: Run full verification**

Run: `python -m pytest -v`

Expected: all tests pass.
