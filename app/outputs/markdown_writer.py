from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.analysis import (
    CompanyPriceBounds,
    DataCoverage,
    DailySignalSummary,
    MacroContext,
    NewsQualityGate,
    PriceSignal,
    ReportSignals,
    SectorRotation,
)
from app.steward.models import FxConversion, HoldingPosition, PortfolioReportState


def render_daily_report(
    report_date: date,
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None = None,
    daily_signal_summary: DailySignalSummary | None = None,
    data_coverage: DataCoverage | None = None,
    company_price_bounds: CompanyPriceBounds | None = None,
    report_signals: ReportSignals | None = None,
    portfolio_state: PortfolioReportState | None = None,
    news_quality: NewsQualityGate | None = None,
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
    lines.extend(_render_watch_next(report_signals))
    lines.extend(
        [
            "",
            "## Data Quality",
            "",
        ]
    )
    lines.extend(_render_data_coverage(data_coverage, news_quality))
    if portfolio_state is not None:
        lines.extend(
            [
                "",
                "## Portfolio Holdings",
                "",
            ]
        )
        lines.extend(_render_portfolio_holdings(portfolio_state.holdings))
        lines.extend(
            [
                "",
                "## FX Conversions",
                "",
            ]
        )
        lines.extend(_render_fx_conversions(portfolio_state.fx_conversions))
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
            "## 5. Triggered Strategy Rules",
            "",
        ]
    )
    lines.extend(_render_strategy_rules(news_quality))
    lines.extend(
        [
            "",
            "## 6. Popular Company Price Bounds",
            "",
        ]
    )
    lines.extend(_render_company_price_bounds(company_price_bounds))
    lines.append("")
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


def _render_watch_next(report_signals: ReportSignals | None) -> list[str]:
    if report_signals is None or not report_signals.watch_next:
        return []

    lines = ["", "Watch next:"]
    for item in report_signals.watch_next[:5]:
        lines.append(f"- {item.subject}: {item.watch}")
    return lines


def _render_data_coverage(
    data_coverage: DataCoverage | None,
    news_quality: NewsQualityGate | None,
) -> list[str]:
    if data_coverage is None:
        overall_status = (
            "data_quality_failed"
            if news_quality is not None
            and news_quality.status == "data_quality_review"
            else "unavailable"
        )
        lines = [
            f"Overall: {overall_status}",
            "",
            "No data coverage diagnostics generated.",
        ]
    else:
        overall_status = data_coverage.status
        if news_quality is not None and news_quality.status == "data_quality_review":
            overall_status = "data_quality_failed"
        lines = [
            f"Overall: {overall_status}",
            "",
            "| Category | Item | Status | Rows | Latest | Detail |",
            "|---|---|---|---:|---|---|",
        ]
        for row in data_coverage.rows:
            lines.append(
                f"| {row.category} | {row.item} | {row.status} | "
                f"{row.rows} | {row.latest} | {row.detail} |"
            )
        if data_coverage.impacts:
            lines.extend(["", "Impact:"])
            lines.extend(f"- {impact}" for impact in data_coverage.impacts)

    if news_quality is not None:
        precision = (
            "N/A"
            if news_quality.entity_precision is None
            else f"{news_quality.entity_precision:.2%}"
        )
        lines.extend(
            [
                "",
                "News quality gate:",
                f"- Status: {news_quality.status}",
                f"- Entity precision: {precision}",
                f"- Precision threshold: {news_quality.precision_threshold:.2%}",
                f"- news_score: {_format_nullable_score(news_quality.news_score)}",
                f"- fundamental_score: {_format_nullable_score(news_quality.fundamental_score)}",
                f"- portfolio_action: {news_quality.portfolio_action}",
            ]
        )
        lines.extend(f"- Reason: {reason}" for reason in news_quality.reasons)
    return lines


