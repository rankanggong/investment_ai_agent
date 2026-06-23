from datetime import date
from pathlib import Path

from app.models.analysis import MacroContext, NewsCluster, PriceSignal, SectorRotation


def render_daily_report(
    report_date: date,
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None = None,
    news_clusters: list[NewsCluster] | None = None,
) -> str:
    lines = [
        f"# Daily Market Brief - {report_date.isoformat()}",
        "",
        "Research support only. Not investment advice.",
        "",
        "## 1. Market Overview",
        "",
        "| Asset | 1D | 5D | 20D | Note |",
        "|---|---:|---:|---:|---|",
    ]

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
            "Deferred to Phase 4.",
            "",
            "## 7. Impact On My Plan",
            "",
            "Deferred to Phase 5.",
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
                f"Confidence: {cluster.confidence:.2f}",
                "",
                "Representative headlines:",
            ]
        )
        for headline, url in zip(
            cluster.representative_headlines,
            cluster.source_urls,
        ):
            lines.append(f"- {headline} ({url})")
    return lines
