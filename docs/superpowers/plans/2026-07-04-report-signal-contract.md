# Report Signal Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic report signal contracts, watch-next items, and manual-reading items to the daily report without introducing LLM interpretation.

**Architecture:** Add small dataclasses to `app.models.analysis`, then add one aggregation analyzer that consumes existing analyzer outputs: price signals, sector rotation, macro context, news clusters, fundamental events, and optional data coverage. The markdown writer receives the aggregate object and renders watch-next items inside `## 0. What Matters Today` plus a populated `## 8. What To Read Manually`, preserving the current top-level report order.

**Tech Stack:** Python dataclasses, existing analyzer functions, existing markdown writer, pytest.

---

## File Structure

- Modify: `app/models/analysis.py`
  - Add `SignalInsight`, `WatchNextItem`, `ManualReadItem`, and `ReportSignals`.
- Create: `app/analyzers/report_signal_analyzer.py`
  - Deterministically maps existing analyzer outputs into report signal objects.
- Modify: `app/jobs/daily_market_job.py`
  - Calls `analyze_report_signals(...)` after existing analyzers complete.
- Modify: `app/outputs/markdown_writer.py`
  - Accepts optional `report_signals`.
  - Renders watch-next items inside Section 0.
  - Replaces the static Section 8 message with manual-reading items.
- Create: `tests/test_report_signal_analyzer.py`
  - Unit tests for deterministic signal generation.
- Modify: `tests/test_markdown_writer.py`
  - Rendering tests for watch-next and manual-reading output.

---

### Task 1: Add Signal Contract Models

**Files:**
- Modify: `app/models/analysis.py`
- Test: no direct test file; Task 2 tests import these models.

- [ ] **Step 1: Add dataclasses**

Add these dataclasses after `DataCoverage` and before `MacroEvidenceRow` in `app/models/analysis.py`:

```python
@dataclass(frozen=True)
class SignalInsight:
    subject: str
    observed_fact: str
    trigger_type: str
    evidence_type: list[str]
    interpretation: str
    confidence: str
    data_coverage: str = "available"
    uncertainty: str = ""
    watch_next: str = ""
    invalidation: str = ""


@dataclass(frozen=True)
class WatchNextItem:
    subject: str
    watch: str
    confirmation: str
    invalidation: str
    source: str


@dataclass(frozen=True)
class ManualReadItem:
    title: str
    url: str
    reason: str
    source_type: str
    related_symbol: str
    priority: int


@dataclass(frozen=True)
class ReportSignals:
    insights: list[SignalInsight]
    watch_next: list[WatchNextItem]
    manual_reading: list[ManualReadItem]
```

- [ ] **Step 2: Run import smoke test**

Run: `python -m pytest tests/test_markdown_writer.py::test_render_daily_report_includes_required_sections -v`

Expected: PASS. This model-only change should not alter rendering behavior.

---

### Task 2: Add Deterministic Report Signal Analyzer

**Files:**
- Create: `app/analyzers/report_signal_analyzer.py`
- Create: `tests/test_report_signal_analyzer.py`

- [ ] **Step 1: Write analyzer tests**

Create `tests/test_report_signal_analyzer.py`:

