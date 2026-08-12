from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json

from app.config import ReportProfile
from app.models.analysis import (
    CapabilityState,
    DataCoverage,
    DataCoverageRow,
    DataQualityState,
    DecisionContext,
    FxCostComparison,
    FxState,
    FreshnessLayer,
    FundamentalEvidenceState,
    GptAnalysisTask,
    MarketBreadth,
    MarketEvidence,
    MarketState,
    MacroContext,
    NewsQualityGate,
    NewsState,
    PortfolioAllocation,
    PortfolioAllocationView,
    PortfolioFreshness,
    PortfolioImpactAnalysis,
    PortfolioDecisionState,
    PortfolioRiskAssessment,
    PortfolioSummary,
    PriceSignal,
    ReportCapabilities,
    ReportState,
    ReportUseStates,
    RiskAssessment,
    RiskAssetAlert,
    RiskClusterAssessment,
    SectorRotation,
    StrategyRuleResult,
    StrategyDecisionState,
)
from app.models.price import PriceBar
from app.steward.models import PortfolioReportState


REPORT_STATE_PREFIX = "<!-- report-state: "
REPORT_STATE_SUFFIX = " -->"
KEY_EVIDENCE_LIMIT = 10
PORTFOLIO_STALE_DAYS = 3
FX_MARKET_STALE_DAYS = 1

RISK_CLUSTERS = {
    "broad_equity_growth": {"SPY", "QQQ"},
    "sector_style": {
        "RSP", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU",
        "XLI", "XLC", "XLRE", "SOXX", "SMH",
    },
    "mega_cap_companies": {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    },
    "rates_duration": {"^TNX", "TLT", "BIL"},
    "credit": {"HYG", "LQD"},
    "usd_cnh": {"DX-Y.NYB", "UUP", "USD/CNH"},
    "gold": {"GLD"},
    "crypto": {"BTC-USD"},
}
_CORE_EVIDENCE = [
    "SPY", "QQQ", "RSP", "^VIX", "^TNX", "DX-Y.NYB", "USD/CNH",
    "GLD", "TLT", "HYG",
]


def analyze_portfolio_summary(
    portfolio_state: PortfolioReportState | None,
    profile: ReportProfile,
    price_signals: dict[str, PriceSignal],
    report_date: date | None = None,
) -> PortfolioSummary:
    if portfolio_state is None:
        unavailable_freshness = PortfolioFreshness(
            _freshness_layer([], report_date, PORTFOLIO_STALE_DAYS, "holdings"),
            _freshness_layer([], report_date, PORTFOLIO_STALE_DAYS, "cash"),
            _freshness_layer([], report_date, FX_MARKET_STALE_DAYS, "fx_market"),
        )
        unavailable_view = PortfolioAllocationView(
            status="unavailable",
            basis="supplied_holding_cost_plus_cash_balance",
            total_value=None,
            allocations=[],
            reason="portfolio_state_not_supplied",
        )
        return PortfolioSummary(
            base_currency=profile.base_currency,
            total_holding_cost=None,
            allocations=[],
            daily_investment_budget=profile.daily_investment_budget,
            usd_cash=0.0,
            usd_daily_spend=profile.usd_daily_spend,
            usd_coverage_days=None,
            snapshot_status="unavailable",
            notes=["No portfolio state was supplied."],
            invested_allocation=PortfolioAllocationView(
                status="unavailable",
                basis="supplied_invested_holding_cost",
                total_value=None,
                allocations=[],
                reason="portfolio_state_not_supplied",
            ),
            liquid_asset_allocation=unavailable_view,
            freshness=unavailable_freshness,
            allocation_tolerance=profile.target_allocation.tolerance,
            daily_budget_currency=profile.daily_budget.currency,
            daily_investment_budgets={
                budget.currency: budget.amount for budget in profile.daily_budgets
            },
        )

    fx_rates = _fx_rates(portfolio_state, profile.base_currency, price_signals)
    values: dict[str, float] = {}
    omitted_holdings: list[str] = []
    notes = [
        "Invested Sleeve Allocation is the share of supplied invested holding "
        "cost; it is not an allocation of total liquid assets."
    ]
    for holding in portfolio_state.holdings:
        rate = fx_rates.get(holding.currency)
        if rate is None:
            omitted_holdings.append(holding.symbol)
            notes.append(
                f"{holding.symbol} omitted: no {holding.currency}/"
                f"{profile.base_currency} conversion rate."
            )
            continue
        values[holding.symbol] = values.get(holding.symbol, 0.0) + (
            float(holding.total_cost) * rate
        )

    total = sum(values.values())
    allocations = _allocations(values, total, profile.target_allocations)
    cash_by_role = {
        "investment_cash": 0.0,
        "investment_source": 0.0,
        "reserved": 0.0,
        "emergency": 0.0,
        "unknown": 0.0,
    }
    missing_cash_fx: list[str] = []
    for position in portfolio_state.cash_positions:
        rate = fx_rates.get(position.currency)
        if rate is not None:
            cash_by_role[position.cash_role] += float(position.balance) * rate
        else:
            missing_cash_fx.append(
                f"{position.institution}/{position.account_label}:{position.currency}"
            )

    usd_cash = sum(
        float(position.balance)
        for position in portfolio_state.cash_positions
        if position.currency == "USD"
        and position.cash_role == "investment_cash"
    )
    coverage = (
        usd_cash / profile.usd_daily_spend
        if profile.usd_daily_spend and profile.usd_daily_spend > 0
        else None
    )
    freshness = _portfolio_freshness(
        portfolio_state, price_signals.get("USD/CNH"), report_date
    )
    snapshot_status = _combined_portfolio_freshness(freshness)
    if not profile.target_allocations:
        notes.append("Target allocations are not configured.")
    elif profile.target_allocation.tolerance is None:
        notes.append("Target allocation tolerance is not configured.")
    if not any(budget.amount is not None for budget in profile.daily_budgets):
        notes.append("Daily investment budget is not configured.")
    if cash_by_role["unknown"]:
        notes.append("Unknown-role cash is excluded from investment cash.")
    invested_view = PortfolioAllocationView(
        status="degraded" if omitted_holdings else "available",
        basis="supplied_invested_holding_cost",
        total_value=total,
        allocations=allocations,
        reason=(
            "holding_fx_conversion_missing"
            if omitted_holdings
            else ""
        ),
    )
    liquid_symbols = sorted(
        {holding.symbol for holding in portfolio_state.holdings} | {"Cash"}
    )
    has_unknown_role = any(
        position.cash_role == "unknown"
        for position in portfolio_state.cash_positions
    )
    liquid_unavailable_reasons: list[str] = []
    if not portfolio_state.cash_positions:
        liquid_unavailable_reasons.append("cash_positions_not_supplied")
    if has_unknown_role:
        liquid_unavailable_reasons.append("cash_role_not_configured")
    if omitted_holdings or missing_cash_fx:
        liquid_unavailable_reasons.append("fx_conversion_missing")
    if liquid_unavailable_reasons:
        liquid_view = PortfolioAllocationView(
            status="unavailable",
            basis="supplied_holding_cost_plus_cash_balance",
            total_value=None,
            allocations=[
                PortfolioAllocation(symbol, None, None, None, None, None)
                for symbol in liquid_symbols
            ],
            reason=",".join(_deduplicate(liquid_unavailable_reasons)),
        )
    else:
        liquid_values = dict(values)
        liquid_values["Cash"] = sum(cash_by_role.values())
        liquid_total = sum(liquid_values.values())
        liquid_view = PortfolioAllocationView(
            status="available",
            basis="supplied_holding_cost_plus_cash_balance",
            total_value=liquid_total,
            allocations=_allocations(liquid_values, liquid_total, {}),
        )
    return PortfolioSummary(
        base_currency=profile.base_currency,
        total_holding_cost=total,
        allocations=allocations,
        daily_investment_budget=profile.daily_investment_budget,
        usd_cash=usd_cash,
        usd_daily_spend=profile.usd_daily_spend,
        usd_coverage_days=coverage,
        investment_cash=cash_by_role["investment_cash"],
        investment_source_cash=cash_by_role["investment_source"],
        reserved_cash=cash_by_role["reserved"],
        emergency_cash=cash_by_role["emergency"],
        unknown_cash=cash_by_role["unknown"],
        snapshot_status=snapshot_status,
        notes=_deduplicate(notes),
        invested_allocation=invested_view,
        liquid_asset_allocation=liquid_view,
        freshness=freshness,
        allocation_tolerance=profile.target_allocation.tolerance,
        daily_budget_currency=profile.daily_budget.currency,
        daily_investment_budgets={
            budget.currency: budget.amount for budget in profile.daily_budgets
        },
    )