def _render_portfolio_holdings(
    portfolio_holdings: list[HoldingPosition],
) -> list[str]:
    if not portfolio_holdings:
        return ["No portfolio holdings supplied."]

    lines = [
        "| Institution | Account | Symbol | Name | Currency | Quantity | Unit Cost | Total Cost | As Of |",
        "|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for holding in portfolio_holdings:
        lines.append(
            f"| {_escape_cell(holding.institution)} | "
            f"{_escape_cell(holding.account_label)} | "
            f"{_escape_cell(holding.symbol)} | {_escape_cell(holding.name)} | "
            f"{holding.currency} | {_format_decimal_compact(holding.quantity)} | "
            f"{_format_decimal_compact(holding.unit_cost)} | "
            f"{holding.total_cost:.2f} | {holding.as_of_date.isoformat()} |"
        )
    return lines


def _render_fx_conversions(
    fx_conversions: list[FxConversion],
) -> list[str]:
    if not fx_conversions:
        return ["No FX conversions supplied."]

    lines = [
        "| Date | Account | Sold | Bought | Effective Rate | Fee |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for conversion in fx_conversions:
        fee_currency = conversion.fee_currency or "—"
        lines.append(
            f"| {conversion.fx_date.isoformat()} | "
            f"{_escape_cell(conversion.institution)} / "
            f"{_escape_cell(conversion.account_label)} | "
            f"{conversion.sold_currency} "
            f"{_format_money_decimal(conversion.sold_amount)} | "
            f"{conversion.bought_currency} "
            f"{_format_money_decimal(conversion.bought_amount)} | "
            f"{conversion.effective_rate:.4f} "
            f"{conversion.sold_currency}/{conversion.bought_currency} | "
            f"{fee_currency} {conversion.fee_amount:.2f} |"
        )
    return lines


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _format_decimal_compact(value: Decimal) -> str:
    return format(value, "f")


def _format_money_decimal(value: Decimal) -> str:
    return f"{value:.2f}"


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


def _render_strategy_rules(news_quality: NewsQualityGate | None) -> list[str]:
    lines = ["Portfolio action: unavailable", ""]
    if news_quality is not None and news_quality.status == "data_quality_review":
        lines.append(
            "- Data quality circuit breaker is active; news and fundamental scores are null."
        )
    lines.append("- No explicit strategy rule configuration is active.")
    lines.append("- Market evidence is not converted into an automatic portfolio action.")
    return lines


def _format_nullable_score(value: float | None) -> str:
    return "null" if value is None else f"{value:.2f}"


def _render_company_price_bounds(
    company_price_bounds: CompanyPriceBounds | None,
) -> list[str]:
    if company_price_bounds is None:
        return ["No popular company price bounds generated."]

    lines = [
        "Research support only. These are price-derived review bands, not intrinsic value.",
        "",
    ]
    if company_price_bounds.bounds:
        lines.extend(
            [
                "| Company | Latest | Lower Review Bound | Upper Review Bound | Basis | Confidence |",
                "|---|---:|---:|---:|---|---:|",
            ]
        )
        for bound in company_price_bounds.bounds:
            lines.append(
                f"| {bound.symbol} | {_format_decimal(bound.latest)} | "
                f"{_format_decimal(bound.lower_review_bound)} | "
                f"{_format_decimal(bound.upper_review_bound)} | "
                f"{bound.basis} | {bound.confidence:.2f} |"
            )
    else:
        lines.append("No company price bounds available.")

    notes = _company_price_bound_notes(company_price_bounds)
    if notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in notes)
    return lines


def _company_price_bound_notes(company_price_bounds: CompanyPriceBounds) -> list[str]:
    notes: list[str] = []
    for bound in company_price_bounds.bounds:
        notes.extend(f"{bound.symbol}: {note}" for note in bound.notes)
    notes.extend(company_price_bounds.notes)
    return notes


def _format_decimal(value: float) -> str:
    return f"{value:.2f}"