```python
from datetime import datetime

from app.analyzers.report_signal_analyzer import analyze_report_signals
from app.models.analysis import (
    DataCoverage,
    DataCoverageRow,
    FundamentalEvent,
    MacroContext,
    MacroEvidenceRow,
    NewsCluster,
    PriceSignal,
    SectorRotation,
)


def price_signal(
    symbol: str,
    return_1d: float = 0.0,
    return_5d: float = 0.0,
    return_20d: float = 0.0,
    volume_ratio_20d: float | None = None,
    unusual: bool = False,
    reason: str = "",
) -> PriceSignal:
    return PriceSignal(
        symbol=symbol,
        return_1d=return_1d,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=volume_ratio_20d,
        volatility_zscore=None,
        is_unusual_move=unusual,
        reason=reason,
    )


def rotation() -> SectorRotation:
    return SectorRotation(
        strong_sectors=["SOXX"],
        weak_sectors=["XLE"],
        risk_on_score=0.42,
        growth_vs_value="growth_leading",
        cyclical_vs_defensive="mixed",
        notes=[],
    )


def test_report_signals_include_unusual_price_watch_item():
    result = analyze_report_signals(
        price_signals={
            "SOXX": price_signal(
                "SOXX",
                return_1d=0.028,
                return_5d=0.054,
                return_20d=0.092,
                volume_ratio_20d=2.3,
                unusual=True,
                reason="1D return exceeds recent volatility threshold; volume exceeds 2x recent average",
            )
        },
        sector_rotation=rotation(),
        macro_context=None,
        news_clusters=[],
        fundamental_events=[],
        data_coverage=None,
    )

    insight = next(item for item in result.insights if item.subject == "SOXX")
    assert insight.trigger_type == "absolute_move"
    assert insight.evidence_type == ["price_confirmed", "volume_confirmed"]
    assert insight.confidence == "medium"
    assert "SOXX moved 2.80% in 1D" in insight.observed_fact
    assert "No confirmed fundamental event is linked to the move." == insight.uncertainty

    watch = next(item for item in result.watch_next if item.subject == "SOXX")
    assert watch.source == "price"
    assert "volume" in watch.confirmation.lower()
    assert "gives back" in watch.invalidation


def test_report_signals_include_macro_news_fundamental_and_data_gap_items():
    result = analyze_report_signals(
        price_signals={"SPY": price_signal("SPY")},
        sector_rotation=rotation(),
        macro_context=MacroContext(
            rates_context="rates_pressure",
            usd_context="usd_strengthening",
            credit_context="credit_stress",
            gold_context="gold_pressure",
            overall_regime="risk_off_with_macro_pressure",
            notes=[],
            evidence_rows=[
                MacroEvidenceRow(
                    area="Rates",
                    signal="rates_pressure",
                    evidence="TLT 5D -2.10%",
                    interpretation="Long-duration proxies are weak, suggesting rate pressure.",
                )
            ],
        ),
        news_clusters=[
            NewsCluster(
                topic="ai chip demand",
                related_assets=["NVDA"],
                representative_headlines=["Nvidia rises on AI chip demand"],
                source_urls=["https://example.com/nvda"],
                item_count=2,
                confidence=0.8,
                source_count=1,
                why_it_matters="2 stored headlines mention NVDA.",
                manual_read_urls=["https://example.com/nvda"],
            )
        ],
        fundamental_events=[
            FundamentalEvent(
                event_type="earnings_release",
                related_symbol="AAPL",
                headline="Apple reports quarterly earnings",
                publisher="Reuters",
                source_url="https://example.com/aapl",
                confidence=0.85,
                review_type="earnings_review",
                why_it_matters="Earnings can reset assumptions.",
            )
        ],
        data_coverage=DataCoverage(
            rows=[
                DataCoverageRow(
                    category="Macro",
                    item="UUP",
                    status="missing",
                    rows=0,
                    latest="N/A",
                    detail="Needs at least 6 price rows for 5D macro context.",
                )
            ],
            impacts=["Section 4 may be unknown because UUP is missing."],
        ),
    )

    assert any(item.subject == "Rates" and item.trigger_type == "macro_proxy_shift" for item in result.insights)
    assert any(item.subject == "NVDA" and item.trigger_type == "news_cluster" for item in result.insights)
    assert any(item.subject == "AAPL" and item.trigger_type == "fundamental_event" for item in result.insights)
    assert any(item.subject == "Macro: UUP" and item.trigger_type == "data_gap" for item in result.insights)

    manual_urls = [item.url for item in result.manual_reading]
    assert manual_urls == ["https://example.com/aapl", "https://example.com/nvda"]
    assert result.manual_reading[0].priority == 100
    assert result.manual_reading[1].priority == 80
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_report_signal_analyzer.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.analyzers.report_signal_analyzer'`.

- [ ] **Step 3: Implement analyzer**

Create `app/analyzers/report_signal_analyzer.py`:

