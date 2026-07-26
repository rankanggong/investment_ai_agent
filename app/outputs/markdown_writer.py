from datetime import date
from decimal import Decimal
from pathlib import Path

from app.models.analysis import (
    CompanyPriceBounds,
    AssetEvent,
    DataCoverage,
    DataCoverageRow,
    DailySignalSummary,
    DecisionContext,
    FxCostComparison,
    FxState,
    FundamentalEvidenceState,
    GptAnalysisTask,
    MarketBreadth,
    MarketEvidence,
    MarketState,
    MacroContext,
    NewsQualityGate,
    NewsCluster,
    NewsState,
    PortfolioAllocationView,
    PortfolioDecisionState,
    PortfolioImpactAnalysis,
    PortfolioRiskAssessment,
    PortfolioSummary,
    PriceSignal,
    ReportState,
    ReportSignals,
    ReportUseStates,
    RiskAssessment,
    SectorRotation,
    StrategyRuleResult,
    StrategyDecisionState,
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
    portfolio_decision_risk: PortfolioRiskAssessment | None = None,
    use_states: ReportUseStates | None = None,
    market_breadth: MarketBreadth | None = None,
    fx_costs: list[FxCostComparison] | None = None,
    fx_state: FxState | None = None,
    key_evidence: list[MarketEvidence] | None = None,
    strategy_rules: list[StrategyRuleResult] | None = None,
    strategy_decision: StrategyDecisionState | None = None,
    changes: list[str] | None = None,
    gpt_questions: list[str] | None = None,
    gpt_tasks: list[GptAnalysisTask] | None = None,
    report_state: ReportState | None = None,
    price_sources: dict[str, str] | None = None,
    portfolio_impact: PortfolioImpactAnalysis | None = None,
    fundamental_state: FundamentalEvidenceState | None = None,
    news_clusters: list[NewsCluster] | None = None,
    asset_events: list[AssetEvent] | None = None,
    decision_context: DecisionContext | None = None,
) -> str:
    effective_risk = risk_assessment or RiskAssessment(
        score=0,
        level="unknown",
        explanations=["Risk assessment was not generated."],
    )
    effective_evidence = key_evidence or []
    effective_rules = strategy_rules or []
    effective_portfolio_decision_risk = (
        portfolio_decision_risk
        or PortfolioRiskAssessment(
            exposure_risk=RiskAssessment(
                score=0,
                level="unknown",
                explanations=["Portfolio exposure risk was not generated."],
                scope="portfolio_exposure",
            ),
            data_quality_risk=RiskAssessment(
                score=0,
                level="unknown",
                explanations=["Portfolio data-quality risk was not generated."],
                scope="portfolio_data_quality",
            ),
            decision_readiness="blocked",
            readiness_reasons=("Portfolio risk was not evaluated.",),
        )
    )
    effective_use_states = use_states or ReportUseStates(
        market=MarketState(
            risk=effective_risk.level,
            regime=(
                macro_context.overall_regime
                if macro_context is not None
                else "unknown"
            ),
            actionability="available" if price_signals else "blocked",
            reason="Fallback state derived by the renderer.",
        ),
        portfolio=PortfolioDecisionState(
            risk="unknown",
            data_readiness="blocked",
            actionability="blocked",
            reason="Portfolio decision readiness was not evaluated.",
        ),
        news=NewsState(
            quality="blocked",
            actionability="unavailable",
            reason="News state was not evaluated.",
        ),
    )
    lines = [
        f"# Daily Market State - {report_date.isoformat()}",
        "",
        "Research support only. Not investment advice.",
        "",
        "## 0. Executive State",
        "",
    ]
    lines.extend(_render_executive_states(effective_use_states, strategy_decision))
    lines.extend(["", "## 1. Data Quality", ""])
    lines.extend(
        _render_data_quality_issues(
            data_coverage,
            news_quality,
            effective_use_states,
        )
    )
    lines.extend(
        [
            "",
            "## 2. Portfolio Summary",
            "",
            "Evidence Ref: PORTFOLIO:ALLOCATION",
            "",
        ]
    )
    lines.extend(_render_portfolio_summary(portfolio_summary))
    lines.extend(["", "### Portfolio Factor Exposure and Market Impact", ""])
    lines.extend(["Evidence Ref: PORTFOLIO:FACTOR_IMPACT", ""])
    lines.extend(_render_portfolio_impact(portfolio_impact))
    lines.extend(["", "### Fundamental Evidence", ""])
    lines.extend(["Evidence Ref: FUNDAMENTAL:STATE", ""])
    lines.extend(_render_fundamental_state(fundamental_state))
    lines.extend(
        [
            "",
            "## 3. Changes Since Previous Report",
            "",
            "Evidence Ref: STATE:CHANGES",
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
    lines.extend(["", *_render_metric_definitions()])
    lines.extend(["", "Market Breadth:"])
    lines.extend(["Evidence Refs: BREADTH:MARKET, BREADTH:SECTOR_ROTATION"])
    lines.extend(_render_market_breadth(market_breadth))
    lines.extend(["", "News Entity Pipeline:", ""])
    lines.extend(_render_news_pipeline(news_quality, news_clusters, asset_events))
    lines.extend(
        [
            "",
            "## 5. Strategy Decision and Rules",
            "",
        ]
    )
    lines.extend(_render_action_readiness(strategy_decision))
    lines.extend(["", "Decision Context:", ""])
    lines.extend(_render_decision_context(decision_context))
    lines.extend(["", "Rule Evaluations:", ""])
    lines.extend(_render_triggered_rules(effective_rules))
    lines.extend(["", f"Market risk: {effective_risk.score}/100 ({effective_risk.level})"])
    lines.extend(f"- {reason}" for reason in effective_risk.explanations)
    lines.extend(_render_unusual_move_groups(effective_risk))
    lines.extend(
        [
            "",
            f"Portfolio exposure risk: "
            f"{effective_portfolio_decision_risk.exposure_risk.score}/100 "
            f"({effective_portfolio_decision_risk.exposure_risk.level})",
        ]
    )
    lines.extend(
        f"- {reason}"
        for reason in effective_portfolio_decision_risk.exposure_risk.explanations
    )
    lines.extend(
        [
            "",
            f"Portfolio data-quality risk: "
            f"{effective_portfolio_decision_risk.data_quality_risk.score}/100 "
            f"({effective_portfolio_decision_risk.data_quality_risk.level})",
            f"- Decision readiness: "
            f"{effective_portfolio_decision_risk.decision_readiness}.",
        ]
    )
    lines.extend(
        f"- {reason}"
        for reason in effective_portfolio_decision_risk.data_quality_risk.explanations
    )
    lines.extend(
        [
            "",
            "## 6. GPT Analysis Tasks",
            "",
        ]
    )
    if gpt_tasks:
        lines.extend(_render_gpt_tasks(gpt_tasks))
    else:
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
        lines.extend(["Evidence Ref: PORTFOLIO:FX", ""])
        lines.extend(_render_fx_conversions(portfolio_state.fx_conversions))
        lines.extend(["", "#### FX Cost vs Spot", ""])
        lines.extend(_render_fx_state(fx_state))
        lines.extend(["", "Conversion Detail", ""])
        lines.extend(_render_fx_costs(fx_costs or []))
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


def _render_executive_states(
    states: ReportUseStates,
    decision: StrategyDecisionState | None,
) -> list[str]:
    lines = [
        f"[STATE:MARKET] Market risk is {states.market.risk}; market regime is "
        f"{states.market.regime}; market analysis is "
        f"{states.market.actionability}.",
        "",
        f"[STATE:PORTFOLIO] Portfolio risk is {states.portfolio.risk}. "
        f"{states.portfolio.reason}",
        "",
        f"[STATE:NEWS] News quality is {states.news.quality}; news-based causal "
        f"analysis is {states.news.actionability}.",
    ]
    readiness = decision.action_readiness if decision is not None else None
    execution = decision.execution_readiness if decision is not None else None
    lines.extend([
        "",
        f"[STATE:ACTION] Action readiness is "
        f"{readiness.status if readiness is not None else 'blocked'}; "
        f"candidate is "
        f"{readiness.candidate_action if readiness and readiness.candidate_action else 'none'}; "
        "human approval is required.",
        "",
        f"[STATE:EXECUTION] Execution readiness is "
        f"{execution.status if execution is not None else 'blocked'}; "
        f"rule permission is "
        f"{execution.permission_status if execution is not None else 'denied'}; "
        f"proposed amount is "
        f"{_format_money(execution.proposed_amount, execution.currency or '') if execution else 'N/A'}; "
        "no execution is authorized.",
    ])
    return lines


def _render_data_quality_issues(
    data_coverage: DataCoverage | None,
    news_quality: NewsQualityGate | None,
    states: ReportUseStates,
) -> list[str]:
    capabilities = states.data_quality.capabilities if states.data_quality else None
    lines = [
        "Blocking is use-specific; a blocked portfolio or news module does not "
        "block market analysis.",
        "",
        "Overall: "
        + (states.data_quality.overall.status if states.data_quality else "unknown"),
        "",
    ]
    if capabilities is not None:
        lines.extend([
            "| Capability | Status | Reasons |",
            "|---|---|---|",
        ])
        for name, capability in (
            ("market_analysis", capabilities.market_analysis),
            ("macro_analysis", capabilities.macro_analysis),
            ("portfolio_analysis", capabilities.portfolio_analysis),
            ("investment_action", capabilities.investment_action),
            ("fx_analysis", capabilities.fx_analysis),
            ("news_analysis", capabilities.news_analysis),
            ("fundamental_analysis", capabilities.fundamental_analysis),
        ):
            lines.append(
                f"| {name} | {capability.status} | "
                f"{_escape_cell('; '.join(capability.reasons) or 'N/A')} |"
            )
        lines.extend(["",
        "| State Ref | Risk / Quality | Regime / Readiness | Actionability |",
        "|---|---|---|---|",
        f"| STATE:MARKET | {states.market.risk} | {states.market.regime} | "
        f"{states.market.actionability} |",
        f"| STATE:PORTFOLIO | {states.portfolio.risk} | "
        f"{states.portfolio.data_readiness} | "
        f"{states.portfolio.actionability} |",
        f"| STATE:NEWS | {states.news.quality} | N/A | "
        f"{states.news.actionability} |",
        "",
        ])
    lines.extend([
        "| Ref | Module | Item | Status | Latest | Detail |",
        "|---|---|---|---|---|---|",
    ])
    issue_count = 0
    if data_coverage is None:
        lines.append(
            "| DQ:MARKET | Data coverage | all | blocked | N/A | "
            "Diagnostics were not generated. |"
        )
        issue_count += 1
    else:
        for row in data_coverage.rows:
            if row.status == "available":
                continue
            lines.append(
                f"| {_data_quality_ref(row)} | {row.category} | {row.item} | "
                f"{row.status} | "
                f"{row.latest} | {_escape_cell(row.detail)} |"
            )
            issue_count += 1
    if news_quality is not None and news_quality.status in {
        "disabled",
        "data_quality_review",
    } and not any(row.category == "News" for row in (data_coverage.rows if data_coverage else [])):
        detail = "; ".join(news_quality.reasons) or "No detail supplied."
        lines.append(
            f"| DQ:NEWS | News | entity pipeline | blocked | N/A | "
            f"{_escape_cell(detail)} |"
        )
        issue_count += 1
    if issue_count == 0:
        return ["No missing, stale, insufficient, or blocked modules."]
    impacts = [
        impact for impact in (data_coverage.impacts if data_coverage else [])
        if "No data coverage gaps" not in impact
    ]
    if impacts:
        lines.extend(["", "Impact:"])
        lines.extend(f"- {impact}" for impact in impacts)
    return lines


def _render_portfolio_summary(
    summary: PortfolioSummary | None,
) -> list[str]:
    if summary is None:
        return ["Portfolio summary was not generated."]
    lines = [
        "### Invested Sleeve Allocation",
        "",
        f"Status: {_allocation_status(summary.invested_allocation)}",
        "",
        "Basis: supplied invested holding cost; this is not market value.",
        "",
        f"Total holding cost: {_format_money(summary.total_holding_cost, summary.base_currency)}",
        "",
        "| Asset | Supplied Cost | Invested Weight | Target Weight | Gap | Target Cost Gap |",
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
    lines.extend(["", "### Total Liquid Asset Allocation", ""])
    liquid_view = summary.liquid_asset_allocation
    if liquid_view is None:
        lines.append("Status: unavailable")
        lines.append("")
        lines.append("Reason: liquid_asset_allocation_not_generated")
    else:
        lines.extend([
            f"Status: {liquid_view.status}",
            "",
            f"Basis: {liquid_view.basis}; this is not market value.",
        ])
        if liquid_view.reason:
            lines.extend(["", f"Reason: {liquid_view.reason}"])
        lines.extend([
            "",
            f"Total liquid asset basis value: "
            f"{_format_money(liquid_view.total_value, summary.base_currency)}",
            "",
            "| Asset | Basis Value | Weight |",
            "|---|---:|---:|",
        ])
        if liquid_view.allocations:
            lines.extend(
                f"| {row.symbol} | "
                f"{_format_money(row.current_value, summary.base_currency)} | "
                f"{_format_percent(row.current_weight)} |"
                for row in liquid_view.allocations
            )
        else:
            lines.append("| None | N/A | N/A |")
    lines.extend(
        [
            "",
            f"Daily investment budget: "
            f"{_format_money(summary.daily_investment_budget, summary.daily_budget_currency or summary.base_currency)}",
            "",
            f"Target allocation tolerance: {_format_percent(summary.allocation_tolerance)}",
            "",
            f"USD cash: USD {summary.usd_cash:.2f}",
            "",
            f"Investment Cash: {_format_money(summary.investment_cash, summary.base_currency)}",
            "",
            f"Investment Source: {_format_money(summary.investment_source_cash, summary.base_currency)}",
            "",
            f"Reserved Cash: {_format_money(summary.reserved_cash, summary.base_currency)}",
            "",
            f"Emergency Cash: {_format_money(summary.emergency_cash, summary.base_currency)}",
            "",
            f"Unknown-Role Cash: {_format_money(summary.unknown_cash, summary.base_currency)}",
            "",
            f"Portfolio snapshot status: {summary.snapshot_status}",
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
    if summary.freshness is not None:
        lines.extend([
            "",
            "Portfolio freshness layers:",
            "",
            "| Layer | Status | Latest | Oldest | Maximum Age | Stale After |",
            "|---|---|---|---|---:|---:|",
        ])
        for name, layer in (
            ("holdings", summary.freshness.holdings),
            ("cash", summary.freshness.cash),
            ("fx_market", summary.freshness.fx_market),
        ):
            lines.append(
                f"| {name} | {layer.status} | "
                f"{layer.latest_date.isoformat() if layer.latest_date else 'N/A'} | "
                f"{layer.oldest_date.isoformat() if layer.oldest_date else 'N/A'} | "
                f"{layer.maximum_age_days if layer.maximum_age_days is not None else 'N/A'} | "
                f"{layer.stale_after_days} |"
            )
    if summary.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in summary.notes)
    return lines


def _render_key_evidence(evidence: list[MarketEvidence]) -> list[str]:
    if not evidence:
        return ["No key market evidence available."]
    lines = [
        "| Ref | Asset / Macro | Latest | 1D | 5D | 20D | Medium-Term Trend | 50D | 200D | 50DMA Slope 20D | Drawdown from 252D High | Absolute-Move z-score 60D | ATR | Absolute-Move Percentile 252D | Short-Term State | Detection Reason |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in evidence:
        lines.append(
            f"| {row.evidence_ref} | {row.symbol} | {_format_decimal_or_na(row.latest)} | "
            f"{_format_percent(row.return_1d)} | {_format_percent(row.return_5d)} | "
            f"{_format_percent(row.return_20d)} | {row.medium_term_trend} | "
            f"{_format_decimal_or_na(row.sma_50)} | {_format_decimal_or_na(row.sma_200)} | "
            f"{_format_percent(row.sma_50_slope_20d)} | "
            f"{_format_percent(row.drawdown_from_252d_high)} | "
            f"{_format_decimal_or_na(row.absolute_move_z_score_60d)} | "
            f"{_format_multiple(row.atr_multiple)} | "
            f"{_format_percent(row.absolute_move_percentile_252d)} | "
            f"{row.short_term_state} | {_escape_cell(row.detection_reason)} |"
        )
    return lines


def _render_fundamental_state(
    state: FundamentalEvidenceState | None,
) -> list[str]:
    if state is None:
        return ["Status: blocked", "- Reason: fundamental state was not evaluated."]
    lines = [
        f"Valuation status: {state.valuation_status}",
        f"Earnings revision status: {state.earnings_revision_status}",
        "",
        "Valuation observations:",
        "",
        "| Symbol | As Of | Metric | Value | Currency | Period | Source |",
        "|---|---|---|---:|---|---|---|",
    ]
    if state.valuations:
        lines.extend(
            f"| {item.symbol} | {item.as_of_date.isoformat()} | {item.metric} | "
            f"{item.value:.4f} | {item.currency or 'N/A'} | "
            f"{item.period or 'N/A'} | {item.source} |"
            for item in state.valuations
        )
    else:
        lines.append("| None | N/A | N/A | N/A | N/A | N/A | N/A |")
    lines.extend([
        "",
        "Earnings estimate revisions:",
        "",
        "| Symbol | Fiscal Period | Metric | Previous | Current | Change | Direction | Material | Source |",
        "|---|---|---|---:|---:|---:|---|---|---|",
    ])
    if state.revisions:
        lines.extend(
            f"| {item.symbol} | {item.fiscal_period} | {item.metric} | "
            f"{item.previous_value:.4f} ({item.previous_date.isoformat()}) | "
            f"{item.current_value:.4f} ({item.current_date.isoformat()}) | "
            f"{_format_percent(item.change_pct)} | {item.direction} | "
            f"{'yes' if item.material else 'no' if item.material is False else 'N/A'} | "
            f"{item.source} |"
            for item in state.revisions
        )
    else:
        lines.append("| None | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
    lines.extend(f"- Reason: {reason}" for reason in state.reasons)
    return lines


def _render_news_pipeline(
    quality: NewsQualityGate | None,
    clusters: list[NewsCluster] | None,
    events: list[AssetEvent] | None,
) -> list[str]:
    lines = [
        "Evidence Ref: NEWS:ENTITY_PIPELINE",
        f"- Status: {quality.status if quality else 'blocked'}",
        f"- Entity precision: "
        f"{_format_percent(quality.entity_precision if quality else None)}",
    ]
    if quality:
        lines.extend(f"- Reason: {reason}" for reason in quality.reasons)
    lines.extend([
        f"- News clusters: {len(clusters or [])}",
        f"- Deduplicated asset events: {len(events or [])}",
    ])
    for event in events or []:
        lines.append(
            f"- {event.related_symbol} / {event.event_type} / "
            f"{event.event_date}: {event.headline} "
            f"({event.article_count} article(s))."
        )
    return lines


def _render_portfolio_impact(
    analysis: PortfolioImpactAnalysis | None,
) -> list[str]:
    if analysis is None:
        return ["Status: blocked", "- Reason: portfolio impact was not evaluated."]
    lines = [
        f"Factor exposure status: {analysis.factors.status}",
        f"- Mapped invested weight: {_format_percent(analysis.factors.mapped_weight)}",
        "- Unmapped invested symbols: "
        + (", ".join(analysis.factors.unmapped_symbols) or "none"),
    ]
    lines.extend(f"- Factor reason: {reason}" for reason in analysis.factors.reasons)
    lines.extend([
        "",
        "| Factor | Exposure | Symbols | Basis |",
        "|---|---:|---|---|",
    ])
    if analysis.factors.exposures:
        lines.extend(
            f"| {item.factor_id} | {_format_percent(item.weight)} | "
            f"{_escape_cell(', '.join(item.symbols) or 'None')} | "
            f"{item.basis} |"
            for item in analysis.factors.exposures
        )
    else:
        lines.append("| None | N/A | N/A | N/A |")
    lines.extend([
        "",
        f"Portfolio impact status: {analysis.impact.status}",
        f"- Dominant factor: {analysis.impact.dominant_factor_id or 'N/A'}",
        f"- Dominant impact score: "
        f"{analysis.impact.dominant_impact_score if analysis.impact.dominant_impact_score is not None else 'N/A'} "
        f"({analysis.impact.level})",
    ])
    lines.extend(f"- Impact reason: {reason}" for reason in analysis.impact.reasons)
    lines.extend([
        "",
        "| Factor | Exposure | Market Risk Points | Impact Score | Level | Drivers | Evidence |",
        "|---|---:|---:|---:|---|---|---|",
    ])
    if analysis.impact.items:
        lines.extend(
            f"| {item.factor_id} | {_format_percent(item.exposure_weight)} | "
            f"{item.market_risk_points} | {item.impact_score} | {item.level} | "
            f"{_escape_cell('; '.join(item.drivers) or 'none')} | "
            f"{_escape_cell(', '.join(item.evidence_refs) or 'N/A')} |"
            for item in analysis.impact.items
        )
    else:
        lines.append("| None | N/A | N/A | N/A | N/A | N/A | N/A |")
    lines.extend([
        "",
        "Factor exposure uses configured tags over supplied holding cost; it is "
        "not regression beta or market-value exposure. Impact Score is a "
        "screening score, not an expected gain or loss.",
    ])
    return lines


def _render_decision_context(context: DecisionContext | None) -> list[str]:
    if context is None:
        return ["- Status: blocked", "- Reason: context was not generated."]
    lines = [
        "Evidence Ref: STATE:DECISION_CONTEXT",
        "",
        f"- Status: {context.status}",
        f"- Transition: {context.transition}",
        f"- Previous journal date: "
        f"{context.previous_report_date.isoformat() if context.previous_report_date else 'N/A'}",
        f"- Market risk: {context.market_risk_score}/100 "
        f"({context.market_risk_level})",
        f"- Dominant portfolio factor: {context.dominant_factor_id or 'N/A'}",
        f"- Dominant factor impact: "
        f"{context.dominant_impact_score if context.dominant_impact_score is not None else 'N/A'}",
        f"- Target allocation configured: "
        f"{'yes' if context.target_allocation else 'no'}",
        f"- Daily budget: "
        f"{_format_money(context.daily_budget_amount, context.daily_budget_currency or '')}",
        f"- Available investment cash: "
        f"{_format_money(context.available_investment_cash, context.daily_budget_currency or '')}",
        f"- Candidate: {context.candidate_action or 'none'} / "
        f"{context.candidate_symbol or 'N/A'}",
        f"- Action → execution: {context.action_readiness_status} → "
        f"{context.execution_readiness_status}",
        f"- Permission: {context.permission_status}",
    ]
    lines.extend(f"- Context reason: {reason}" for reason in context.reasons)
    lines.append("- Evidence refs: " + ", ".join(context.evidence_refs))
    return lines


def _render_metric_definitions() -> list[str]:
    return [
        "Trend Model:",
        "- Medium-term inputs: close versus 50DMA, close versus 200DMA, and "
        "the 20-session change in 50DMA as supporting slope evidence.",
        "- medium_term_uptrend: close is above both 50DMA and 200DMA.",
        "- medium_term_downtrend: close is below both 50DMA and 200DMA.",
        "- mixed: all other combinations.",
        "- insufficient: either 50DMA or 200DMA is unavailable.",
        "",
        "Metric Definitions:",
        "- absolute_move_z_score_60d: latest absolute 1D return minus the mean "
        "absolute 1D return "
        "over the prior observations in a 60-session lookback, divided by the "
        "standard deviation of those prior signed daily returns.",
        "- ATR multiple: absolute latest close-to-close move divided by 20-day "
        "average true range.",
        "- absolute_move_percentile_252d: rank of the latest absolute 1D return "
        "against up to 252 "
        "prior absolute daily returns; 95% means the move is at least as large "
        "as 95% of the comparison history.",
        "- drawdown_from_252d_high: latest close divided by the highest close "
        "in the latest 252 sessions, minus one.",
    ]


def _render_triggered_rules(
    rules: list[StrategyRuleResult],
) -> list[str]:
    if not rules:
        return ["No strategy rule is triggered or near its threshold."]
    lines = [
        "| Rule ID / Name | Symbol | Action | Status | Blocking | Observed | Threshold | Absolute-Move z-score 60D | ATR | Absolute-Move Percentile 252D | Evidence Refs | Detection Reason |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for rule in rules:
        lines.append(
            f"| {rule.rule_id or rule.name} | {rule.symbol or 'N/A'} | "
            f"{rule.action or 'monitor'} | {rule.status} | "
            f"{'yes' if rule.blocking else 'no'} | "
            f"{_escape_cell(rule.observed)} | "
            f"{_escape_cell(rule.threshold)} | "
            f"{_format_decimal_or_na(rule.absolute_move_z_score_60d)} | "
            f"{_format_multiple(rule.atr_multiple)} | "
            f"{_format_percent(rule.absolute_move_percentile_252d)} | "
            f"{_escape_cell(', '.join(rule.evidence_refs) or 'N/A')} | "
            f"{_escape_cell(rule.reason)} |"
        )
    return lines


def _render_action_readiness(
    decision: StrategyDecisionState | None,
) -> list[str]:
    if decision is None:
        return [
            "Action Readiness: blocked",
            "- Reason: strategy decision was not evaluated.",
            "- Human approval required: yes.",
        ]
    readiness = decision.action_readiness
    execution = decision.execution_readiness
    lines = [
        "Evidence Ref: STATE:ACTION_READINESS",
        "",
        f"Action Readiness: {readiness.status}",
        f"- Candidate action: {readiness.candidate_action or 'none'}",
        f"- Symbol: {readiness.symbol or 'N/A'}",
        f"- Triggering rule: {readiness.rule_id or 'N/A'}",
        "- Human approval required: yes.",
        "",
        "Evidence Ref: STATE:EXECUTION_READINESS",
        "",
        f"Execution Readiness: {execution.status}",
        f"- Rule execution permission: {execution.permission_status}",
        f"- Proposed amount: {_format_money(execution.proposed_amount, execution.currency or '')}",
        f"- Sizing method: {execution.sizing_method or 'N/A'}",
        "- Execution authorized: no.",
    ]
    lines.extend(f"- Reason: {reason}" for reason in readiness.reasons)
    if readiness.evidence_refs:
        lines.append(
            "- Evidence refs: " + ", ".join(readiness.evidence_refs)
        )
    lines.extend(f"- Execution reason: {reason}" for reason in execution.reasons)
    return lines


def _render_market_breadth(breadth: MarketBreadth | None) -> list[str]:
    if breadth is None:
        return ["- Not generated."]
    return [
        f"- Tracked universe: {breadth.tracked_count} assets.",
        f"- Above 50D: {breadth.above_50d_count} "
        f"({_format_percent(breadth.above_50d_share)} of eligible assets).",
        f"- Above 200D: {breadth.above_200d_count} "
        f"({_format_percent(breadth.above_200d_share)} of eligible assets).",
        f"- RSP vs SPY 20D: {_format_percent(breadth.rsp_vs_spy_20d)}.",
        f"- VIX: {_format_decimal_or_na(breadth.vix_level)}; "
        f"252D level percentile "
        f"{_format_percent(breadth.vix_level_percentile_252d)}.",
        "- Breadth covers the configured tracked universe, not the full NYSE/Nasdaq.",
    ]


def _render_gpt_tasks(tasks: list[GptAnalysisTask]) -> list[str]:
    lines: list[str] = []
    for index, task in enumerate(tasks, 1):
        lines.extend([
            f"### Task {index}",
            "",
            f"ID: {task.task_id}",
            "",
            f"Question: {task.question}",
            "",
            f"Status: {task.status}",
            "",
            "Evidence Refs: "
            + (", ".join(task.evidence_refs) if task.evidence_refs else "N/A"),
            "",
            f"Expected Output: {task.expected_output}",
            "",
            f"Confidence Requirement: {task.confidence_requirement}",
            "",
        ])
        if task.blocked_reasons:
            lines.extend(["Blocked Reasons:"])
            lines.extend(f"- {reason}" for reason in task.blocked_reasons)
            lines.append("")
    return lines


def _render_unusual_move_groups(risk: RiskAssessment) -> list[str]:
    lines: list[str] = []
    if risk.single_asset_alerts:
        lines.extend(["", "Single-asset alerts:"])
        lines.extend(
            f"- {item.symbol} ({item.category}): {item.points} points; "
            f"{item.evidence_ref}."
            for item in risk.single_asset_alerts
        )
    if risk.clusters:
        lines.extend(["", "Correlated clusters:"])
        lines.extend(
            f"- {item.cluster}: {', '.join(item.symbols)}; {item.points} points."
            for item in risk.clusters
        )
    return lines


def _render_fx_costs(costs: list[FxCostComparison]) -> list[str]:
    if not costs:
        return ["No comparable CNY/USD FX conversions."]
    lines = [
        "| Date | Pair | Effective | All-In | USD/CNH Spot | Spot Premium | Benchmark |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in costs:
        lines.append(
            f"| {item.fx_date.isoformat()} | {item.pair} | "
            f"{item.effective_rate:.4f} | {item.all_in_rate:.4f} | "
            f"{_format_decimal_or_na(item.spot_rate)} | "
            f"{_format_percent(item.spot_premium)} | "
            f"{_escape_cell(item.benchmark_note)} |"
        )
    return lines


def _render_fx_state(state: FxState | None) -> list[str]:
    if state is None:
        return ["FX state was not generated."]
    lines = [
        f"Status: {state.status}",
        f"- USD investment cash balance: USD {state.usd_balance:.2f}",
        f"- USD required daily: {_format_money(state.usd_required_daily, 'USD')}",
        (
            "- Coverage days: N/A"
            if state.coverage_days is None
            else f"- Coverage days: {state.coverage_days:.1f}"
        ),
        f"- Coverage status: {state.coverage_status}",
        f"- USD/CNH spot: {_format_decimal_or_na(state.spot_usd_cnh)}",
        f"- Weighted all-in cost basis: {_format_decimal_or_na(state.cost_basis)}",
        f"- Spot versus cost basis: {_format_percent(state.difference_pct)}",
    ]
    lines.extend(f"- Reason: {reason}" for reason in state.reasons)
    return lines


def _render_full_price_evidence(
    price_signals: dict[str, PriceSignal],
) -> list[str]:
    lines = [
        "| Asset | Latest | Latest Date | 1D | 5D | 20D | 50D | 200D | 50DMA Slope 20D | Drawdown from 252D High | Absolute-Move z-score 60D | ATR | Absolute-Move Percentile 252D | Detection Reason |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not price_signals:
        lines.append("| None | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | No price signals. |")
        return lines
    for symbol in sorted(price_signals):
        signal = price_signals[symbol]
        lines.append(
            f"| {symbol} | {_format_decimal_or_na(signal.latest)} | "
            f"{signal.latest_date.isoformat() if signal.latest_date else 'N/A'} | "
            f"{_format_percent(signal.return_1d)} | "
            f"{_format_percent(signal.return_5d)} | "
            f"{_format_percent(signal.return_20d)} | "
            f"{_format_decimal_or_na(signal.sma_50)} | "
            f"{_format_decimal_or_na(signal.sma_200)} | "
            f"{_format_percent(signal.sma_50_slope_20d)} | "
            f"{_format_percent(signal.drawdown_from_252d_high)} | "
            f"{_format_decimal_or_na(signal.absolute_move_z_score_60d)} | "
            f"{_format_multiple(signal.atr_multiple)} | "
            f"{_format_percent(signal.absolute_move_percentile_252d)} | "
            f"{_escape_cell(signal.reason or 'No detector threshold crossed.')} |"
        )
    return lines


def _render_cash_positions(cash_positions: list[CashPosition]) -> list[str]:
    if not cash_positions:
        return ["No cash positions supplied."]
    lines = [
        "| Institution | Account | Currency | Balance | Cash Role | As Of |",
        "|---|---|---|---:|---|---|",
    ]
    for position in cash_positions:
        lines.append(
            f"| {_escape_cell(position.institution)} | "
            f"{_escape_cell(position.account_label)} | {position.currency} | "
            f"{_format_decimal_compact(position.balance)} | {position.cash_role} | "
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


def _format_multiple(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}x"


def _format_money(value: float | None, currency: str) -> str:
    return "N/A" if value is None else f"{currency} {value:.2f}"


def _allocation_status(view: PortfolioAllocationView | None) -> str:
    return view.status if view is not None else "available"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _format_list(values: list[str]) -> str:
    if not values:
        return "None"
    return ", ".join(values)


def _data_quality_ref(row: DataCoverageRow) -> str:
    if row.category == "News":
        return "DQ:NEWS"
    if row.category == "Portfolio":
        suffix = (
            "SNAPSHOT"
            if row.item == "cash and holdings"
            else "CASH_ROLES"
            if row.item == "cash roles"
            else "STATE"
        )
        return f"DQ:PORTFOLIO:{suffix}"
    return "DQ:MARKET"


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
        return ["Macro context was not generated."]

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