def combine_data_quality(
    market_coverage: DataCoverage,
    news_quality: NewsQualityGate | None,
    portfolio_state: PortfolioReportState | None,
    report_date: date,
    fundamental_state: FundamentalEvidenceState | None = None,
) -> DataCoverage:
    rows = list(market_coverage.rows)
    price_rows = [row for row in rows if row.category == "Prices"]
    below_200 = [row for row in price_rows if row.rows < 200]
    if below_200:
        rows.append(
            DataCoverageRow(
                "Technical",
                "50D/200D trend coverage",
                "insufficient",
                len(price_rows) - len(below_200),
                "N/A",
                (
                    f"{len(below_200)} configured "
                    f"{'asset has' if len(below_200) == 1 else 'assets have'} "
                    "fewer than 200 rows."
                ),
            )
        )
    if news_quality and news_quality.status in {"disabled", "data_quality_review"}:
        rows.append(
            DataCoverageRow(
                "News",
                "entity pipeline",
                "blocked",
                0,
                "N/A",
                "; ".join(news_quality.reasons) or "News pipeline is blocked.",
            )
        )
    if fundamental_state is not None:
        rows.extend(
            [
                DataCoverageRow(
                    "Fundamentals",
                    "valuation observations",
                    fundamental_state.valuation_status,
                    len(fundamental_state.valuations),
                    max(
                        (item.as_of_date for item in fundamental_state.valuations),
                        default=None,
                    ).isoformat()
                    if fundamental_state.valuations
                    else "N/A",
                    "; ".join(fundamental_state.reasons) or "Available.",
                ),
                DataCoverageRow(
                    "Fundamentals",
                    "earnings revisions",
                    fundamental_state.earnings_revision_status,
                    len(fundamental_state.revisions),
                    max(
                        (item.current_date for item in fundamental_state.revisions),
                        default=None,
                    ).isoformat()
                    if fundamental_state.revisions
                    else "N/A",
                    "; ".join(fundamental_state.reasons) or "Available.",
                ),
            ]
        )
    if portfolio_state is None:
        rows.append(
            DataCoverageRow(
                "Portfolio", "state", "blocked", 0, "N/A",
                "Portfolio state was not supplied.",
            )
        )
    else:
        snapshot_dates = [
            item.as_of_date
            for item in [
                *portfolio_state.cash_positions,
                *portfolio_state.holdings,
            ]
        ]
        rows.append(
            DataCoverageRow(
                "Portfolio",
                "cash and holdings",
                _portfolio_snapshot_status(portfolio_state, report_date),
                len(snapshot_dates),
                max(snapshot_dates).isoformat() if snapshot_dates else "N/A",
                "Compatibility aggregate; use the holdings and cash rows for "
                "layer-specific freshness.",
            )
        )
        for item, dates in (
            ("holdings", [row.as_of_date for row in portfolio_state.holdings]),
            ("cash", [row.as_of_date for row in portfolio_state.cash_positions]),
        ):
            freshness = _freshness_layer(
                dates, report_date, PORTFOLIO_STALE_DAYS, item
            )
            rows.append(
                DataCoverageRow(
                    "Portfolio",
                    item,
                    freshness.status,
                    len(dates),
                    freshness.latest_date.isoformat()
                    if freshness.latest_date else "N/A",
                    f"{item.title()} snapshots older than "
                    f"{PORTFOLIO_STALE_DAYS} days are stale.",
                )
            )
        unknown_roles = sum(
            position.cash_role == "unknown"
            for position in portfolio_state.cash_positions
        )
        if unknown_roles:
            rows.append(
                DataCoverageRow(
                    "Portfolio",
                    "cash roles",
                    "degraded",
                    unknown_roles,
                    "N/A",
                    f"{unknown_roles} cash positions have an unknown role.",
                )
            )
    status = _overall_quality_status(rows)
    impacts = [
        impact
        for impact in market_coverage.impacts
        if "No data coverage gaps" not in impact
    ]
    return DataCoverage(rows=rows, impacts=_deduplicate(impacts), status=status)


def select_key_market_evidence(
    price_signals: dict[str, PriceSignal],
) -> list[MarketEvidence]:
    selected = [symbol for symbol in _CORE_EVIDENCE if symbol in price_signals]
    remaining = sorted(
        (
            signal for symbol, signal in price_signals.items()
            if symbol not in selected
        ),
        key=lambda signal: (
            signal.is_unusual_move,
            _signal_severity(signal),
        ),
        reverse=True,
    )
    selected.extend(
        signal.symbol
        for signal in remaining[: max(0, KEY_EVIDENCE_LIMIT - len(selected))]
    )
    return [_market_evidence(price_signals[symbol]) for symbol in selected]


def analyze_market_breadth(
    signals: dict[str, PriceSignal],
    history: dict[str, list[PriceBar]],
) -> MarketBreadth:
    tracked = [
        signal for symbol, signal in signals.items()
        if not symbol.startswith("^") and symbol not in {"USD/CNH", "DX-Y.NYB"}
    ]
    above_50 = sum(
        signal.latest is not None
        and signal.sma_50 is not None
        and signal.latest > signal.sma_50
        for signal in tracked
    )
    above_200 = sum(
        signal.latest is not None
        and signal.sma_200 is not None
        and signal.latest > signal.sma_200
        for signal in tracked
    )
    eligible_50 = sum(signal.sma_50 is not None for signal in tracked)
    eligible_200 = sum(signal.sma_200 is not None for signal in tracked)
    rsp = signals.get("RSP")
    spy = signals.get("SPY")
    vix = signals.get("^VIX")
    return MarketBreadth(
        tracked_count=len(tracked),
        above_50d_count=above_50,
        above_200d_count=above_200,
        above_50d_share=above_50 / eligible_50 if eligible_50 else None,
        above_200d_share=above_200 / eligible_200 if eligible_200 else None,
        rsp_vs_spy_20d=(
            rsp.return_20d - spy.return_20d
            if rsp and spy
            and rsp.return_20d is not None
            and spy.return_20d is not None
            else None
        ),
        vix_level=vix.latest if vix else None,
        vix_percentile=_level_percentile(history.get("^VIX", [])),
    )


def assess_market_risk(
    price_signals: dict[str, PriceSignal],
    breadth: MarketBreadth,
) -> RiskAssessment:
    cluster_results: list[RiskClusterAssessment] = []
    single_asset_alerts: list[RiskAssetAlert] = []
    for cluster, symbols in RISK_CLUSTERS.items():
        triggered = [
            signal for symbol, signal in price_signals.items()
            if symbol in symbols and signal.is_unusual_move
        ]
        if not triggered:
            continue
        severity = max(_signal_severity(signal) for signal in triggered)
        points = min(10, max(1, round(severity * 5)))
        if len(triggered) >= 2:
            downside_count = sum(
                signal.return_1d is not None and signal.return_1d < 0
                for signal in triggered
            )
            cluster_results.append(
                RiskClusterAssessment(
                    cluster=cluster,
                    symbols=tuple(sorted(signal.symbol for signal in triggered)),
                    severity=severity,
                    points=points if downside_count >= 2 else 0,
                    evidence_refs=tuple(
                        sorted(_evidence_ref(signal) for signal in triggered)
                    ),
                )
            )
        else:
            signal = triggered[0]
            single_asset_alerts.append(
                RiskAssetAlert(
                    symbol=signal.symbol,
                    category=cluster,
                    severity=severity,
                    points=0,
                    evidence_ref=_evidence_ref(signal),
                )
            )
    downside_cluster_points = sum(item.points for item in cluster_results)
    breadth_points = 0
    if breadth.above_50d_share is not None:
        breadth_points += round(max(0.0, 0.5 - breadth.above_50d_share) * 20)
    if breadth.above_200d_share is not None:
        breadth_points += round(max(0.0, 0.5 - breadth.above_200d_share) * 20)
    breadth_points = min(15, breadth_points)
    vix_points = 0
    if breadth.vix_level is not None:
        vix_points = 15 if breadth.vix_level >= 30 else 8 if breadth.vix_level >= 20 else 0
    if (
        breadth.vix_level_percentile_252d is not None
        and breadth.vix_level_percentile_252d >= 0.90
    ):
        vix_points = max(vix_points, 12)
    score = min(100, downside_cluster_points + breadth_points + vix_points)
    explanations = [
        f"Abnormal-move alerts: {len(single_asset_alerts)} single-asset alerts and "
        f"{len(cluster_results)} correlated clusters; alerts are informational "
        "and do not add downside-risk points.",
        f"Correlated downside clusters: {downside_cluster_points} points.",
        f"Tracked-universe breadth: {breadth_points} points.",
        f"VIX level/252D level percentile: {vix_points} points.",
        f"Total market downside risk: {score}/100.",
    ]
    return RiskAssessment(
        score=score,
        level=_risk_level(score),
        explanations=explanations,
        scope="market_downside",
        clusters=cluster_results,
        single_asset_alerts=single_asset_alerts,
        components={
            "downside_clusters": downside_cluster_points,
            "breadth": breadth_points,
            "volatility": vix_points,
        },
    )