```python
from app.models.analysis import (
    DataCoverage,
    FundamentalEvent,
    MacroContext,
    NewsCluster,
    PriceSignal,
    ReportSignals,
    SectorRotation,
    SignalInsight,
    WatchNextItem,
    ManualReadItem,
)


def analyze_report_signals(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    news_clusters: list[NewsCluster],
    fundamental_events: list[FundamentalEvent],
    data_coverage: DataCoverage | None = None,
) -> ReportSignals:
    insights: list[SignalInsight] = []
    watch_next: list[WatchNextItem] = []
    manual_reading: list[ManualReadItem] = []

    for signal in price_signals.values():
        if not signal.is_unusual_move:
            continue
        insights.append(_price_insight(signal))
        watch_next.append(_price_watch_item(signal))

    for symbol in sector_rotation.strong_sectors:
        insights.append(_sector_insight(symbol, "relative_strength"))
        watch_next.append(_sector_watch_item(symbol, "leadership broadens into related growth assets"))
    for symbol in sector_rotation.weak_sectors:
        insights.append(_sector_insight(symbol, "relative_weakness"))
        watch_next.append(_sector_watch_item(symbol, "weakness remains isolated instead of spreading"))

    if macro_context is not None:
        for row in macro_context.evidence_rows:
            if row.signal in {"mixed", "unknown"}:
                continue
            insights.append(_macro_insight(row.area, row.signal, row.evidence, row.interpretation))
            watch_next.append(_macro_watch_item(row.area, row.signal))

    for cluster in news_clusters:
        insights.append(_news_insight(cluster))
        watch_next.append(_news_watch_item(cluster))
        manual_reading.extend(_manual_reads_from_cluster(cluster))

    for event in fundamental_events:
        insights.append(_fundamental_insight(event))
        watch_next.append(_fundamental_watch_item(event))
        manual_reading.append(_manual_read_from_event(event))

    if data_coverage is not None:
        for row in data_coverage.rows:
            if row.status == "available":
                continue
            insights.append(_data_gap_insight(row.category, row.item, row.status, row.detail))
            watch_next.append(_data_gap_watch_item(row.category, row.item))

    return ReportSignals(
        insights=insights,
        watch_next=_dedupe_watch_items(watch_next),
        manual_reading=sorted(
            _dedupe_manual_reading(manual_reading),
            key=lambda item: (-item.priority, item.related_symbol, item.title),
        ),
    )


def _price_insight(signal: PriceSignal) -> SignalInsight:
    evidence = ["price_confirmed"]
    if signal.volume_ratio_20d is not None and signal.volume_ratio_20d > 2:
        evidence.append("volume_confirmed")
    return SignalInsight(
        subject=signal.symbol,
        observed_fact=f"{signal.symbol} moved {_format_percent(signal.return_1d)} in 1D.",
        trigger_type="absolute_move",
        evidence_type=evidence,
        interpretation=signal.reason or "Unusual price move detected by deterministic thresholds.",
        confidence="medium",
        uncertainty="No confirmed fundamental event is linked to the move.",
        watch_next=f"Whether {signal.symbol} confirms the move with follow-through and stable volume.",
        invalidation=f"{signal.symbol} gives back the unusual move without related confirmation.",
    )


def _price_watch_item(signal: PriceSignal) -> WatchNextItem:
    return WatchNextItem(
        subject=signal.symbol,
        watch=f"Whether {signal.symbol} follow-through confirms the unusual move.",
        confirmation="Move persists and volume remains above recent average.",
        invalidation=f"{signal.symbol} gives back the move while volume normalizes.",
        source="price",
    )


def _sector_insight(symbol: str, trigger_type: str) -> SignalInsight:
    direction = "strength" if trigger_type == "relative_strength" else "weakness"
    return SignalInsight(
        subject=symbol,
        observed_fact=f"{symbol} appeared in sector rotation {direction}.",
        trigger_type=trigger_type,
        evidence_type=["relative_strength_confirmed"],
        interpretation=f"{symbol} is part of current sector rotation {direction}.",
        confidence="medium",
        uncertainty="Sector rotation does not by itself confirm a fundamental change.",
        watch_next=f"Whether {symbol} {direction} persists versus SPY.",
        invalidation=f"{symbol} stops outperforming or underperforming SPY.",
    )


def _sector_watch_item(symbol: str, confirmation: str) -> WatchNextItem:
    return WatchNextItem(
        subject=symbol,
        watch=f"Whether {symbol} rotation signal persists versus SPY.",
        confirmation=confirmation,
        invalidation=f"{symbol} relative performance returns to neutral.",
        source="sector_rotation",
    )


def _macro_insight(area: str, signal: str, evidence: str, interpretation: str) -> SignalInsight:
    return SignalInsight(
        subject=area,
        observed_fact=evidence,
        trigger_type="macro_proxy_shift",
        evidence_type=["macro_supported"],
        interpretation=interpretation,
        confidence="medium",
        uncertainty="ETF proxies are not a substitute for formal macro data.",
        watch_next=f"Whether {area} proxy evidence continues to support {signal}.",
        invalidation=f"{area} proxy evidence moves back to mixed.",
    )


def _macro_watch_item(area: str, signal: str) -> WatchNextItem:
    return WatchNextItem(
        subject=area,
        watch=f"Whether {area} proxy evidence confirms {signal}.",
        confirmation=f"{area} remains in {signal} on the next report.",
        invalidation=f"{area} returns to mixed or unknown.",
        source="macro_context",
    )


def _news_insight(cluster: NewsCluster) -> SignalInsight:
    subject = _first_asset(cluster.related_assets)
    return SignalInsight(
        subject=subject,
        observed_fact=f"{cluster.item_count} stored news items grouped under {cluster.topic}.",
        trigger_type="news_cluster",
        evidence_type=["news_supported"],
        interpretation=cluster.why_it_matters or "News cluster may explain asset-specific attention.",
        confidence=_confidence_label(cluster.confidence),
        uncertainty="Stored headlines need manual review before treating them as fundamental evidence.",
        watch_next=f"Whether price action in {subject} confirms the news cluster.",
        invalidation=f"{subject} price action does not confirm the news cluster.",
    )


def _news_watch_item(cluster: NewsCluster) -> WatchNextItem:
    subject = _first_asset(cluster.related_assets)
    return WatchNextItem(
        subject=subject,
        watch=f"Whether {subject} price action confirms the {cluster.topic} news cluster.",
        confirmation="Related asset shows follow-through or relative strength.",
        invalidation="Related asset does not react despite continued headlines.",
        source="news_cluster",
    )


def _fundamental_insight(event: FundamentalEvent) -> SignalInsight:
    return SignalInsight(
        subject=event.related_symbol,
        observed_fact=f"{event.related_symbol} had a {event.event_type}: {event.headline}",
        trigger_type="fundamental_event",
        evidence_type=["fundamental_confirmed", "manual_review_required"],
        interpretation=event.why_it_matters or "This event may affect fundamental assumptions.",
        confidence=_confidence_label(event.confidence),
        uncertainty="The source should be read manually before changing assumptions.",
        watch_next=f"Manual review of {event.related_symbol} {event.review_type or event.event_type}.",
        invalidation="Primary-source details show the headline is not material.",
    )


def _fundamental_watch_item(event: FundamentalEvent) -> WatchNextItem:
    return WatchNextItem(
        subject=event.related_symbol,
        watch=f"Read the source for {event.related_symbol} {event.review_type or event.event_type}.",
        confirmation="Primary-source details confirm a material assumption change.",
        invalidation="Primary-source details show limited or no material impact.",
        source="fundamental_event",
    )


def _data_gap_insight(category: str, item: str, status: str, detail: str) -> SignalInsight:
    return SignalInsight(
        subject=f"{category}: {item}",
        observed_fact=detail,
        trigger_type="data_gap",
        evidence_type=["data_limited"],
        interpretation=f"{category} {item} data is {status}.",
        confidence="high",
        data_coverage=status,
        uncertainty="Quiet output may reflect missing or insufficient data.",
        watch_next=f"Whether {category} {item} becomes available after the next collection run.",
        invalidation=f"{category} {item} data becomes available.",
    )


def _data_gap_watch_item(category: str, item: str) -> WatchNextItem:
    return WatchNextItem(
        subject=f"{category}: {item}",
        watch=f"Whether {category} {item} data becomes available after the next collection run.",
        confirmation="Data coverage changes to available.",
        invalidation="Data remains missing or insufficient.",
        source="data_coverage",
    )


def _manual_reads_from_cluster(cluster: NewsCluster) -> list[ManualReadItem]:
    subject = _first_asset(cluster.related_assets)
    urls = cluster.manual_read_urls or cluster.source_urls
    return [
        ManualReadItem(
            title=f"{cluster.topic} news cluster",
            url=url,
            reason=cluster.why_it_matters or "Manual review can confirm whether the cluster matters.",
            source_type="news_cluster",
            related_symbol=subject,
            priority=80,
        )
        for url in urls
    ]


def _manual_read_from_event(event: FundamentalEvent) -> ManualReadItem:
    return ManualReadItem(
        title=event.headline,
        url=event.source_url,
        reason=event.why_it_matters or "Manual review can confirm whether the event is material.",
        source_type=event.review_type or event.event_type,
        related_symbol=event.related_symbol,
        priority=100,
    )


def _dedupe_watch_items(items: list[WatchNextItem]) -> list[WatchNextItem]:
    seen: set[tuple[str, str, str]] = set()
    result: list[WatchNextItem] = []
    for item in items:
        key = (item.subject, item.watch, item.source)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_manual_reading(items: list[ManualReadItem]) -> list[ManualReadItem]:
    seen: set[str] = set()
    result: list[ManualReadItem] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        result.append(item)
    return result


def _first_asset(assets: list[str]) -> str:
    if not assets:
        return "Market"
    return assets[0].upper()


def _confidence_label(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.55:
        return "medium"
    return "low"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"
```

