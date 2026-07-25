from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json

from app.config import ReportProfile
from app.models.analysis import (
    DataCoverage,
    DataCoverageRow,
    DailySignalSummary,
    FxCostComparison,
    GptAnalysisTask,
    MarketBreadth,
    MarketEvidence,
    MacroContext,
    NewsQualityGate,
    PortfolioAllocation,
    PortfolioSummary,
    PriceSignal,
    ReportState,
    RiskAssessment,
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
        )

    fx_rates = _fx_rates(portfolio_state, profile.base_currency, price_signals)
    values: dict[str, float] = {}
    notes = [
        "Current Allocation is the share of supplied invested holding cost; "
        "it is not an allocation of total liquid assets."
    ]
    for holding in portfolio_state.holdings:
        rate = fx_rates.get(holding.currency)
        if rate is None:
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
    cash_by_role = {"investable": 0.0, "reserved": 0.0, "unclassified": 0.0}
    for position in portfolio_state.cash_positions:
        rate = fx_rates.get(position.currency)
        if rate is not None:
            cash_by_role[position.cash_role] += float(position.balance) * rate

    usd_cash = sum(
        float(position.balance)
        for position in portfolio_state.cash_positions
        if position.currency == "USD" and position.cash_role == "investable"
    )
    coverage = (
        usd_cash / profile.usd_daily_spend
        if profile.usd_daily_spend and profile.usd_daily_spend > 0
        else None
    )
    snapshot_status = _portfolio_snapshot_status(portfolio_state, report_date)
    if not profile.target_allocations:
        notes.append("Target allocations are not configured.")
    if cash_by_role["unclassified"]:
        notes.append("Unclassified cash is excluded from investable cash.")
    return PortfolioSummary(
        base_currency=profile.base_currency,
        total_holding_cost=total,
        allocations=allocations,
        daily_investment_budget=profile.daily_investment_budget,
        usd_cash=usd_cash,
        usd_daily_spend=profile.usd_daily_spend,
        usd_coverage_days=coverage,
        investable_cash=cash_by_role["investable"],
        reserved_cash=cash_by_role["reserved"],
        unclassified_cash=cash_by_role["unclassified"],
        snapshot_status=snapshot_status,
        notes=_deduplicate(notes),
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
                f"{len(below_200)} configured assets have fewer than 200 rows.",
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
        unclassified = sum(
            position.cash_role == "unclassified"
            for position in portfolio_state.cash_positions
        )
        if unclassified:
            rows.append(
                DataCoverageRow(
                    "Portfolio",
                    "cash roles",
                    "degraded",
                    unclassified,
                    "N/A",
                    f"{unclassified} cash positions are unclassified.",
                )
            )
    status = _overall_quality_status(rows)
    impacts = [
        impact
        for impact in market_coverage.impacts
        if "No data coverage gaps" not in impact
    ]
    if status != "available":
        impacts.append(f"Overall report data quality is {status}.")
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
    for cluster, symbols in RISK_CLUSTERS.items():
        triggered = [
            signal for symbol, signal in price_signals.items()
            if symbol in symbols and signal.is_unusual_move
        ]
        if not triggered:
            continue
        severity = max(_signal_severity(signal) for signal in triggered)
        points = min(10, max(1, round(severity * 5)))
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
    cluster_points = sum(item.points for item in cluster_results)
    breadth_points = 0
    if breadth.above_50d_share is not None:
        breadth_points += round(max(0.0, 0.5 - breadth.above_50d_share) * 20)
    if breadth.above_200d_share is not None:
        breadth_points += round(max(0.0, 0.5 - breadth.above_200d_share) * 20)
    breadth_points = min(15, breadth_points)
    vix_points = 0
    if breadth.vix_level is not None:
        vix_points = 15 if breadth.vix_level >= 30 else 8 if breadth.vix_level >= 20 else 0
    if breadth.vix_percentile is not None and breadth.vix_percentile >= 0.90:
        vix_points = max(vix_points, 12)
    score = min(100, cluster_points + breadth_points + vix_points)
    explanations = [
        f"Unusual-move risk: {len(cluster_results)} risk clusters, "
        f"{cluster_points} points; correlated assets count once per cluster.",
        f"Tracked-universe breadth: {breadth_points} points.",
        f"VIX level/percentile: {vix_points} points.",
        f"Total market risk: {score}/100.",
    ]
    return RiskAssessment(
        score=score,
        level=_risk_level(score),
        explanations=explanations,
        scope="market",
        clusters=cluster_results,
    )


def assess_portfolio_risk(summary: PortfolioSummary) -> RiskAssessment:
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
    stale_points = 25 if summary.snapshot_status == "stale" else 0
    unclassified_points = 20 if (summary.unclassified_cash or 0) > 0 else 0
    coverage_points = (
        15
        if summary.usd_coverage_days is not None
        and summary.usd_coverage_days < 90
        else 8
        if summary.usd_coverage_days is not None
        and summary.usd_coverage_days < 120
        else 0
    )
    score = min(
        100,
        gap_points + concentration_points + stale_points
        + unclassified_points + coverage_points,
    )
    return RiskAssessment(
        score=score,
        level=_risk_level(score),
        scope="portfolio",
        explanations=[
            f"Target-allocation gap: {gap_points} points.",
            f"Invested-holdings concentration: {concentration_points} points.",
            f"Stale portfolio snapshots: {stale_points} points.",
            f"Unclassified cash: {unclassified_points} points.",
            f"USD coverage: {coverage_points} points.",
            f"Total portfolio risk: {score}/100.",
        ],
    )


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


def evaluate_strategy_rules(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    data_coverage: DataCoverage | None,
    portfolio_summary: PortfolioSummary,
    evidence: list[MarketEvidence],
) -> list[StrategyRuleResult]:
    results: list[StrategyRuleResult] = []
    if data_coverage is None or data_coverage.status != "available":
        results.append(
            StrategyRuleResult(
                "Data quality circuit breaker",
                "triggered",
                data_coverage.status if data_coverage else "unavailable",
                "Overall quality != available",
                "A required report module is blocked, stale, or degraded.",
                evidence_refs=("DQ:OVERALL",),
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
        results.append(
            StrategyRuleResult(
                f"Unusual move cluster: {cluster}",
                "triggered",
                ", ".join(sorted(signal.symbol for signal in triggered)),
                "z ≥ 2.0, ATR ≥ 1.5x, or percentile ≥ 95%",
                strongest.reason,
                return_zscore=strongest.return_zscore_60d,
                atr_multiple=strongest.atr_multiple,
                historical_percentile=strongest.historical_percentile,
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
    daily_signal_summary: DailySignalSummary | None,
    data_coverage: DataCoverage | None,
    macro_context: MacroContext | None,
    market_risk: RiskAssessment,
    portfolio_risk: RiskAssessment,
    rules: list[StrategyRuleResult],
    evidence: list[MarketEvidence],
    portfolio: PortfolioSummary,
) -> ReportState:
    return ReportState(
        executive_status=(
            daily_signal_summary.status if daily_signal_summary else "not_available"
        ),
        data_quality_status=(
            data_coverage.status if data_coverage else "unavailable"
        ),
        macro_regime=(
            macro_context.overall_regime if macro_context else "unavailable"
        ),
        market_risk_score=market_risk.score,
        market_risk_level=market_risk.level,
        portfolio_risk_score=portfolio_risk.score,
        portfolio_risk_level=portfolio_risk.level,
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
    )


def serialize_report_state(state: ReportState) -> str:
    return (
        REPORT_STATE_PREFIX
        + json.dumps(asdict(state), ensure_ascii=False, sort_keys=True)
        + REPORT_STATE_SUFFIX
    )


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
            executive_status=data["executive_status"],
            data_quality_status=data["data_quality_status"],
            macro_regime=data["macro_regime"],
            market_risk_score=int(
                data.get("market_risk_score", data.get("risk_score", 0))
            ),
            market_risk_level=data.get(
                "market_risk_level", data.get("risk_level", "unknown")
            ),
            portfolio_risk_score=int(data.get("portfolio_risk_score", 0)),
            portfolio_risk_level=data.get("portfolio_risk_level", "unknown"),
            triggered_rules=tuple(data["triggered_rules"]),
            medium_term_trends=tuple(
                _normalize_legacy_trend(value)
                for value in data.get(
                    "medium_term_trends",
                    data.get("structural_trends", []),
                )
            ),
            portfolio_gaps=tuple(data["portfolio_gaps"]),
        )
    return None


def _normalize_legacy_trend(value: str) -> str:
    return (
        value.replace("structural_uptrend", "legacy_uptrend")
        .replace("structural_downtrend", "legacy_downtrend")
    )


def compare_report_states(
    previous: ReportState | None,
    current: ReportState,
) -> list[str]:
    if previous is None:
        return ["Baseline created; no previous comparable report state was found."]
    labels = {
        "executive_status": "Executive status",
        "data_quality_status": "Data quality",
        "macro_regime": "Macro regime",
        "market_risk_score": "Market risk score",
        "market_risk_level": "Market risk level",
        "portfolio_risk_score": "Portfolio risk score",
        "portfolio_risk_level": "Portfolio risk level",
        "triggered_rules": "Triggered/near rules",
        "medium_term_trends": "Medium-term trends",
        "portfolio_gaps": "Portfolio target gaps",
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
) -> list[GptAnalysisTask]:
    refs = tuple(row.evidence_ref for row in evidence[:6])
    questions: list[tuple[str, tuple[str, ...]]] = []
    if any("Baseline created" not in item and "No state changes" not in item for item in changes):
        questions.append(
            ("哪些状态变化最重要，它们是否改变此前判断？", ("STATE:CHANGES",))
        )
    if rules:
        questions.append(
            (
                "如何解释已触发或接近触发的规则，并识别共同风险簇？",
                tuple(dict.fromkeys(
                    ref for rule in rules for ref in rule.evidence_refs
                )),
            )
        )
    questions.extend((question, refs) for question in profile.gpt_questions)
    expected = (
        "Conclusion; supporting evidence; counterevidence; confidence; "
        "confirmation conditions; invalidation conditions."
    )
    return [
        GptAnalysisTask(question, evidence_refs, expected, "State confidence as low/medium/high.")
        for question, evidence_refs in _deduplicate_pairs(questions)[:6]
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
        return_zscore=signal.return_zscore_60d,
        atr_multiple=signal.atr_multiple,
        historical_percentile=signal.historical_percentile,
        sma_50=signal.sma_50,
        sma_200=signal.sma_200,
        drawdown_from_high=signal.drawdown_from_high,
        evidence_ref=_evidence_ref(signal),
    )


def _medium_term_trend(signal: PriceSignal) -> str:
    if signal.latest is None or signal.sma_50 is None:
        return "insufficient"
    if signal.sma_200 is None:
        return "above_50d" if signal.latest >= signal.sma_50 else "below_50d"
    if signal.latest >= signal.sma_50 >= signal.sma_200:
        return "medium_term_uptrend"
    if signal.latest <= signal.sma_50 <= signal.sma_200:
        return "medium_term_downtrend"
    return "mixed"


def _short_term_state(return_5d: float | None, trend: str) -> str:
    if return_5d is None:
        return "unknown"
    if return_5d >= 0.01 and trend in {"medium_term_downtrend", "below_50d"}:
        return "countertrend_rebound"
    if return_5d <= -0.01 and trend in {"medium_term_uptrend", "above_50d"}:
        return "countertrend_pullback"
    if return_5d >= 0.01:
        return "short_term_strength"
    if return_5d <= -0.01:
        return "short_term_weakness"
    return "flat"


def _signal_severity(signal: PriceSignal) -> float:
    return max(
        (signal.return_zscore_60d or 0) / 2.0,
        (signal.atr_multiple or 0) / 1.5,
        (signal.historical_percentile or 0) / 0.95,
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
    statuses = {row.status for row in rows}
    if "blocked" in statuses:
        return "blocked"
    if "stale" in statuses:
        return "stale"
    if any(status != "available" for status in statuses):
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


def _state_value(value) -> str:
    if isinstance(value, tuple):
        return ", ".join(value) if value else "none"
    return str(value)


def _format_percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _deduplicate_pairs(
    values: list[tuple[str, tuple[str, ...]]],
) -> list[tuple[str, tuple[str, ...]]]:
    seen: set[str] = set()
    result = []
    for question, refs in values:
        if question not in seen:
            result.append((question, refs))
            seen.add(question)
    return result