def assess_portfolio_decision_risk(
    summary: PortfolioSummary,
) -> PortfolioRiskAssessment:
    gaps = [
        abs(item.weight_gap)
        for item in summary.allocations
        if item.weight_gap is not None
    ]
    max_gap = max(gaps, default=0.0)
    gap_points = min(30, round(max_gap * 200))
    max_weight = max(
        (item.current_weight or 0.0 for item in summary.allocations),
        default=0.0,
    )
    concentration_points = min(15, round(max(0.0, max_weight - 0.5) * 50))
    stale_points = (
        40
        if summary.snapshot_status == "unavailable"
        else 25
        if summary.snapshot_status == "stale"
        else 0
    )
    unknown_role_points = 20 if (summary.unknown_cash or 0) > 0 else 0
    coverage_points = (
        15
        if summary.usd_coverage_days is not None
        and summary.usd_coverage_days < 90
        else 8
        if summary.usd_coverage_days is not None
        and summary.usd_coverage_days < 120
        else 0
    )
    exposure_score = min(
        100, gap_points + concentration_points + coverage_points
    )
    data_quality_score = min(100, stale_points + unknown_role_points)
    readiness_reasons: list[str] = []
    if summary.freshness is not None:
        for name, layer in (
            ("holding", summary.freshness.holdings),
            ("cash", summary.freshness.cash),
        ):
            if layer.status in {"stale", "unavailable"}:
                readiness_reasons.append(
                    f"{name} snapshots are {layer.status}"
                )
    elif summary.snapshot_status in {"stale", "unavailable"}:
        readiness_reasons.append(f"portfolio snapshots are {summary.snapshot_status}")
    if (summary.unknown_cash or 0) > 0:
        readiness_reasons.append("cash roles are unknown")
    return PortfolioRiskAssessment(
        invested_sleeve_exposure_risk=RiskAssessment(
            score=exposure_score,
            level=_risk_level(exposure_score),
            scope="invested_sleeve_exposure",
            explanations=[
            f"Target-allocation gap: {gap_points} points.",
            f"Invested-holdings concentration: {concentration_points} points.",
                f"USD coverage: {coverage_points} points.",
                f"Total invested-sleeve exposure risk: {exposure_score}/100.",
            ],
        ),
        data_quality_risk=RiskAssessment(
            score=data_quality_score,
            level=_risk_level(data_quality_score),
            scope="portfolio_data_quality",
            explanations=[
            f"Stale portfolio snapshots: {stale_points} points.",
                f"Unknown cash roles: {unknown_role_points} points.",
                f"Total portfolio data-quality risk: {data_quality_score}/100.",
            ],
        ),
        decision_readiness="blocked" if readiness_reasons else "ready",
        readiness_reasons=tuple(readiness_reasons),
    )


def build_report_use_states(
    market_risk: RiskAssessment,
    macro_context: MacroContext | None,
    sector_rotation: SectorRotation,
    data_coverage: DataCoverage | None,
    portfolio_summary: PortfolioSummary,
    portfolio_decision_risk: PortfolioRiskAssessment,
    news_quality: NewsQualityGate | None,
    profile: ReportProfile | None = None,
    fx_state: FxState | None = None,
    fundamental_state: FundamentalEvidenceState | None = None,
) -> ReportUseStates:
    spy_row = next(
        (
            row
            for row in (data_coverage.rows if data_coverage else [])
            if row.category == "Prices" and row.item == "SPY"
        ),
        None,
    )
    market_available = (
        (spy_row is None or spy_row.status == "available")
        and market_risk.level != "unknown"
    )
    market_actionability = "available" if market_available else "blocked"
    market_reason = (
        "Core price, breadth, and volatility evidence support market analysis."
        if market_available
        else "Core price evidence is insufficient for market analysis."
    )

    portfolio_reasons = list(portfolio_decision_risk.readiness_reasons)
    portfolio_readiness = portfolio_decision_risk.decision_readiness
    portfolio_analysis_status = (
        "blocked"
        if portfolio_summary.snapshot_status == "unavailable"
        else "limited"
        if portfolio_reasons
        else "available"
    )
    action_reasons = list(portfolio_reasons)
    if profile is not None and not profile.target_allocations:
        action_reasons.append("target allocations are not configured")
    if profile is not None and profile.target_allocations:
        unmapped_target_symbols = sorted(
            item.symbol
            for item in portfolio_summary.allocations
            if (item.current_weight or 0) > 0 and item.target_weight is None
        )
        if unmapped_target_symbols:
            action_reasons.append(
                "target allocations do not cover current holdings: "
                + ", ".join(unmapped_target_symbols)
            )
    if (
        profile is not None
        and profile.target_allocations
        and profile.target_allocation.tolerance is None
    ):
        action_reasons.append("target allocation tolerance is not configured")
    if profile is not None and profile.daily_investment_budget is None:
        action_reasons.append("daily investment budget is not configured")
    portfolio_actionability = "blocked" if action_reasons else "available"
    portfolio_risk = (
        "unknown"
        if portfolio_readiness == "blocked"
        else portfolio_decision_risk.exposure_risk.level
    )

    macro_available = (
        macro_context is not None and macro_context.overall_regime != "unknown"
    )
    macro_status = "available" if macro_available else "blocked"
    macro_reasons = () if macro_available else ("macro regime is unavailable",)

    if fx_state is None:
        fx_status = "degraded"
        fx_reasons = ("fx_state_not_evaluated",)
    else:
        fx_status = fx_state.status
        fx_reasons = fx_state.reasons

    news_external = (
        news_quality is not None
        and news_quality.status == "external_research"
    )
    news_blocked = (
        news_quality is None
        or news_quality.status in {"disabled", "data_quality_review"}
    )
    news_state = NewsState(
        quality=(
            "external_research"
            if news_external
            else "blocked" if news_blocked else "available"
        ),
        actionability=(
            "reference_only"
            if news_external
            else "unavailable" if news_blocked else "available"
        ),
        reason=(
            "; ".join(news_quality.reasons)
            if news_quality is not None and news_quality.reasons
            else (
                "Current news is delegated to a GPT research task."
                if news_external
                else "News evidence is not available."
                if news_blocked
                else "News evidence passed its quality gate."
            )
        ),
    )
    news_reasons = (
        ()
        if news_external
        else tuple(news_quality.reasons)
        if news_quality is not None and news_quality.reasons
        else ("news evidence is unavailable",)
        if news_blocked
        else ()
    )
    if fundamental_state is None:
        fundamental_status = "blocked"
        fundamental_reasons = ("fundamental_state_not_evaluated",)
    else:
        fundamental_reasons = fundamental_state.reasons
        statuses = {
            fundamental_state.valuation_status,
            fundamental_state.earnings_revision_status,
        }
        fundamental_status = (
            "blocked"
            if statuses == {"blocked"}
            else "available"
            if statuses == {"available"}
            else "degraded"
        )
    capabilities = ReportCapabilities(
        market_analysis=CapabilityState(
            market_actionability,
            () if market_available else (market_reason,),
        ),
        macro_analysis=CapabilityState(macro_status, macro_reasons),
        portfolio_analysis=CapabilityState(
            portfolio_analysis_status,
            tuple(portfolio_reasons),
        ),
        investment_action=CapabilityState(
            portfolio_actionability,
            tuple(action_reasons),
        ),
        fx_analysis=CapabilityState(fx_status, fx_reasons),
        news_analysis=CapabilityState(
            (
                "external_research"
                if news_external
                else "blocked" if news_blocked else "available"
            ),
            news_reasons,
        ),
        fundamental_analysis=CapabilityState(
            fundamental_status, fundamental_reasons
        ),
    )
    overall_status = data_coverage.status if data_coverage else "blocked"
    return ReportUseStates(
        market=MarketState(
            risk=market_risk.level,
            regime=_market_state_regime(macro_context, sector_rotation),
            actionability=market_actionability,
            reason=market_reason,
        ),
        portfolio=PortfolioDecisionState(
            risk=portfolio_risk,
            data_readiness=portfolio_readiness,
            actionability=portfolio_actionability,
            reason=(
                "Portfolio decision readiness is blocked because "
                + " and ".join(action_reasons)
                + "."
                if action_reasons
                else "Portfolio inputs support portfolio-specific analysis."
            ),
        ),
        news=news_state,
        data_quality=DataQualityState(
            overall=CapabilityState(overall_status),
            capabilities=capabilities,
        ),
    )


def assess_portfolio_risk(summary: PortfolioSummary) -> PortfolioRiskAssessment:
    """Backward-compatible alias for the split portfolio risk assessment."""
    return assess_portfolio_decision_risk(summary)


def analyze_fx_costs(
    portfolio_state: PortfolioReportState | None,
    usd_cnh_history: list[PriceBar],
) -> list[FxCostComparison]:
    if portfolio_state is None:
        return []
    results: list[FxCostComparison] = []
    for conversion in portfolio_state.fx_conversions:
        if not (
            conversion.sold_currency == "CNY"
            and conversion.bought_currency == "USD"
        ):
            continue
        sold = float(conversion.sold_amount)
        bought = float(conversion.bought_amount)
        if conversion.fee_currency == "CNY":
            sold += float(conversion.fee_amount)
        elif conversion.fee_currency == "USD":
            bought -= float(conversion.fee_amount)
        all_in = sold / bought
        spot = _spot_on_or_before(usd_cnh_history, conversion.fx_date)
        results.append(
            FxCostComparison(
                fx_date=conversion.fx_date,
                pair="CNY/USD",
                effective_rate=float(conversion.effective_rate),
                all_in_rate=all_in,
                spot_rate=spot,
                spot_premium=all_in / spot - 1 if spot else None,
                benchmark_note=(
                    "USD/CNH close is an offshore approximation, not an exact "
                    "bank CNY spread."
                ),
            )
        )
    return results