- [ ] **Step 4: Run analyzer tests**

Run: `python -m pytest tests/test_report_signal_analyzer.py -v`

Expected: PASS.

---

### Task 3: Render Watch-Next And Manual Reading Items

**Files:**
- Modify: `app/outputs/markdown_writer.py`
- Modify: `tests/test_markdown_writer.py`

- [ ] **Step 1: Add markdown rendering test**

Append to `tests/test_markdown_writer.py`:

```python
def test_render_daily_report_includes_report_signals_watch_next_and_manual_reading():
    from app.models.analysis import ManualReadItem, ReportSignals, SignalInsight, WatchNextItem

    content = render_daily_report(
        report_date=date(2026, 5, 16),
        price_signals={},
        sector_rotation=SectorRotation(
            strong_sectors=[],
            weak_sectors=[],
            risk_on_score=0.0,
            growth_vs_value="unknown",
            cyclical_vs_defensive="unknown",
            notes=[],
        ),
        report_signals=ReportSignals(
            insights=[
                SignalInsight(
                    subject="SOXX",
                    observed_fact="SOXX moved 2.80% in 1D.",
                    trigger_type="absolute_move",
                    evidence_type=["price_confirmed", "volume_confirmed"],
                    interpretation="Unusual price move detected.",
                    confidence="medium",
                    uncertainty="No confirmed fundamental event is linked to the move.",
                    watch_next="Whether SOXX confirms the move.",
                    invalidation="SOXX gives back the move.",
                )
            ],
            watch_next=[
                WatchNextItem(
                    subject="SOXX",
                    watch="Whether SOXX follow-through confirms the unusual move.",
                    confirmation="Move persists and volume remains above recent average.",
                    invalidation="SOXX gives back the move while volume normalizes.",
                    source="price",
                )
            ],
            manual_reading=[
                ManualReadItem(
                    title="Apple reports quarterly earnings",
                    url="https://example.com/aapl",
                    reason="Earnings can reset assumptions.",
                    source_type="earnings_review",
                    related_symbol="AAPL",
                    priority=100,
                )
            ],
        ),
    )

    assert "Watch next:" in content
    assert "- SOXX: Whether SOXX follow-through confirms the unusual move." in content
    assert "## 8. What To Read Manually" in content
    assert "| Priority | Asset | Type | Reason | Source |" in content
    assert (
        "| 100 | AAPL | earnings_review | Earnings can reset assumptions. | "
        "Apple reports quarterly earnings (https://example.com/aapl) |"
    ) in content
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/test_markdown_writer.py::test_render_daily_report_includes_report_signals_watch_next_and_manual_reading -v`

