from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.analysis import (
    CompanyPriceBounds,
    DataCoverage,
    DailySignalSummary,
    MarketEvidence,
    MacroContext,
    NewsQualityGate,
    PortfolioSummary,
    PriceSignal,
    ReportState,
    ReportSignals,
    RiskAssessment,
    SectorRotation,
    StrategyRuleResult,
)
from app.analyzers.daily_report_state_analyzer import serialize_report_state
from app.steward.models import (
    CashPosition,
    FxConversion,
    HoldingPosition,
    PortfolioReportState,
)


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
    portfolio_summary: PortfolioSummary | None = None,
    risk_assessment: RiskAssessment | None = None,
    key_evidence: list[MarketEvidence] | None = None,
    strategy_rules: list[StrategyRuleResult] | None = None,
    changes: list[str] | None = None,
    gpt_questions: list[str] | None = None,
    report_state: ReportState | None = None,
    price_sources: dict[str, str] | None = None,
) -> str:
    effective_risk = risk_assessment or RiskAssessment(
        score=0,
        level="unknown",
        explanations=["Risk assessment was not generated."],
    )
    effective_evidence = key_evidence or []
    effective_rules = strategy_rules or []
    lines = [
        f"# Daily Market State - {report_date.isoformat()}",
        "",
        "Research support only. Not investment advice.",
        "",
        "## 0. Executive State",
        "",
        _executive_sentence(
            daily_signal_summary,
            macro_context,
            effective_risk,
        ),
        "",
        "## 1. Data Quality",
        "",
    ]
    lines.extend(_render_data_quality_issues(data_coverage, news_quality))
    lines.extend(
        [
            "",
            "## 2. Portfolio Summary",
            "",
        ]
    )
    lines.extend(_render_portfolio_summary(portfolio_summary))
    lines.extend(
        [
            "",
            "## 3. Changes Since Previous Report",
            "",
        ]
    )
    lines.extend(f"- {change}" for change in (changes or ["No state changes detected."]))
    lines.extend(
        [
            "",
            "## 4. Key Market Evidence",
            "",
        ]
    )
    lines.extend(_render_key_evidence(effective_evidence))
    lines.extend(
        [
            "",
            "## 5. Triggered Rules",
            "",
        ]
    )
    lines.extend(_render_triggered_rules(effective_rules))
    lines.extend(["", f"Risk score: {effective_risk.score}/100 ({effective_risk.level})"])
    lines.extend(f"- {reason}" for reason in effective_risk.explanations)
    lines.extend(
        [
            "",
            "## 6. GPT Analysis Tasks",
            "",
        ]
    )
    questions = gpt_questions or ["No GPT analysis task was generated."]
    lines.extend(f"{index}. {question}" for index, question in enumerate(questions, 1))
    lines.extend(
        [
            "",
            "## Appendix",
            "",
            "### A. Full Price Evidence",
            "",
        ]
    )
    lines.extend(_render_full_price_evidence(price_signals))
    lines.extend(["", "### B. Account Detail", ""])
    if portfolio_state is None:
        lines.append("No portfolio state supplied.")
    else:
        lines.extend(["#### Cash Positions", ""])
        lines.extend(_render_cash_positions(portfolio_state.cash_positions))
        lines.extend(["", "#### Holding Snapshots", ""])
        lines.extend(_render_portfolio_holdings(portfolio_state.holdings))
        lines.extend(["", "#### FX Conversions", ""])
        lines.extend(_render_fx_conversions(portfolio_state.fx_conversions))
    lines.extend(["", "### C. Company Price Bounds", ""])
    lines.extend(_render_company_price_bounds(company_price_bounds))
    lines.extend(["", "### D. Macro Evidence and Raw Sources", ""])
    lines.extend(_render_macro_context(macro_context))
    lines.extend(["", "Raw price sources:", ""])
    lines.extend(_render_raw_sources(price_sources or {}))
    if report_state is not None:
        lines.extend(["", serialize_report_state(report_state)])
    lines.append("")
    return "\n".join(lines)


def write_daily_report(report_dir: Path, report_date: date, content: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"daily-market-brief-{report_date.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _executive_sentence(
    summary: DailySignalSummary | None,
    macro_context: MacroContext | None,
    risk: RiskAssessment,
) -> str:
    status = summary.status if summary is not None else "not_available"
    regime = (
        macro_context.overall_regime
        if macro_context is not None
        else "not_available"
    )
    return (
        f"Market state is {status}; macro regime is {regime}; "
        f"deterministic risk is {risk.score}/100 ({risk.level})."
    )


def _render_data_quality_issues(
    data_coverage: DataCoverage | None,
    news_quality: NewsQualityGate | None,
) -> list[str]:
    lines = [
        "| Module | Item | Status | Latest | Detail |",
        "|---|---|---|---|---|",
    ]
    issue_count = 0
    if data_coverage is None:
        lines.append(
            "| Data coverage | all | blocked | N/A | Diagnostics were not generated. |"
        )
        issue_count += 1
    else:
        for row in data_coverage.rows:
            if row.status == "available":
                continue
            lines.append(
                f"| {row.category} | {row.item} | {row.status} | "
                f"{row.latest} | {_escape_cell(row.detail)} |"
            )
            issue_count += 1
    if news_quality is not None and news_quality.status in {
        "disabled",
        "data_quality_review",
    }:
        detail = "; ".join(news_quality.reasons) or "No detail supplied."
        lines.append(
            f"| News | entity pipeline | blocked | N/A | {_escape_cell(detail)} |"
        )
        issue_count += 1
    if issue_count == 0:
        return ["No missing, stale, insufficient, or blocked modules."]
    if data_coverage is not None and data_coverage.impacts:
        lines.extend(["", "Impact:"])
        lines.extend(
            f"- {impact}"
            for impact in data_coverage.impacts
            if "No data coverage gaps" not in impact
        )
    return lines