def analyze_fx_state(
    portfolio_state: PortfolioReportState | None,
    portfolio_summary: PortfolioSummary,
    usd_cnh_history: list[PriceBar],
) -> FxState:
    comparisons = analyze_fx_costs(portfolio_state, usd_cnh_history)
    spot = (
        max(usd_cnh_history, key=lambda item: item.date).close
        if usd_cnh_history
        else None
    )
    cost_basis = _weighted_fx_cost_basis(portfolio_state)
    reasons: list[str] = []
    if portfolio_state is None:
        reasons.append("portfolio_state_not_supplied")
    elif cost_basis is None:
        reasons.append("cny_usd_cost_basis_unavailable")
    if spot is None:
        reasons.append("usd_cnh_spot_unavailable")
    if portfolio_summary.usd_daily_spend is None:
        reasons.append("usd_daily_spend_not_configured")
    coverage_status = _coverage_status(portfolio_summary.usd_coverage_days)
    status = (
        "blocked"
        if portfolio_state is None or cost_basis is None
        else "degraded"
        if spot is None or portfolio_summary.usd_daily_spend is None
        else "available"
    )
    return FxState(
        status=status,
        usd_balance=portfolio_summary.usd_cash,
        usd_required_daily=portfolio_summary.usd_daily_spend,
        coverage_days=portfolio_summary.usd_coverage_days,
        spot_usd_cnh=spot,
        cost_basis=cost_basis,
        difference_pct=(
            spot / cost_basis - 1
            if spot is not None and cost_basis not in {None, 0}
            else None
        ),
        reasons=tuple(reasons),
        comparisons=tuple(comparisons),
        coverage_status=coverage_status,
    )


def evaluate_strategy_rules(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    portfolio_summary: PortfolioSummary,
    evidence: list[MarketEvidence],
    use_states: ReportUseStates,
) -> list[StrategyRuleResult]:
    results: list[StrategyRuleResult] = []
    if use_states.market.actionability != "available":
        results.append(
            StrategyRuleResult(
                "Market analysis readiness gate",
                "triggered",
                use_states.market.actionability,
                "Market actionability must be available",
                use_states.market.reason,
                evidence_refs=("STATE:MARKET", "DQ:MARKET"),
            )
        )
    if use_states.portfolio.actionability != "available":
        results.append(
            StrategyRuleResult(
                "Portfolio decision readiness gate",
                "triggered",
                use_states.portfolio.data_readiness,
                "Portfolio data readiness and actionability must be available",
                use_states.portfolio.reason,
                evidence_refs=(
                    "STATE:PORTFOLIO",
                    "DQ:PORTFOLIO:SNAPSHOT",
                    "DQ:PORTFOLIO:CASH_ROLES",
                ),
            )
        )
    for cluster, symbols in RISK_CLUSTERS.items():
        triggered = [
            signal for symbol, signal in price_signals.items()
            if symbol in symbols and signal.is_unusual_move
        ]
        if not triggered:
            continue
        strongest = max(triggered, key=_signal_severity)
        is_cluster = len(triggered) >= 2
        results.append(
            StrategyRuleResult(
                (
                    f"Unusual move cluster: {cluster}"
                    if is_cluster
                    else f"Single-asset unusual move: {strongest.symbol}"
                ),
                "triggered",
                ", ".join(sorted(signal.symbol for signal in triggered)),
                "absolute-move z-score ≥ 2.0, ATR ≥ 1.5x, or "
                "absolute-move percentile ≥ 95%",
                strongest.reason,
                return_zscore=strongest.absolute_move_z_score_60d,
                atr_multiple=strongest.atr_multiple,
                historical_percentile=strongest.absolute_move_percentile_252d,
                evidence_refs=tuple(
                    sorted(_evidence_ref(signal) for signal in triggered)
                ),
            )
        )
    magnitude = abs(sector_rotation.risk_on_score)
    if magnitude >= 0.28:
        results.append(
            StrategyRuleResult(
                "Sector rotation monitor",
                "triggered" if magnitude >= 0.35 else "near",
                f"{sector_rotation.risk_on_score:.2f}",
                "|risk-on score| ≥ 0.35; near ≥ 0.28",
                "Sector leadership is near or beyond the regime boundary.",
                evidence_refs=("BREADTH:SECTOR_ROTATION",),
            )
        )
    gaps = [
        abs(row.weight_gap)
        for row in portfolio_summary.allocations
        if row.weight_gap is not None
    ]
    if gaps and max(gaps) >= 0.04:
        results.append(
            StrategyRuleResult(
                "Target allocation drift",
                "triggered" if max(gaps) >= 0.05 else "near",
                _format_percent(max(gaps)),
                "Absolute invested-holdings target gap ≥ 5%; near ≥ 4%",
                "At least one invested holding is outside its review band.",
                evidence_refs=("PORTFOLIO:ALLOCATION",),
            )
        )
    divergences = [
        row for row in evidence
        if row.short_term_state in {"countertrend_rebound", "countertrend_pullback"}
    ]
    if divergences:
        strongest = max(
            divergences,
            key=lambda row: max(
                row.return_zscore or 0,
                row.atr_multiple or 0,
                row.historical_percentile or 0,
            ),
        )
        results.append(
            StrategyRuleResult(
                "Medium-term/short-term divergence",
                "triggered",
                ", ".join(row.symbol for row in divergences),
                "5D direction opposes the 50D/200D medium-term trend",
                "Short-term movement has not changed the medium-term trend.",
                strongest.return_zscore,
                strongest.atr_multiple,
                strongest.historical_percentile,
                tuple(row.evidence_ref for row in divergences),
            )
        )
    return results