Expected: FAIL because `render_daily_report` does not accept `report_signals`.

- [ ] **Step 3: Update markdown writer imports and signature**

In `app/outputs/markdown_writer.py`, import `ReportSignals` and add an optional parameter:

```python
from app.models.analysis import (
    CompanyPriceBounds,
    DataCoverage,
    DailySignalSummary,
    FundamentalEvent,
    MacroContext,
    NewsCluster,
    PlanImpact,
    PlanImpactItem,
    PriceSignal,
    ReportSignals,
    SectorRotation,
)
```

Change `render_daily_report(...)` signature:

```python
def render_daily_report(
    report_date: date,
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None = None,
    news_clusters: list[NewsCluster] | None = None,
    fundamental_events: list[FundamentalEvent] | None = None,
    daily_signal_summary: DailySignalSummary | None = None,
    data_coverage: DataCoverage | None = None,
    plan_impact: PlanImpact | None = None,
    company_price_bounds: CompanyPriceBounds | None = None,
    report_signals: ReportSignals | None = None,
) -> str:
```

- [ ] **Step 4: Render watch-next inside Section 0**

After `lines.extend(_render_daily_signal_summary(daily_signal_summary))`, add:

```python
    lines.extend(_render_watch_next(report_signals))
```

Add helper:

```python
def _render_watch_next(report_signals: ReportSignals | None) -> list[str]:
    if report_signals is None or not report_signals.watch_next:
        return []

    lines = ["", "Watch next:"]
    for item in report_signals.watch_next[:5]:
        lines.append(f"- {item.subject}: {item.watch}")
    return lines
```