def _render_portfolio_summary(
    summary: PortfolioSummary | None,
) -> list[str]:
    if summary is None:
        return ["Portfolio summary was not generated."]
    lines = [
        f"Aggregation basis: supplied holding cost in {summary.base_currency}.",
        "",
        f"Total holding cost: {_format_money(summary.total_holding_cost, summary.base_currency)}",
        "",
        "| Asset | Current Cost | Current Allocation | Target Allocation | Gap | Target Cost Gap |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if summary.allocations:
        for row in summary.allocations:
            lines.append(
                f"| {row.symbol} | "
                f"{_format_money(row.current_value, summary.base_currency)} | "
                f"{_format_percent(row.current_weight)} | "
                f"{_format_percent(row.target_weight)} | "
                f"{_format_percent(row.weight_gap)} | "
                f"{_format_money(row.target_value_gap, summary.base_currency)} |"
            )
    else:
        lines.append("| None | N/A | N/A | N/A | N/A | N/A |")
    lines.extend(
        [
            "",
            f"Daily investment budget: "
            f"{_format_money(summary.daily_investment_budget, summary.base_currency)}",
            "",
            f"USD cash: USD {summary.usd_cash:.2f}",
            "",
            f"USD daily spend: {_format_money(summary.usd_daily_spend, 'USD')}",
            "",
            (
                "USD coverage days: N/A"
                if summary.usd_coverage_days is None
                else f"USD coverage days: {summary.usd_coverage_days:.1f}"
            ),
        ]
    )
    if summary.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in summary.notes)
    return lines


def _render_key_evidence(evidence: list[MarketEvidence]) -> list[str]:
    if not evidence:
        return ["No key market evidence available."]
    lines = [
        "| Asset / Macro | Latest | 1D | 5D | 20D | Structural Trend | Short-Term State | Detection Reason |",
        "|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in evidence:
        lines.append(
            f"| {row.symbol} | {_format_decimal_or_na(row.latest)} | "
            f"{_format_percent(row.return_1d)} | {_format_percent(row.return_5d)} | "
            f"{_format_percent(row.return_20d)} | {row.structural_trend} | "
            f"{row.short_term_state} | {_escape_cell(row.detection_reason)} |"
        )
    return lines


def _render_triggered_rules(
    rules: list[StrategyRuleResult],
) -> list[str]:
    if not rules:
        return ["No strategy rule is triggered or near its threshold."]
    lines = [
        "| Rule | Status | Observed | Threshold | Detection Reason |",
        "|---|---|---|---|---|",
    ]
    for rule in rules:
        lines.append(
            f"| {rule.name} | {rule.status} | {_escape_cell(rule.observed)} | "
            f"{_escape_cell(rule.threshold)} | {_escape_cell(rule.reason)} |"
        )
    return lines


def _render_full_price_evidence(
    price_signals: dict[str, PriceSignal],
) -> list[str]:
    lines = [
        "| Asset | Latest | Latest Date | 1D | 5D | 20D | Detection Reason |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    if not price_signals:
        lines.append("| None | N/A | N/A | N/A | N/A | N/A | No price signals. |")
        return lines
    for symbol in sorted(price_signals):
        signal = price_signals[symbol]
        lines.append(
            f"| {symbol} | {_format_decimal_or_na(signal.latest)} | "
            f"{signal.latest_date.isoformat() if signal.latest_date else 'N/A'} | "
            f"{_format_percent(signal.return_1d)} | "
            f"{_format_percent(signal.return_5d)} | "
            f"{_format_percent(signal.return_20d)} | "
            f"{_escape_cell(signal.reason or 'No detector threshold crossed.')} |"
        )
    return lines


def _render_cash_positions(cash_positions: list[CashPosition]) -> list[str]:
    if not cash_positions:
        return ["No cash positions supplied."]
    lines = [
        "| Institution | Account | Currency | Balance | As Of |",
        "|---|---|---|---:|---|",
    ]
    for position in cash_positions:
        lines.append(
            f"| {_escape_cell(position.institution)} | "
            f"{_escape_cell(position.account_label)} | {position.currency} | "
            f"{_format_decimal_compact(position.balance)} | "
            f"{position.as_of_date.isoformat()} |"
        )
    return lines


def _render_raw_sources(price_sources: dict[str, str]) -> list[str]:
    if not price_sources:
        return ["- No raw price-source metadata available."]
    return [
        f"- {symbol}: {source}"
        for symbol, source in sorted(price_sources.items())
    ]


def _format_decimal_or_na(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def _format_money(value: float | None, currency: str) -> str:
    return "N/A" if value is None else f"{currency} {value:.2f}"


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