def build_report_state(
    use_states: ReportUseStates,
    market_risk: RiskAssessment,
    portfolio_decision_risk: PortfolioRiskAssessment,
    rules: list[StrategyRuleResult],
    evidence: list[MarketEvidence],
    portfolio: PortfolioSummary,
    fx_state: FxState | None = None,
    strategy_decision: StrategyDecisionState | None = None,
    portfolio_impact: PortfolioImpactAnalysis | None = None,
    fundamental_state: FundamentalEvidenceState | None = None,
    decision_context: DecisionContext | None = None,
) -> ReportState:
    liquid_view = portfolio.liquid_asset_allocation
    return ReportState(
        data_quality_status=(
            use_states.data_quality.overall.status
            if use_states.data_quality is not None
            else "unknown"
        ),
        market_actionability=use_states.market.actionability,
        market_regime=use_states.market.regime,
        market_risk_score=market_risk.score,
        market_risk_level=market_risk.level,
        portfolio_risk=use_states.portfolio.risk,
        portfolio_data_readiness=use_states.portfolio.data_readiness,
        portfolio_actionability=use_states.portfolio.actionability,
        invested_sleeve_exposure_risk_score=(
            portfolio_decision_risk.invested_sleeve_exposure_risk.score
        ),
        invested_sleeve_exposure_risk_level=(
            portfolio_decision_risk.invested_sleeve_exposure_risk.level
        ),
        portfolio_data_quality_risk_score=(
            portfolio_decision_risk.data_quality_risk.score
        ),
        portfolio_data_quality_risk_level=(
            portfolio_decision_risk.data_quality_risk.level
        ),
        news_quality=use_states.news.quality,
        news_actionability=use_states.news.actionability,
        triggered_rules=tuple(
            sorted(f"{rule.name}:{rule.status}" for rule in rules)
        ),
        medium_term_trends=tuple(
            sorted(f"{row.symbol}:{row.medium_term_trend}" for row in evidence)
        ),
        portfolio_gaps=tuple(
            sorted(
                f"{row.symbol}:{row.weight_gap:.4f}"
                for row in portfolio.allocations
                if row.weight_gap is not None
            )
        ),
        capabilities=_serialize_capabilities(use_states),
        invested_allocation=_serialize_allocation(
            portfolio.invested_allocation.allocations
            if portfolio.invested_allocation is not None
            else portfolio.allocations
        ),
        liquid_asset_allocation_status=(
            liquid_view.status if liquid_view is not None else "unavailable"
        ),
        liquid_asset_allocation_reason=(
            liquid_view.reason if liquid_view is not None else "not_generated"
        ),
        liquid_asset_allocation=_serialize_allocation(
            liquid_view.allocations if liquid_view is not None else []
        ),
        fx_status=fx_state.status if fx_state is not None else "unavailable",
        fx_spot_usd_cnh=(
            fx_state.spot_usd_cnh if fx_state is not None else None
        ),
        fx_cost_basis=fx_state.cost_basis if fx_state is not None else None,
        fx_difference_pct=(
            fx_state.difference_pct if fx_state is not None else None
        ),
        action_readiness_status=(
            strategy_decision.action_readiness.status
            if strategy_decision is not None
            else "blocked"
        ),
        veto_status=(
            strategy_decision.action_readiness.veto_status
            if strategy_decision is not None
            else "unknown"
        ),
        candidate_action=(
            strategy_decision.action_readiness.candidate_action
            if strategy_decision is not None
            else None
        ),
        candidate_symbol=(
            strategy_decision.action_readiness.symbol
            if strategy_decision is not None
            else None
        ),
        candidate_rule_id=(
            strategy_decision.action_readiness.rule_id
            if strategy_decision is not None
            else None
        ),
        execution_readiness_status=(
            strategy_decision.execution_readiness.status
            if strategy_decision is not None
            else "blocked"
        ),
        rule_execution_permission_status=(
            strategy_decision.execution_readiness.permission_status
            if strategy_decision is not None
            else "unknown"
        ),
        proposed_action_amount=(
            strategy_decision.execution_readiness.proposed_amount
            if strategy_decision is not None
            else None
        ),
        proposed_action_currency=(
            strategy_decision.execution_readiness.currency
            if strategy_decision is not None
            else None
        ),
        decision_context_status=(
            decision_context.status if decision_context is not None else "blocked"
        ),
        decision_transition=(
            decision_context.transition if decision_context is not None else "baseline"
        ),
        dominant_portfolio_factor=(
            decision_context.dominant_factor_id
            if decision_context is not None
            else None
        ),
        dominant_portfolio_impact_score=(
            decision_context.dominant_impact_score
            if decision_context is not None
            else None
        ),
        decision_context_reasons=(
            decision_context.reasons if decision_context is not None else ()
        ),
        portfolio_factor_exposures=(
            {
                item.factor_id: (
                    round(item.weight, 6) if item.weight is not None else None
                )
                for item in portfolio_impact.factors.exposures
            }
            if portfolio_impact is not None
            else {}
        ),
        portfolio_impact_scores=(
            {
                item.factor_id: item.impact_score
                for item in portfolio_impact.impact.items
            }
            if portfolio_impact is not None
            else {}
        ),
        valuation_status=(
            fundamental_state.valuation_status
            if fundamental_state is not None
            else "blocked"
        ),
        earnings_revision_status=(
            fundamental_state.earnings_revision_status
            if fundamental_state is not None
            else "blocked"
        ),
        earnings_revision_directions=(
            {
                f"{item.symbol}:{item.fiscal_period}:{item.metric}": item.direction
                for item in fundamental_state.revisions
            }
            if fundamental_state is not None
            else {}
        ),
        decision_evidence_status=(
            decision_context.decision_evidence.status
            if decision_context is not None
            and decision_context.decision_evidence is not None
            else "blocked"
        ),
        decision_evidence_symbols=(
            tuple(
                item.symbol
                for item in decision_context.decision_evidence.assets
            )
            if decision_context is not None
            and decision_context.decision_evidence is not None
            else ()
        ),
        decision_evidence_review_flags=(
            decision_context.decision_evidence.review_flags
            if decision_context is not None
            and decision_context.decision_evidence is not None
            else ()
        ),
        news_entity_pipeline_status=(
            decision_context.decision_evidence.news_entity_status
            if decision_context is not None
            and decision_context.decision_evidence is not None
            else "disabled"
        ),
        strategy_rule_states=(
            {
                result.rule_id: result.status
                for result in strategy_decision.rules
                if result.rule_id
            }
            if strategy_decision is not None
            else {}
        ),
    )


def serialize_report_state(state: ReportState) -> str:
    return (
        REPORT_STATE_PREFIX
        + json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)
        + REPORT_STATE_SUFFIX
    )


def _serialize_capabilities(states: ReportUseStates) -> dict[str, str]:
    if states.data_quality is None:
        return {}
    capabilities = states.data_quality.capabilities
    return {
        name: capability.status
        for name, capability in (
            ("market_analysis", capabilities.market_analysis),
            ("macro_analysis", capabilities.macro_analysis),
            ("portfolio_analysis", capabilities.portfolio_analysis),
            ("investment_action", capabilities.investment_action),
            ("fx_analysis", capabilities.fx_analysis),
            ("news_analysis", capabilities.news_analysis),
            ("fundamental_analysis", capabilities.fundamental_analysis),
        )
    }


def _serialize_allocation(
    allocations: list[PortfolioAllocation],
) -> dict[str, float | None]:
    return {
        row.symbol: (
            round(row.current_weight, 6)
            if row.current_weight is not None
            else None
        )
        for row in sorted(allocations, key=lambda item: item.symbol)
    }


def extract_report_state(content: str | None) -> ReportState | None:
    if not content:
        return None
    for line in content.splitlines():
        if not (
            line.startswith(REPORT_STATE_PREFIX)
            and line.endswith(REPORT_STATE_SUFFIX)
        ):
            continue
        data = json.loads(
            line[len(REPORT_STATE_PREFIX) : -len(REPORT_STATE_SUFFIX)]
        )
        return ReportState(
            data_quality_status=data.get("data_quality_status", "unknown"),
            market_actionability=data.get("market_actionability", "available"),
            market_regime=data.get(
                "market_regime", data.get("macro_regime", "unknown")
            ),
            market_risk_score=int(
                data.get("market_risk_score", data.get("risk_score", 0))
            ),
            market_risk_level=data.get(
                "market_risk_level", data.get("risk_level", "unknown")
            ),
            portfolio_risk=data.get("portfolio_risk", "unknown"),
            portfolio_data_readiness=data.get(
                "portfolio_data_readiness",
                "blocked"
                if data.get("data_quality_status") == "blocked"
                else "unknown",
            ),
            portfolio_actionability=data.get(
                "portfolio_actionability", "blocked"
            ),
            invested_sleeve_exposure_risk_score=int(
                data.get(
                    "invested_sleeve_exposure_risk_score",
                    data.get(
                        "portfolio_exposure_risk_score",
                        data.get("portfolio_decision_risk_score", 0),
                    ),
                )
            ),
            invested_sleeve_exposure_risk_level=data.get(
                "invested_sleeve_exposure_risk_level",
                data.get(
                    "portfolio_exposure_risk_level",
                    data.get("portfolio_decision_risk_level", "unknown"),
                ),
            ),
            portfolio_data_quality_risk_score=int(
                data.get(
                    "portfolio_data_quality_risk_score",
                    data.get("portfolio_risk_score", 0),
                )
            ),
            portfolio_data_quality_risk_level=data.get(
                "portfolio_data_quality_risk_level",
                data.get("portfolio_risk_level", "unknown"),
            ),
            news_quality=data.get(
                "news_quality",
                "blocked"
                if data.get("data_quality_status") == "blocked"
                else "unknown",
            ),
            news_actionability=data.get("news_actionability", "unavailable"),
            triggered_rules=tuple(
                _normalize_legacy_rule(value)
                for value in data["triggered_rules"]
            ),
            medium_term_trends=tuple(
                _normalize_legacy_trend(value)
                for value in data.get(
                    "medium_term_trends",
                    data.get("structural_trends", []),
                )
            ),
            portfolio_gaps=tuple(data["portfolio_gaps"]),
            capabilities=dict(data.get("capabilities", {})),
            invested_allocation=dict(data.get("invested_allocation", {})),
            liquid_asset_allocation_status=data.get(
                "liquid_asset_allocation_status", "unavailable"
            ),
            liquid_asset_allocation_reason=data.get(
                "liquid_asset_allocation_reason", ""
            ),
            liquid_asset_allocation=dict(
                data.get("liquid_asset_allocation", {})
            ),
            fx_status=data.get("fx_status", "unavailable"),
            fx_spot_usd_cnh=data.get("fx_spot_usd_cnh"),
            fx_cost_basis=data.get("fx_cost_basis"),
            fx_difference_pct=data.get("fx_difference_pct"),
            action_readiness_status=data.get(
                "action_readiness_status", "blocked"
            ),
            veto_status=data.get("veto_status", "unknown"),
            candidate_action=data.get("candidate_action"),
            candidate_symbol=data.get("candidate_symbol"),
            candidate_rule_id=data.get("candidate_rule_id"),
            execution_readiness_status=data.get(
                "execution_readiness_status", "blocked"
            ),
            rule_execution_permission_status=data.get(
                "rule_execution_permission_status", "unknown"
            ),
            proposed_action_amount=data.get("proposed_action_amount"),
            proposed_action_currency=data.get("proposed_action_currency"),
            decision_context_status=data.get(
                "decision_context_status", "blocked"
            ),
            decision_transition=data.get("decision_transition", "baseline"),
            dominant_portfolio_factor=data.get("dominant_portfolio_factor"),
            dominant_portfolio_impact_score=data.get(
                "dominant_portfolio_impact_score"
            ),
            decision_context_reasons=tuple(
                data.get("decision_context_reasons", [])
            ),
            portfolio_factor_exposures=dict(
                data.get("portfolio_factor_exposures", {})
            ),
            portfolio_impact_scores={
                key: int(value)
                for key, value in data.get("portfolio_impact_scores", {}).items()
            },
            valuation_status=data.get("valuation_status", "blocked"),
            earnings_revision_status=data.get(
                "earnings_revision_status", "blocked"
            ),
            earnings_revision_directions=dict(
                data.get("earnings_revision_directions", {})
            ),
            decision_evidence_status=data.get(
                "decision_evidence_status", "blocked"
            ),
            decision_evidence_symbols=tuple(
                data.get("decision_evidence_symbols", [])
            ),
            decision_evidence_review_flags=tuple(
                data.get("decision_evidence_review_flags", [])
            ),
            news_entity_pipeline_status=data.get(
                "news_entity_pipeline_status", "disabled"
            ),
            strategy_rule_states=dict(data.get("strategy_rule_states", {})),
            gpt_task_ids=tuple(data.get("gpt_task_ids", [])),
        )
    return None


