from datetime import date
from pathlib import Path

from app.models.analysis import (
    DailySignalSummary,
    FundamentalEvent,
    MacroContext,
    NewsCluster,
    PlanImpact,
    PlanImpactItem,
    PriceSignal,
    SectorRotation,
)


def render_daily_report(
    report_date: date,
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None = None,
    news_clusters: list[NewsCluster] | None = None,
    fundamental_events: list[FundamentalEvent] | None = None,
    daily_signal_summary: DailySignalSummary | None = None,
    plan_impact: PlanImpact | None = None,
) -> str:
    lines = [
        f"# Daily Market Brief - {report_date.isoformat()}",
        "",
        "Research support only. Not investment advice.",
        "",
        "## 0. What Matters Today",
        "",
    ]
    lines.extend(_render_daily_signal_summary(daily_signal_summary))
    lines.extend(
        [
            "",
            "## 1. Market Overview",
            "",
            "| Asset | 1D | 5D | 20D | Note |",
            "|---|---:|---:|---:|---|",
        ]
    )

    for symbol in sorted(price_signals):
        signal = price_signals[symbol]
        lines.append(
            f"| {symbol} | {_format_percent(signal.return_1d)} | "
            f"{_format_percent(signal.return_5d)} | {_format_percent(signal.return_20d)} | "
            f"{signal.reason if signal.reason else ''} |"
        )

    lines.extend(
        [
            "",
            "## 2. Biggest Moves",
            "",
            "| Asset | Move | Possible Driver | Confidence |",
            "|---|---:|---|---:|",
        ]
    )

    unusual = [signal for signal in price_signals.values() if signal.is_unusual_move]
    for signal in sorted(unusual, key=lambda item: abs(item.return_1d or 0), reverse=True):
        lines.append(
            f"| {signal.symbol} | {_format_percent(signal.return_1d)} | "
            f"{signal.reason or 'Needs review'} | N/A |"
        )

    if not unusual:
        lines.append("| None |  | No unusual price move detected by Phase 1 rules |  |")

    lines.extend(
        [
            "",
            "## 3. Sector Rotation",
            "",
            f"Strong: {_format_list(sector_rotation.strong_sectors)}",
            "",
            f"Weak: {_format_list(sector_rotation.weak_sectors)}",
            "",
            f"Risk-on score: {sector_rotation.risk_on_score:.2f}",
            "",
            f"Growth vs value: {sector_rotation.growth_vs_value}",
            "",
            f"Cyclical vs defensive: {sector_rotation.cyclical_vs_defensive}",
            "",
            "## 4. Macro Context",
            "",
        ]
    )
    lines.extend(_render_macro_context(macro_context))
    lines.extend(
        [
            "",
            "## 5. Important News Clusters",
            "",
        ]
    )
    lines.extend(_render_news_clusters(news_clusters or []))
    lines.extend(
        [
            "",
            "## 6. Fundamental Events",
            "",
        ]
    )
    lines.extend(_render_fundamental_events(fundamental_events))
    lines.extend(
        [
            "",
            "## 7. Impact On My Plan",
            "",
        ]
    )
    lines.extend(_render_plan_impact(plan_impact))
    lines.extend(
        [
            "",
            "## 8. What To Read Manually",
            "",
            "No reading list generated in Phase 1.",
            "",
        ]
    )
    return "\n".join(lines)


def write_daily_report(report_dir: Path, report_date: date, content: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"daily-market-brief-{report_date.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _format_list(values: list[str]) -> str:
    if not values:
        return "None"
    return ", ".join(values)


def _render_daily_signal_summary(
    daily_signal_summary: DailySignalSummary | None,
) -> list[str]:
    if daily_signal_summary is None:
        daily_signal_summary = DailySignalSummary(
            status="not_available",
            drivers=["Summary was not generated."],
            reason="Daily signal summary was not generated for this report.",
        )

    lines = [
        f"Status: {daily_signal_summary.status}",
        "",
        "Drivers:",
    ]
    lines.extend(f"- {driver}" for driver in daily_signal_summary.drivers)
    lines.extend(["", f"Reason: {daily_signal_summary.reason}"])
    return lines


def _render_macro_context(macro_context: MacroContext | None) -> list[str]:
    if macro_context is None:
        return ["Deferred to Phase 3."]

    lines = [
        f"Rates: {macro_context.rates_context}",
        "",
        f"USD: {macro_context.usd_context}",
        "",
        f"Credit: {macro_context.credit_context}",
        "",
        f"Gold: {macro_context.gold_context}",
        "",
        f"Regime: {macro_context.overall_regime}",
    ]
    if macro_context.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in macro_context.notes)
    if macro_context.evidence_rows:
        lines.extend(
            [
                "",
                "Evidence:",
                "",
                "| Area | Signal | Evidence | Interpretation |",
                "|---|---|---|---|",
            ]
        )
        for row in macro_context.evidence_rows:
            lines.append(
                f"| {row.area} | {row.signal} | {row.evidence} | {row.interpretation} |"
            )
    return lines


