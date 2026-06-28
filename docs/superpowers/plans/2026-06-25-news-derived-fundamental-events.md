# News-Derived Fundamental Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate section 6 with deterministic fundamental events derived from stored news headlines and polish section 5 cluster output.

**Architecture:** Add a `FundamentalEvent` model and analyzer that consumes `NewsItem` values. The daily report job will fetch recent news once, derive both clusters and events, and pass both to the Markdown writer.

**Tech Stack:** Python 3.11+, dataclasses, pytest

---

### Task 1: Fundamental Event Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/fundamental_event_analyzer.py`
- Create: `tests/test_fundamental_event_analyzer.py`

- [ ] Write failing tests for event keyword detection and ignoring non-event headlines.
- [ ] Run `python -m pytest tests/test_fundamental_event_analyzer.py -v` and confirm missing analyzer failure.
- [ ] Implement `FundamentalEvent` and `analyze_fundamental_events(items, max_events=10)`.
- [ ] Run `python -m pytest tests/test_fundamental_event_analyzer.py -v`.

### Task 2: Report Rendering

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `tests/test_markdown_writer.py`

- [ ] Write failing tests for section 6 rendering and section 5 item count rendering.
- [ ] Run `python -m pytest tests/test_markdown_writer.py -v`.
- [ ] Add optional `fundamental_events` rendering and cluster item count output.
- [ ] Run `python -m pytest tests/test_markdown_writer.py -v`.

### Task 3: Daily Job Integration And Verification

**Files:**
- Modify: `app/jobs/daily_market_job.py`

- [ ] Fetch recent news once in `generate_daily_report`.
- [ ] Pass recent news into both news cluster and fundamental event analyzers.
- [ ] Pass events into `render_daily_report`.
- [ ] Run `python -m pytest -v`.
- [ ] Run `git diff --check` and review `git diff --stat`.