def _normalize_legacy_trend(value: str) -> str:
    return (
        value.replace("structural_uptrend", "legacy_uptrend")
        .replace("structural_downtrend", "legacy_downtrend")
    )


def _normalize_legacy_rule(value: str) -> str:
    return value.replace(
        "Data quality circuit breaker",
        "Legacy overall data-quality gate",
    )


def compare_report_states(
    previous: ReportState | None,
    current: ReportState,
) -> list[str]:
    if previous is None:
        return ["Baseline created; no previous comparable report state was found."]
    labels = {
        "data_quality_status": "Overall data quality",
        "market_actionability": "Market actionability",
        "market_regime": "Market regime",
        "market_risk_score": "Market risk score",
        "market_risk_level": "Market risk level",
        "portfolio_risk": "Portfolio risk",
        "portfolio_data_readiness": "Portfolio data readiness",
        "portfolio_actionability": "Portfolio actionability",
        "invested_sleeve_exposure_risk_score": "Invested-sleeve exposure risk score",
        "invested_sleeve_exposure_risk_level": "Invested-sleeve exposure risk level",
        "portfolio_data_quality_risk_score": "Portfolio data-quality risk score",
        "portfolio_data_quality_risk_level": "Portfolio data-quality risk level",
        "news_quality": "News quality",
        "news_actionability": "News actionability",
        "triggered_rules": "Triggered/near rules",
        "medium_term_trends": "Medium-term trends",
        "portfolio_gaps": "Portfolio target gaps",
        "capabilities": "Capability states",
        "invested_allocation": "Invested sleeve allocation",
        "liquid_asset_allocation_status": "Liquid asset allocation status",
        "liquid_asset_allocation_reason": "Liquid asset allocation reason",
        "liquid_asset_allocation": "Liquid asset allocation",
        "fx_status": "FX status",
        "fx_spot_usd_cnh": "USD/CNH spot",
        "fx_cost_basis": "FX cost basis",
        "fx_difference_pct": "FX spot-to-cost difference",
        "action_readiness_status": "Action readiness",
        "veto_status": "Safety veto",
        "candidate_action": "Decision candidate action",
        "candidate_symbol": "Decision candidate symbol",
        "candidate_rule_id": "Decision candidate rule",
        "execution_readiness_status": "Execution readiness",
        "rule_execution_permission_status": "Rule execution permission",
        "proposed_action_amount": "Proposed action amount",
        "proposed_action_currency": "Proposed action currency",
        "decision_context_status": "Decision context status",
        "decision_transition": "Decision transition",
        "dominant_portfolio_factor": "Dominant portfolio factor",
        "dominant_portfolio_impact_score": "Dominant portfolio impact score",
        "decision_context_reasons": "Decision context reasons",
        "portfolio_factor_exposures": "Portfolio factor exposures",
        "portfolio_impact_scores": "Portfolio impact scores",
        "valuation_status": "Valuation evidence status",
        "earnings_revision_status": "Earnings revision status",
        "earnings_revision_directions": "Earnings revision directions",
        "decision_evidence_status": "Decision evidence status",
        "decision_evidence_symbols": "Decision evidence symbols",
        "decision_evidence_review_flags": "Decision evidence review flags",
        "news_entity_pipeline_status": "News entity pipeline status",
        "strategy_rule_states": "Strategy rule states",
    }
    changes = []
    for field, label in labels.items():
        before = getattr(previous, field)
        after = getattr(current, field)
        if before == after:
            continue
        severity = _change_severity(field, before, after)
        changes.append(
            f"[{severity}] {label}: {_semantic_state_diff(before, after)}."
        )
    return changes or ["No state changes detected."]


def _semantic_state_diff(before, after) -> str:
    if isinstance(before, dict) and isinstance(after, dict):
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        changed = sorted(
            key for key in set(before) & set(after) if before[key] != after[key]
        )
        parts = []
        if added:
            parts.append("added " + ", ".join(added))
        if removed:
            parts.append("removed " + ", ".join(removed))
        if changed:
            parts.append(
                "changed "
                + ", ".join(
                    f"{key} ({_state_value(before[key])} → {_state_value(after[key])})"
                    for key in changed
                )
            )
        return "; ".join(parts) or "mapping content changed"
    if isinstance(before, tuple) and isinstance(after, tuple):
        added = sorted(set(after) - set(before))
        removed = sorted(set(before) - set(after))
        parts = []
        if added:
            parts.append("added " + ", ".join(added))
        if removed:
            parts.append("removed " + ", ".join(removed))
        return "; ".join(parts) or "ordered values changed"
    return f"{_state_value(before)} → {_state_value(after)}"


def _change_severity(field: str, before, after) -> str:
    if field in {
        "action_readiness_status",
        "veto_status",
        "execution_readiness_status",
        "rule_execution_permission_status",
        "decision_context_status",
    }:
        return "critical"
    if field in {
        "market_actionability",
        "portfolio_actionability",
        "portfolio_data_readiness",
        "data_quality_status",
        "strategy_rule_states",
        "valuation_status",
        "earnings_revision_status",
    }:
        return "high"
    if field.endswith("risk_score") or field.endswith("risk_level"):
        return "medium"
    return "low"


