# Macro Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic macro context to the daily market report using existing proxy ETF price signals.

**Architecture:** Introduce a `MacroContext` dataclass and a dedicated analyzer that derives labels from `TLT`, `UUP`, `HYG`, `LQD`, `GLD`, and `SPY` price signals. Thread the analyzer through the daily report job and render the result in the existing Markdown report section.

**Tech Stack:** Python 3.11+, dataclasses, pytest

---

### Task 1: Macro Context Analyzer

**Files:**
- Modify: `app/models/analysis.py`
- Create: `app/analyzers/macro_context_analyzer.py`
- Create: `tests/test_macro_context_analyzer.py`

- [ ] **Step 1: Write failing analyzer tests**

```python
from app.analyzers.macro_context_analyzer import analyze_macro_context
from app.models.analysis import PriceSignal


def signal(symbol, r5, r20):
    return PriceSignal(
        symbol=symbol,
        return_1d=0.0,
        return_5d=r5,
        return_20d=r20,
        volume_ratio_20d=None,
        volatility_zscore=None,
        is_unusual_move=False,
        reason="",
    )


def test_macro_context_identifies_supportive_risk_backdrop():
    result = analyze_macro_context(
        {
            "SPY": signal("SPY", 0.03, 0.05),
            "TLT": signal("TLT", 0.025, 0.04),
            "UUP": signal("UUP", -0.02, -0.03),
            "HYG": signal("HYG", 0.015, 0.02),
            "LQD": signal("LQD", 0.004, 0.01),
            "GLD": signal("GLD", 0.02, 0.03),
        }
    )

    assert result.rates_context == "duration_supported"
    assert result.usd_context == "usd_weakening"
    assert result.credit_context == "risk_appetite_supportive"
    assert result.gold_context == "gold_supported"
    assert result.overall_regime == "risk_on_with_macro_support"
    assert result.notes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_macro_context_analyzer.py -v`

Expected: FAIL with missing `app.analyzers.macro_context_analyzer`.

- [ ] **Step 3: Implement `MacroContext` and analyzer**

Add `MacroContext` to `app/models/analysis.py`, then implement deterministic threshold rules in `app/analyzers/macro_context_analyzer.py`.

- [ ] **Step 4: Run analyzer tests**

Run: `python -m pytest tests/test_macro_context_analyzer.py -v`

Expected: PASS.

### Task 2: Markdown Rendering

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `tests/test_markdown_writer.py`

- [ ] **Step 1: Write failing report rendering test**

Extend `tests/test_markdown_writer.py` so `render_daily_report(..., macro_context=...)` renders `Rates:`, `USD:`, `Credit:`, `Gold:`, `Regime:`, and notes under `## 4. Macro Context`.

- [ ] **Step 2: Run report test to verify it fails**

Run: `python -m pytest tests/test_markdown_writer.py -v`

Expected: FAIL because `render_daily_report` does not accept `macro_context`.

- [ ] **Step 3: Add optional `macro_context` rendering**

Update `render_daily_report` to accept `macro_context: MacroContext | None = None`. Preserve the current placeholder when it is `None`.

- [ ] **Step 4: Run report test**

Run: `python -m pytest tests/test_markdown_writer.py -v`

Expected: PASS.

### Task 3: Daily Job Integration And Verification

**Files:**
- Modify: `app/jobs/daily_market_job.py`

- [ ] **Step 1: Wire analyzer into daily report job**

Import `analyze_macro_context`, compute it from `signals`, and pass it into `render_daily_report`.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -v`

Expected: all tests pass.

- [ ] **Step 3: Review final diff**

Run: `git diff --check` and `git diff --stat`.

Expected: changes are limited to macro analysis, report rendering, docs, and tests.

