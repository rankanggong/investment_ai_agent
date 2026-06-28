# Daily Signal Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic Section 0 daily triage summary to the generated market brief.

**Architecture:** Introduce a `DailySignalSummary` model and analyzer that consumes existing report inputs. Render it before Section 1 and wire the daily job to compute it after all underlying analyzers complete.

**Tech Stack:** Python dataclasses, pytest, existing markdown report pipeline.

---

### Task 1: Summary Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/daily_signal_summary_analyzer.py`
- Test: `tests/test_daily_signal_summary_analyzer.py`

- [ ] **Step 1: Write failing analyzer tests**

```python
from app.analyzers.daily_signal_summary_analyzer import analyze_daily_signal_summary
from app.models.analysis import FundamentalEvent, MacroContext, PriceSignal, SectorRotation


def signal(symbol, unusual=False):
    return PriceSignal(symbol, 0.0, 0.0, 0.0, None, None, unusual, "large move" if unusual else "")


def rotation(score=0.0):
    return SectorRotation([], [], score, "mixed", "mixed", [])


def test_summary_reports_no_material_signal_when_inputs_are_quiet():
    result = analyze_daily_signal_summary(
        {"SPY": signal("SPY")},
        rotation(),
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        [],
        [],
    )

    assert result.status == "no_material_signal"
    assert "Price: no unusual moves" in result.drivers
    assert result.reason == "No price, sector, macro, news, or fundamental event crossed review thresholds."


def test_summary_requires_review_for_unusual_price_moves_and_events():
    result = analyze_daily_signal_summary(
        {"AAPL": signal("AAPL", unusual=True)},
        rotation(),
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        [],
        [FundamentalEvent("earnings_release", "AAPL", "Apple reports earnings", "Reuters", "https://example.com", 0.85)],
    )

    assert result.status == "review_required"
    assert "Price: 1 unusual move" in result.drivers
    assert "Fundamental events: 1 detected" in result.drivers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_daily_signal_summary_analyzer.py -v`

Expected: fail because `app.analyzers.daily_signal_summary_analyzer` does not exist.

- [ ] **Step 3: Implement minimal model and analyzer**

Add `DailySignalSummary` to `app/models/analysis.py` and implement `analyze_daily_signal_summary(...)` in `app/analyzers/daily_signal_summary_analyzer.py`.

- [ ] **Step 4: Run analyzer tests**

Run: `python -m pytest tests/test_daily_signal_summary_analyzer.py -v`

Expected: pass.

### Task 2: Markdown Rendering And Job Wiring

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `app/jobs/daily_market_job.py`
- Test: `tests/test_markdown_writer.py`

- [ ] **Step 1: Write failing markdown test**

Add a test asserting `## 0. What Matters Today`, status, drivers, and reason render before `## 1. Market Overview`.

- [ ] **Step 2: Run markdown test to verify it fails**

Run: `python -m pytest tests/test_markdown_writer.py -v`

Expected: fail because the new section is not rendered.

- [ ] **Step 3: Render `DailySignalSummary` and wire daily job**

Import the model in `markdown_writer.py`, add an optional `daily_signal_summary` parameter, render a fallback summary when omitted, and call `analyze_daily_signal_summary(...)` in `daily_market_job.py`.

- [ ] **Step 4: Run full tests**

Run: `python -m pytest -v`

Expected: all tests pass.