def build_gpt_tasks(
    profile: ReportProfile,
    changes: list[str],
    rules: list[StrategyRuleResult],
    evidence: list[MarketEvidence],
    use_states: ReportUseStates,
    strategy_decision: StrategyDecisionState | None = None,
) -> list[GptAnalysisTask]:
    market_refs = tuple(row.evidence_ref for row in evidence[:6])
    evidence_by_symbol = {row.symbol: row.evidence_ref for row in evidence}
    questions: list[
        tuple[str, str, tuple[str, ...], str, tuple[str, ...]]
    ] = []
    if any("Baseline created" not in item and "No state changes" not in item for item in changes):
        questions.append(
            (
                "explain_state_changes",
                "哪些状态变化最重要，它们是否改变此前判断？",
                (
                    "STATE:CHANGES",
                    "STATE:MARKET",
                    "STATE:PORTFOLIO",
                    "STATE:NEWS",
                ),
                "ready",
                (),
            )
        )
    if rules:
        questions.append(
            (
                "explain_triggered_rules",
                "如何解释已触发或接近触发的规则，并识别共同风险簇？",
                tuple(dict.fromkeys(
                    ref for rule in rules for ref in rule.evidence_refs
                )),
                "ready",
                (),
            )
        )
    if strategy_decision is not None:
        readiness = strategy_decision.action_readiness
        questions.append(
            (
                "explain_strategy_decision",
                "根据确定性规则的计算结果，解释 action readiness、命中的条件与"
                "缺失证据；不要创建、修改或替代策略规则。",
                tuple(
                    dict.fromkeys(
                        [
                            "STATE:ACTION_READINESS",
                            *readiness.evidence_refs,
                            *(
                                ref
                                for rule in strategy_decision.rules
                                for ref in rule.evidence_refs
                            ),
                        ]
                    )
                ),
                "ready",
                (),
            )
        )
    for index, question in enumerate(profile.gpt_questions, 1):
        refs, required_state = _gpt_question_refs(
            question,
            market_refs,
            evidence_by_symbol,
        )
        if required_state == "external_research":
            continue
        blocked_reasons: list[str] = []
        status = "ready"
        capability = None
        if use_states.data_quality is not None:
            capabilities = use_states.data_quality.capabilities
            capability = {
                "portfolio_action": capabilities.investment_action,
                "portfolio_analysis": capabilities.portfolio_analysis,
                "news": capabilities.news_analysis,
                "market": capabilities.market_analysis,
                "fx": capabilities.fx_analysis,
                "fundamental": capabilities.fundamental_analysis,
            }.get(required_state)
        if capability is not None and capability.status != "available":
            status = (
                "blocked"
                if capability.status in {"blocked", "unavailable"}
                else "degraded"
            )
            blocked_reasons.extend(capability.reasons)
        elif (
            required_state == "portfolio_action"
            and use_states.portfolio.actionability != "available"
        ):
            status = "blocked"
            blocked_reasons.append(use_states.portfolio.reason)
        elif required_state == "news" and use_states.news.actionability != "available":
            status = "blocked"
            blocked_reasons.append(use_states.news.reason)
        elif required_state == "market" and use_states.market.actionability != "available":
            status = "blocked"
            blocked_reasons.append(use_states.market.reason)
        if (
            any(term in question for term in ["目标仓位", "配置缺口"])
            and not profile.target_allocations
        ):
            status = "blocked"
            blocked_reasons.append("target allocations are not configured")
        task_id = (
            "evaluate_allocation_gap"
            if any(term in question for term in ["目标仓位", "配置缺口"])
            else "research_external_news"
            if any(term in question for term in ["新闻", "近期事件", "参考资料"])
            else f"profile_question_{index}_{required_state}"
        )
        questions.append(
            (
                task_id,
                question,
                refs,
                status,
                tuple(dict.fromkeys(blocked_reasons)),
            )
        )

    news_question = next(
        (
            question
            for question in profile.gpt_questions
            if any(term in question for term in ["新闻", "近期事件", "参考资料"])
        ),
        (
            "优先关注科技股，检索并核验与当前市场状态、持仓和决策候选"
            "相关的近期新闻、研究报告与官方资料；重点说明市场资金流向，"
            "包括券商、银行、政府或公共部门以及个人投资者的资金动向，并"
            "指出哪些事实可能解释或反驳现有判断。"
        ),
    )
    questions.append(
        (
            "research_external_news",
            news_question,
            (
                "STATE:MARKET",
                "STATE:PORTFOLIO",
                "PORTFOLIO:ALLOCATION",
                "FUNDAMENTAL:STATE",
            ),
            "ready",
            (),
        )
    )

    available_output = (
        "Conclusion; supporting evidence linked by ref; counterevidence; "
        "confidence; confirmation conditions; invalidation conditions; do not "
        "invent or modify strategy rules."
    )
    blocked_output = (
        "State that the task is blocked; list missing or stale inputs by evidence "
        "ref; do not infer a decision; specify what would unblock the task."
    )
    external_research_output = (
        "Current source summary with direct URL, publisher, publication date, and "
        "event date for each material item; separate sourced facts from model "
        "interpretation; prioritize technology stocks and summarize market money "
        "flows, distinguishing broker, bank, government or public-sector, and retail "
        "investor activity when supported; explain relevance and counterevidence; "
        "state that research was unavailable if browsing or source verification is "
        "unavailable; do not turn news into an action or override deterministic rules."
    )
    return [
        GptAnalysisTask(
            question=question,
            evidence_refs=evidence_refs,
            expected_output=(
                external_research_output
                if task_id == "research_external_news"
                else blocked_output if status == "blocked" else available_output
            ),
            confidence_requirement=(
                "Confidence applies to interpretation, not sourced facts; identify "
                "unverified or single-source claims."
                if task_id == "research_external_news"
                else "Do not assign confidence while blocked."
                if status == "blocked"
                else "State confidence as low/medium and name degraded inputs."
                if status == "degraded"
                else "State confidence as low/medium/high."
            ),
            task_id=task_id,
            status=status,
            status_reasons=blocked_reasons,
        )
        for task_id, question, evidence_refs, status, blocked_reasons
        in _deduplicate_task_specs(questions)
    ]


def build_evidence_registry(
    evidence: list[MarketEvidence],
    rules: list[StrategyRuleResult],
    fundamental_state: FundamentalEvidenceState | None = None,
) -> dict[str, str]:
    """Build the canonical, unique Evidence Ref registry for report consumers."""
    registry = {
        "STATE:CHANGES": "Semantic changes since the previous report",
        "STATE:MARKET": "Canonical market state",
        "STATE:PORTFOLIO": "Canonical portfolio decision state",
        "STATE:NEWS": "Current-news research mode",
        "STATE:ACTION_READINESS": "Deterministic action and veto state",
        "STATE:EXECUTION_READINESS": "Sizing and execution-permission state",
        "BREADTH:MARKET": "Tracked-universe breadth",
        "BREADTH:VIX": "VIX level and 252-day percentile",
        "BREADTH:SECTOR_ROTATION": "Sector-rotation breadth",
        "MACRO:CREDIT": "Canonical macro credit state",
        "PORTFOLIO:ALLOCATION": "Invested-sleeve cost allocation and targets",
        "PORTFOLIO:FACTOR_IMPACT": "Market-factor to portfolio-impact mapping",
        "PORTFOLIO:FX": "FX balances, cost basis, and coverage",
        "FUNDAMENTAL:STATE": "Asset-typed valuation and earnings evidence",
        "DQ:MARKET": "Market data quality",
        "DQ:PORTFOLIO:SNAPSHOT": "Portfolio snapshot freshness",
        "DQ:PORTFOLIO:CASH_ROLES": "Cash-role classification quality",
        "DQ:FUNDAMENTALS": "Fundamental data quality",
        "DQ:FUNDAMENTALS:VALUATION": "Valuation data quality",
        "DQ:FUNDAMENTALS:EARNINGS_REVISION": "Earnings-revision data quality",
    }
    for row in evidence:
        registry[row.evidence_ref] = f"Price-derived evidence for {row.symbol}"
    for rule in rules:
        for ref in rule.evidence_refs:
            registry.setdefault(ref, f"Condition evidence for {rule.rule_id or rule.name}")
    if fundamental_state is not None:
        for item in fundamental_state.valuations:
            ref = (
                f"VALUATION:{item.symbol}:{item.metric}:"
                f"{item.as_of_date.isoformat()}:{item.source}"
            )
            registry[ref] = f"{item.asset_type} valuation observation for {item.symbol}"
        for item in fundamental_state.revisions:
            ref = (
                f"EARNINGS_REVISION:{item.symbol}:{item.fiscal_period}:"
                f"{item.metric}:{item.current_date.isoformat()}:{item.source}"
            )
            registry[ref] = f"{item.asset_type} earnings revision for {item.symbol}"
    return dict(sorted(registry.items()))


