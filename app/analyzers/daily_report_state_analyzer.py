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
    FxCostComparison,
    FxState,
    GptAnalysisTask,
    MarketBreadth,
    MarketEvidence,
    MarketState,
    MacroContext,
    NewsQualityGate,
    NewsState,
    PortfolioAllocation,
    PortfolioAllocationView,
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
)
from app.models.price import PriceBar
from app.steward.models import PortfolioReportState


REPORT_STATE_PREFIX = "<!-- report-state: "
REPORT_STATE_SUFFIX = " -->"
KEY_EVIDENCE_LIMIT = 10
PORTFOLIO_STALE_DAYS = 3

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
    snapshot_status = _portfolio_snapshot_status(portfolio_state, report_date)
    if not profile.target_allocations:
        notes.append("Target allocations are not configured.")
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
    )


def combine_data_quality(
    market_coverage: DataCoverage,
    news_quality: NewsQualityGate | None,
    portfolio_state: PortfolioReportState | None,
    report_date: date,
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
    if portfolio_state is None:
        rows.append(
            DataCoverageRow(
                "Portfolio", "state", "blocked", 0, "N/A",
                "Portfolio state was not supplied.",
            )
        )
    else:
        snapshot_status = _portfolio_snapshot_status(portfolio_state, report_date)
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
                snapshot_status,
                len(snapshot_dates),
                max(snapshot_dates).isoformat() if snapshot_dates else "N/A",
                f"Snapshots older than {PORTFOLIO_STALE_DAYS} days are stale.",
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
            cluster_results.append(
                RiskClusterAssessment(
                    cluster=cluster,
                    symbols=tuple(sorted(signal.symbol for signal in triggered)),
                    severity=severity,
                    points=points,
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
                    points=points,
                    evidence_ref=_evidence_ref(signal),
                )
            )
    unusual_move_points = sum(item.points for item in cluster_results) + sum(
        item.points for item in single_asset_alerts
    )
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
    score = min(100, unusual_move_points + breadth_points + vix_points)
    explanations = [
        f"Unusual-move risk: {len(single_asset_alerts)} single-asset alerts and "
        f"{len(cluster_results)} correlated clusters, {unusual_move_points} "
        "points; correlated assets count once per cluster.",
        f"Tracked-universe breadth: {breadth_points} points.",
        f"VIX level/252D level percentile: {vix_points} points.",
        f"Total market risk: {score}/100.",
    ]
    return RiskAssessment(
        score=score,
        level=_risk_level(score),
        explanations=explanations,
        scope="market",
        clusters=cluster_results,
        single_asset_alerts=single_asset_alerts,
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
    if summary.snapshot_status in {"stale", "unavailable"}:
        readiness_reasons.append(
            "portfolio snapshots are unavailable"
            if summary.snapshot_status == "unavailable"
            else "portfolio snapshots are stale"
        )
    if (summary.unknown_cash or 0) > 0:
        readiness_reasons.append("cash roles are unknown")
    return PortfolioRiskAssessment(
        exposure_risk=RiskAssessment(
            score=exposure_score,
            level=_risk_level(exposure_score),
            scope="portfolio_exposure",
            explanations=[
            f"Target-allocation gap: {gap_points} points.",
            f"Invested-holdings concentration: {concentration_points} points.",
                f"USD coverage: {coverage_points} points.",
                f"Total portfolio exposure risk: {exposure_score}/100.",
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

    news_blocked = (
        news_quality is None
        or news_quality.status in {"disabled", "data_quality_review"}
    )
    news_state = NewsState(
        quality="blocked" if news_blocked else "available",
        actionability="unavailable" if news_blocked else "available",
        reason=(
            "; ".join(news_quality.reasons)
            if news_quality is not None and news_quality.reasons
            else (
                "News evidence is not available."
                if news_blocked
                else "News evidence passed its quality gate."
            )
        ),
    )
    news_reasons = (
        tuple(news_quality.reasons)
        if news_quality is not None and news_quality.reasons
        else ("news evidence is unavailable",)
        if news_blocked
        else ()
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
            "blocked" if news_blocked else "available",
            news_reasons,
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
    status = (
        "blocked"
        if portfolio_state is None or cost_basis is None
        else "degraded"
        if spot is None
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
    if use_states.news.actionability != "available":
        results.append(
            StrategyRuleResult(
                "News causal-analysis availability gate",
                "triggered",
                use_states.news.actionability,
                "News quality and actionability must be available",
                use_states.news.reason,
                evidence_refs=("STATE:NEWS", "DQ:NEWS"),
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
        portfolio_exposure_risk_score=portfolio_decision_risk.exposure_risk.score,
        portfolio_exposure_risk_level=portfolio_decision_risk.exposure_risk.level,
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
            portfolio_exposure_risk_score=int(
                data.get(
                    "portfolio_exposure_risk_score",
                    data.get("portfolio_decision_risk_score", 0),
                )
            ),
            portfolio_exposure_risk_level=data.get(
                "portfolio_exposure_risk_level",
                data.get("portfolio_decision_risk_level", "unknown"),
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
        "portfolio_exposure_risk_score": "Portfolio exposure risk score",
        "portfolio_exposure_risk_level": "Portfolio exposure risk level",
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
    }
    changes = [
        f"{label}: {_state_value(getattr(previous, field))} → "
        f"{_state_value(getattr(current, field))}."
        for field, label in labels.items()
        if getattr(previous, field) != getattr(current, field)
    ]
    return changes or ["No state changes detected."]


def build_gpt_tasks(
    profile: ReportProfile,
    changes: list[str],
    rules: list[StrategyRuleResult],
    evidence: list[MarketEvidence],
    use_states: ReportUseStates,
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
    for index, question in enumerate(profile.gpt_questions, 1):
        refs, required_state = _gpt_question_refs(
            question,
            market_refs,
            evidence_by_symbol,
        )
        blocked_reasons: list[str] = []
        status = "ready"
        capability = None
        if use_states.data_quality is not None:
            capabilities = use_states.data_quality.capabilities
            capability = {
                "portfolio": capabilities.investment_action,
                "news": capabilities.news_analysis,
                "market": capabilities.market_analysis,
                "fx": capabilities.fx_analysis,
            }.get(required_state)
        if capability is not None and capability.status != "available":
            status = (
                "blocked"
                if capability.status in {"blocked", "unavailable"}
                else "degraded"
            )
            blocked_reasons.extend(capability.reasons)
        elif (
            required_state == "portfolio"
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
            blocked_reasons.append("Target allocations are not configured.")
        task_id = (
            "evaluate_allocation_gap"
            if any(term in question for term in ["目标仓位", "配置缺口"])
            else f"profile_question_{index}_{required_state}"
        )
        questions.append(
            (task_id, question, refs, status, tuple(blocked_reasons))
        )

    available_output = (
        "Conclusion; supporting evidence linked by ref; counterevidence; "
        "confidence; confirmation conditions; invalidation conditions."
    )
    blocked_output = (
        "State that the task is blocked; list missing or stale inputs by evidence "
        "ref; do not infer a decision; specify what would unblock the task."
    )
    return [
        GptAnalysisTask(
            question=question,
            evidence_refs=evidence_refs,
            expected_output=(
                blocked_output if status == "blocked" else available_output
            ),
            confidence_requirement=(
                "Do not assign confidence while blocked."
                if status == "blocked"
                else "State confidence as low/medium and name degraded inputs."
                if status == "degraded"
                else "State confidence as low/medium/high."
            ),
            task_id=task_id,
            status=status,
            blocked_reasons=blocked_reasons,
        )
        for task_id, question, evidence_refs, status, blocked_reasons
        in _deduplicate_task_specs(questions)[:6]
    ]


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
    has_rotation = bool(
        sector_rotation.strong_sectors or sector_rotation.weak_sectors
    )
    if macro_context.rates_context == "rates_pressure" and has_rotation:
        return "rotation_under_rate_pressure"
    if macro_context.rates_context == "duration_supported" and has_rotation:
        return "rotation_with_duration_support"
    return macro_context.overall_regime


def _gpt_question_refs(
    question: str,
    market_refs: tuple[str, ...],
    evidence_by_symbol: dict[str, str],
) -> tuple[tuple[str, ...], str]:
    if any(
        term in question
        for term in [
            "目标仓位",
            "配置缺口",
            "组合风险",
            "组合决策",
            "组合敞口",
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
                    ]
                )
            ),
            "portfolio",
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
        return (("STATE:NEWS", "DQ:NEWS"), "news")
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