def _render_news_clusters(news_clusters: list[NewsCluster]) -> list[str]:
    if not news_clusters:
        return ["No important news clusters available."]

    lines: list[str] = []
    for cluster in news_clusters:
        if lines:
            lines.append("")
        lines.extend(
            [
                f"### {cluster.topic}",
                "",
                f"Assets: {_format_list(cluster.related_assets)}",
                "",
                f"Items: {cluster.item_count}",
                "",
                f"Sources: {cluster.source_count}",
                "",
                f"Confidence: {cluster.confidence:.2f}",
                "",
                f"Why it matters: {cluster.why_it_matters or 'No deterministic explanation available.'}",
                "",
                "Representative headlines:",
            ]
        )
        for headline, url in zip(
            cluster.representative_headlines,
            cluster.source_urls,
        ):
            lines.append(f"- {headline} ({url})")
        manual_read_urls = cluster.manual_read_urls or cluster.source_urls
        if manual_read_urls:
            lines.extend(["", "Manual read:"])
            lines.extend(f"- {url}" for url in manual_read_urls)
    return lines


def _render_fundamental_events(
    fundamental_events: list[FundamentalEvent] | None,
) -> list[str]:
    if fundamental_events is None:
        return ["Deferred to Phase 4."]
    if not fundamental_events:
        return ["No fundamental events detected from stored news."]

    lines = [
        "| Event | Asset | Review Type | Confidence | Why It Matters | Headline | Source |",
        "|---|---|---|---:|---|---|---|",
    ]
    for event in fundamental_events:
        source = (
            f"{event.publisher} ({event.source_url})"
            if event.publisher
            else event.source_url
        )
        lines.append(
            f"| {event.event_type} | {event.related_symbol} | "
            f"{event.review_type or 'fundamental_review'} | "
            f"{event.confidence:.2f} | "
            f"{event.why_it_matters or 'This event may affect fundamental assumptions.'} | "
            f"{event.headline} | {source} |"
        )
    return lines


def _render_plan_impact(plan_impact: PlanImpact | None) -> list[str]:
    if plan_impact is None:
        return ["Deferred to Phase 5."]

    lines = [
        "Research support only. Not a buy/sell instruction.",
        "",
    ]
    if not plan_impact.accumulation_review and not plan_impact.derisk_review:
        lines.append("### No clear plan impact")
        lines.append("")
        if plan_impact.notes:
            lines.extend(f"- {note}" for note in plan_impact.notes)
        else:
            lines.append("- No asset crossed accumulation or de-risk review thresholds.")
        return lines

    lines.extend(
        _render_plan_impact_bucket(
            "High-conviction accumulation review",
            plan_impact.accumulation_review,
        )
    )
    lines.append("")
    lines.extend(
        _render_plan_impact_bucket(
            "High-conviction de-risk review",
            plan_impact.derisk_review,
        )
    )
    if plan_impact.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in plan_impact.notes)
    return lines


def _render_plan_impact_bucket(
    title: str,
    items: list[PlanImpactItem],
) -> list[str]:
    lines = [
        f"### {title}",
        "",
    ]
    if not items:
        lines.append("No candidates.")
        return lines

    lines.extend(
        [
            "| Asset | Score | Evidence |",
            "|---|---:|---|",
        ]
    )
    for item in items:
        lines.append(f"| {item.symbol} | {item.score} | {'; '.join(item.evidence)} |")
    return lines