def validate_gpt_task_evidence(
    tasks: list[GptAnalysisTask],
    registry: dict[str, str],
) -> None:
    task_ids = [task.task_id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("GPT task IDs must be unique")
    for task in tasks:
        if len(task.evidence_refs) != len(set(task.evidence_refs)):
            raise ValueError(f"GPT task {task.task_id} has duplicate Evidence Refs")
        missing = sorted(set(task.evidence_refs) - set(registry))
        if missing:
            raise ValueError(
                f"GPT task {task.task_id} has unresolved Evidence Refs: "
                + ", ".join(missing)
            )


def _allocations(
    values: dict[str, float],
    total: float,
    targets: dict[str, float],
) -> list[PortfolioAllocation]:
    result = []
    for symbol in sorted(set(values) | set(targets)):
        current_value = values.get(symbol, 0.0)
        current_weight = current_value / total if total else None
        target = targets.get(symbol)
        gap = (
            target - current_weight
            if target is not None and current_weight is not None
            else None
        )
        result.append(
            PortfolioAllocation(
                symbol,
                current_value,
                current_weight,
                target,
                gap,
                gap * total if gap is not None else None,
            )
        )
    return result


def _market_evidence(signal: PriceSignal) -> MarketEvidence:
    trend = _medium_term_trend(signal)
    short_term = _short_term_state(signal.return_5d, trend)
    return MarketEvidence(
        symbol=signal.symbol,
        latest=signal.latest,
        return_1d=signal.return_1d,
        return_5d=signal.return_5d,
        return_20d=signal.return_20d,
        medium_term_trend=trend,
        short_term_state=short_term,
        detection_reason=signal.reason,
        return_zscore=signal.absolute_move_z_score_60d,
        atr_multiple=signal.atr_multiple,
        historical_percentile=signal.absolute_move_percentile_252d,
        sma_50=signal.sma_50,
        sma_200=signal.sma_200,
        drawdown_from_high=signal.drawdown_from_252d_high,
        sma_50_slope_20d=signal.sma_50_slope_20d,
        evidence_ref=_evidence_ref(signal),
    )


def _medium_term_trend(signal: PriceSignal) -> str:
    if (
        signal.latest is None
        or signal.sma_50 is None
        or signal.sma_200 is None
    ):
        return "insufficient"
    if signal.latest > signal.sma_50 and signal.latest > signal.sma_200:
        return "medium_term_uptrend"
    if signal.latest < signal.sma_50 and signal.latest < signal.sma_200:
        return "medium_term_downtrend"
    return "mixed"


def _short_term_state(return_5d: float | None, trend: str) -> str:
    if return_5d is None:
        return "unknown"
    if return_5d >= 0.01 and trend == "medium_term_downtrend":
        return "countertrend_rebound"
    if return_5d <= -0.01 and trend == "medium_term_uptrend":
        return "countertrend_pullback"
    if return_5d >= 0.01:
        return "short_term_strength"
    if return_5d <= -0.01:
        return "short_term_weakness"
    return "flat"


def _signal_severity(signal: PriceSignal) -> float:
    return max(
        (signal.absolute_move_z_score_60d or 0) / 2.0,
        (signal.atr_multiple or 0) / 1.5,
        (signal.absolute_move_percentile_252d or 0) / 0.95,
    )


def _portfolio_snapshot_status(
    state: PortfolioReportState,
    report_date: date | None,
) -> str:
    if report_date is None:
        return "available"
    snapshots = [
        item.as_of_date for item in [*state.cash_positions, *state.holdings]
    ]
    if not snapshots:
        return "blocked"
    return (
        "stale"
        if any((report_date - snapshot).days > PORTFOLIO_STALE_DAYS for snapshot in snapshots)
        else "available"
    )


def _portfolio_freshness(
    state: PortfolioReportState,
    fx_signal: PriceSignal | None,
    report_date: date | None,
) -> PortfolioFreshness:
    return PortfolioFreshness(
        holdings=_freshness_layer(
            [item.as_of_date for item in state.holdings],
            report_date,
            PORTFOLIO_STALE_DAYS,
            "holdings",
        ),
        cash=_freshness_layer(
            [item.as_of_date for item in state.cash_positions],
            report_date,
            PORTFOLIO_STALE_DAYS,
            "cash",
        ),
        fx_market=_freshness_layer(
            [fx_signal.latest_date] if fx_signal and fx_signal.latest_date else [],
            report_date,
            FX_MARKET_STALE_DAYS,
            "fx_market",
        ),
    )


def _freshness_layer(
    dates: list[date],
    report_date: date | None,
    stale_after_days: int,
    name: str,
) -> FreshnessLayer:
    if not dates:
        return FreshnessLayer(
            "unavailable", None, None, None, stale_after_days,
            (f"{name}_snapshot_unavailable",),
        )
    latest = max(dates)
    oldest = min(dates)
    maximum_age = (
        max((report_date - item).days for item in dates)
        if report_date is not None
        else None
    )
    status = (
        "stale"
        if maximum_age is not None and maximum_age > stale_after_days
        else "available"
    )
    reasons = (f"{name}_snapshot_stale",) if status == "stale" else ()
    return FreshnessLayer(
        status, latest, oldest, maximum_age, stale_after_days, reasons
    )


def _combined_portfolio_freshness(freshness: PortfolioFreshness) -> str:
    statuses = {freshness.holdings.status, freshness.cash.status}
    if "unavailable" in statuses:
        return "unavailable"
    if "stale" in statuses:
        return "stale"
    return "available"


def _coverage_status(coverage_days: float | None) -> str:
    if coverage_days is None:
        return "unavailable"
    if coverage_days < 90:
        return "below_90_days"
    if coverage_days < 120:
        return "below_120_days"
    return "at_least_120_days"


def _overall_quality_status(rows: list[DataCoverageRow]) -> str:
    price_rows = [row for row in rows if row.category == "Prices"]
    failed_price_rows = [
        row for row in price_rows if row.status != "available"
    ]
    core_price_blocked = any(
        row.item == "SPY" and row.status in {"blocked", "missing", "error"}
        for row in price_rows
    )
    widespread_price_failure = bool(price_rows) and (
        len(failed_price_rows) >= max(3, (len(price_rows) + 1) // 2)
    )
    structural_failure = any(
        row.status in {"blocked", "error"}
        and (
            row.category.casefold() in {"schema", "time alignment"}
            or "schema" in row.detail.casefold()
            or "align" in row.detail.casefold()
        )
        for row in rows
    )
    if core_price_blocked or widespread_price_failure or structural_failure:
        return "blocked"
    if any(row.status != "available" for row in rows):
        return "degraded"
    return "available"


def _fx_rates(
    state: PortfolioReportState,
    base_currency: str,
    signals: dict[str, PriceSignal],
) -> dict[str, float]:
    rates = {base_currency: 1.0}
    usd_cnh = signals.get("USD/CNH")
    if base_currency == "CNY" and usd_cnh and usd_cnh.latest:
        rates["USD"] = usd_cnh.latest
    if base_currency == "CNY" and "USD" not in rates:
        conversions = [
            item for item in state.fx_conversions
            if item.sold_currency == "CNY" and item.bought_currency == "USD"
        ]
        if conversions:
            rates["USD"] = float(
                max(conversions, key=lambda item: item.fx_date).effective_rate
            )
    return rates


def _weighted_fx_cost_basis(
    state: PortfolioReportState | None,
) -> float | None:
    if state is None:
        return None
    total_cny_cost = 0.0
    total_usd_received = 0.0
    for conversion in state.fx_conversions:
        if not (
            conversion.sold_currency == "CNY"
            and conversion.bought_currency == "USD"
        ):
            continue
        cny_cost = float(conversion.sold_amount)
        usd_received = float(conversion.bought_amount)
        if conversion.fee_currency == "CNY":
            cny_cost += float(conversion.fee_amount)
        elif conversion.fee_currency == "USD":
            usd_received -= float(conversion.fee_amount)
        if usd_received <= 0:
            continue
        total_cny_cost += cny_cost
        total_usd_received += usd_received
    if total_usd_received == 0:
        return None
    return total_cny_cost / total_usd_received


def _spot_on_or_before(bars: list[PriceBar], target: date) -> float | None:
    eligible = [bar for bar in bars if bar.date <= target]
    return max(eligible, key=lambda bar: bar.date).close if eligible else None


def _level_percentile(bars: list[PriceBar]) -> float | None:
    if len(bars) < 20:
        return None
    ordered = sorted(bar.close for bar in bars[-252:])
    latest = bars[-1].close
    return sum(value <= latest for value in ordered) / len(ordered)


def _evidence_ref(signal: PriceSignal) -> str:
    observed = signal.latest_date.isoformat() if signal.latest_date else "N/A"
    return f"PRICE:{signal.symbol}:{observed}"


def _risk_level(score: int) -> str:
    return "high" if score >= 60 else "elevated" if score >= 30 else "low"


def _market_state_regime(
    macro_context: MacroContext | None,
    sector_rotation: SectorRotation,
) -> str:
    if macro_context is None:
        return "unknown"
    return macro_context.overall_regime


def _gpt_question_refs(
    question: str,
    market_refs: tuple[str, ...],
    evidence_by_symbol: dict[str, str],
) -> tuple[tuple[str, ...], str]:
    if any(term in question for term in ["目标仓位", "配置缺口", "买多少"]):
        return (
            (
                "STATE:MARKET",
                *market_refs,
                "STATE:PORTFOLIO",
                "PORTFOLIO:ALLOCATION",
                "STATE:ACTION_READINESS",
                "STATE:EXECUTION_READINESS",
            ),
            "portfolio_action",
        )
    if any(
        term in question
        for term in [
            "组合风险",
            "组合决策",
            "组合敞口",
            "因子敞口",
            "组合影响",
            "组合数据质量",
        ]
    ):
        return (
            tuple(
                dict.fromkeys(
                    [
                        "STATE:MARKET",
                        *market_refs,
                        "STATE:PORTFOLIO",
                        "DQ:PORTFOLIO:SNAPSHOT",
                        "DQ:PORTFOLIO:CASH_ROLES",
                        "PORTFOLIO:ALLOCATION",
                        "PORTFOLIO:FACTOR_IMPACT",
                    ]
                )
            ),
            "portfolio_analysis",
        )
    if any(term in question for term in ["换汇", "USD/CNH", "美元指数"]):
        fx_refs = [
            evidence_by_symbol[symbol]
            for symbol in ["USD/CNH", "DX-Y.NYB", "^TNX"]
            if symbol in evidence_by_symbol
        ]
        return (
            tuple(
                dict.fromkeys(
                    [
                        "STATE:MARKET",
                        *fx_refs,
                        "STATE:PORTFOLIO",
                        "PORTFOLIO:FX",
                    ]
                )
            ),
            "fx",
        )
    if any(term in question for term in ["新闻", "因果", "事件"]):
        return (
            (
                "STATE:MARKET",
                "STATE:PORTFOLIO",
                "PORTFOLIO:ALLOCATION",
                "FUNDAMENTAL:STATE",
            ),
            "external_research",
        )
    if any(term in question for term in ["估值", "盈利预期", "盈利修正"]):
        return (
            ("FUNDAMENTAL:STATE", "DQ:FUNDAMENTALS"),
            "fundamental",
        )
    return (
        tuple(dict.fromkeys(["STATE:MARKET", "BREADTH:MARKET", *market_refs])),
        "market",
    )


def _state_value(value) -> str:
    if isinstance(value, tuple):
        return ", ".join(value) if value else "none"
    return str(value)


def _format_percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _deduplicate_task_specs(
    values: list[tuple[str, str, tuple[str, ...], str, tuple[str, ...]]],
) -> list[tuple[str, str, tuple[str, ...], str, tuple[str, ...]]]:
    seen: set[str] = set()
    result = []
    for task_id, question, refs, status, blocked_reasons in values:
        if question not in seen:
            result.append((task_id, question, refs, status, blocked_reasons))
            seen.add(question)
    return result