- [ ] **Step 5: Render manual reading list in Section 8**

Replace the static Section 8 block:

```python
            "## 8. What To Read Manually",
            "",
            "No reading list generated in Phase 1.",
            "",
            "## 9. Popular Company Price Bounds",
            "",
```

with:

```python
            "## 8. What To Read Manually",
            "",
        ]
    )
    lines.extend(_render_manual_reading(report_signals))
    lines.extend(
        [
            "",
            "## 9. Popular Company Price Bounds",
            "",
```

Add helper:

```python
def _render_manual_reading(report_signals: ReportSignals | None) -> list[str]:
    if report_signals is None or not report_signals.manual_reading:
        return ["No manual reading items generated."]

    lines = [
        "| Priority | Asset | Type | Reason | Source |",
        "|---:|---|---|---|---|",
    ]
    for item in report_signals.manual_reading[:10]:
        lines.append(
            f"| {item.priority} | {item.related_symbol} | {item.source_type} | "
            f"{item.reason} | {item.title} ({item.url}) |"
        )
    return lines
```

- [ ] **Step 6: Run markdown test**

Run: `python -m pytest tests/test_markdown_writer.py::test_render_daily_report_includes_report_signals_watch_next_and_manual_reading -v`

Expected: PASS.

---

### Task 4: Wire Daily Job

**Files:**
- Modify: `app/jobs/daily_market_job.py`
- Test: `tests/test_markdown_writer.py`, `tests/test_report_signal_analyzer.py`

- [ ] **Step 1: Import analyzer**

Add import in `app/jobs/daily_market_job.py`:

```python
from app.analyzers.report_signal_analyzer import analyze_report_signals
```

- [ ] **Step 2: Compute report signals**

After `daily_signal_summary = analyze_daily_signal_summary(...)`, add:

```python
    report_signals = analyze_report_signals(
        price_signals=signals,
        sector_rotation=sector_rotation,
        macro_context=macro_context,
        news_clusters=news_clusters,
        fundamental_events=fundamental_events,
        data_coverage=data_coverage,
    )
```

- [ ] **Step 3: Pass to writer**

In `render_daily_report(...)` call, add:

```python
        report_signals=report_signals,
```

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_report_signal_analyzer.py tests/test_markdown_writer.py -v`

Expected: PASS.

---

### Task 5: Full Verification

**Files:**
- No edits.

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest -v`

Expected: PASS.

- [ ] **Step 2: Inspect git status**

Run: `git status --short`

Expected: changed files include the model, analyzer, markdown writer, daily job, new analyzer test, modified markdown writer test, and this plan. Existing unrelated modified/untracked files may still appear and must not be reverted.

---

## How Analyzer-First Works

The key implementation rule is:

```text
existing analyzer outputs -> report_signal_analyzer -> structured signal objects -> markdown rendering
```

The markdown writer should never infer that a price move means a fundamental change. It only renders fields that already exist:

```text
observed_fact = computed fact from existing analyzer output
trigger_type = deterministic category such as absolute_move or macro_proxy_shift
evidence_type = deterministic support such as price_confirmed or news_supported
confidence = rule-based label from thresholds or existing confidence score
uncertainty = fixed language tied to evidence limits
watch_next = deterministic follow-up condition
invalidation = deterministic condition that weakens the signal
```

This keeps LLM and prose layers downstream of analysis. If an LLM layer is added later, it can compress or restyle these objects but cannot create new facts.

---

## Self-Review

Spec coverage:

- Signal contract fields are introduced in Task 1.
- Deterministic analyzer generation is implemented in Task 2.
- Watch-next rendering is implemented inside Section 0 in Task 3, preserving the top-level report order.
- Manual reading list populates existing Section 8 in Task 3.
- Daily job wiring is covered in Task 4.
- Verification is covered in Task 5.

Placeholder scan:

- No placeholder markers or undefined task references remain.

Type consistency:

- `ReportSignals`, `SignalInsight`, `WatchNextItem`, and `ManualReadItem` names match across model, analyzer, writer, and tests.
