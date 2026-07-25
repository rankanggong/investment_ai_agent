from __future__ import annotations

from dataclasses import asdict
import json

from app.config import ReportProfile
from app.models.analysis import (
    DataCoverage,
    DailySignalSummary,
    MarketEvidence,
    MacroContext,
    PortfolioAllocation,
    PortfolioSummary,
    PriceSignal,
    ReportState,
    RiskAssessment,
    SectorRotation,
    StrategyRuleResult,
)
from app.steward.models import PortfolioReportState


REPORT_STATE_PREFIX = "<!-- report-state: "
REPORT_STATE_SUFFIX = " -->"
KEY_EVIDENCE_LIMIT = 10
_CORE_EVIDENCE = [
    "SPY",
    "QQQ",
    "GLD",
    "^TNX",
    "DX-Y.NYB",
    "USD/CNH",
    "TLT",
    "HYG",
    "LQD",
]


def analyze_portfolio_summary(
    portfolio_state: PortfolioReportState | None,
    profile: ReportProfile,
    price_signals: dict[str, PriceSignal],
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
            notes=["No portfolio state was supplied."],
        )

    fx_rates = _fx_rates(portfolio_state, profile.base_currency, price_signals)
    values: dict[str, float] = {}
    notes: list[str] = [
        "Current allocation uses supplied holding cost, not live market value."
    ]
    for holding in portfolio_state.holdings:
        rate = fx_rates.get(holding.currency)
        if rate is None:
            notes.append(
                f"{holding.symbol} omitted from aggregation: no "
                f"{holding.currency}/{profile.base_currency} conversion rate."
            )
            continue
        values[holding.symbol] = values.get(holding.symbol, 0.0) + (
            float(holding.total_cost) * rate
        )

    total = sum(values.values())
    symbols = sorted(set(values) | set(profile.target_allocations))
    allocations: list[PortfolioAllocation] = []
    for symbol in symbols:
        current_value = values.get(symbol, 0.0)
        current_weight = current_value / total if total else None
        target_weight = profile.target_allocations.get(symbol)
        weight_gap = (
            target_weight - current_weight
            if target_weight is not None and current_weight is not None
            else None
        )
        allocations.append(
            PortfolioAllocation(
                symbol=symbol,
                current_value=current_value,
                current_weight=current_weight,
                target_weight=target_weight,
                weight_gap=weight_gap,
                target_value_gap=weight_gap * total
                if weight_gap is not None
                else None,
            )
        )

    if not profile.target_allocations:
        notes.append(
            "Target allocations are not configured in config/report_profile.json."
        )
    usd_cash = sum(
        float(position.balance)
        for position in portfolio_state.cash_positions
        if position.currency == "USD"
    )
    coverage_days = (
        usd_cash / profile.usd_daily_spend
        if profile.usd_daily_spend is not None and profile.usd_daily_spend > 0
        else None
    )
    if profile.daily_investment_budget is None:
        notes.append("Daily investment budget is not configured.")
    if profile.usd_daily_spend is None:
        notes.append("USD daily spend is not configured; coverage days are unavailable.")

    return PortfolioSummary(
        base_currency=profile.base_currency,
        total_holding_cost=total,
        allocations=allocations,
        daily_investment_budget=profile.daily_investment_budget,
        usd_cash=usd_cash,
        usd_daily_spend=profile.usd_daily_spend,
        usd_coverage_days=coverage_days,
        notes=_deduplicate(notes),
    )


def select_key_market_evidence(
    price_signals: dict[str, PriceSignal],
) -> list[MarketEvidence]:
    selected: list[str] = [
        symbol for symbol in _CORE_EVIDENCE if symbol in price_signals
    ]
    remaining = sorted(
        (
            signal
            for symbol, signal in price_signals.items()
            if symbol not in selected
        ),
        key=lambda signal: (
            signal.is_unusual_move,
            abs(signal.return_1d or 0.0),
            abs(signal.return_5d or 0.0),
        ),
        reverse=True,
    )
    selected.extend(
        signal.symbol
        for signal in remaining[: max(0, KEY_EVIDENCE_LIMIT - len(selected))]
    )
    return [_market_evidence(price_signals[symbol]) for symbol in selected]


def assess_risk(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    data_coverage: DataCoverage | None,
) -> RiskAssessment:
    unusual_count = sum(
        signal.is_unusual_move for signal in price_signals.values()
    )
    unusual_points = min(30, unusual_count * 3)
    quality_points = (
        20
        if data_coverage is None or data_coverage.status != "available"
        else 0
    )
    sector_points = round(max(0.0, -sector_rotation.risk_on_score) * 20)
    spy = price_signals.get("SPY")
    spy_return_5d = spy.return_5d if spy is not None else None
    market_points = round(
        min(20.0, max(0.0, -(spy_return_5d or 0.0) * 400))
    )
    macro_points = (
        20
        if macro_context is not None
        and macro_context.overall_regime == "risk_off_with_macro_pressure"
        else 0
    )
    score = min(
        100,
        unusual_points
        + quality_points
        + sector_points
        + market_points
        + macro_points,
    )
    level = "high" if score >= 60 else "elevated" if score >= 30 else "low"
    explanations = [
        f"Unusual moves: {unusual_count} × 3 points, capped at 30 = {unusual_points}.",
        f"Data-quality penalty: {quality_points} points.",
        (
            "Negative sector-rotation contribution: "
            f"{sector_points} points from risk-on score "
            f"{sector_rotation.risk_on_score:.2f}."
        ),
        (
            "SPY 5D drawdown contribution: "
            f"{market_points} points from {_format_percent(spy_return_5d)}."
        ),
        f"Confirmed risk-off macro regime: {macro_points} points.",
        f"Total: {score}/100; 0–29 low, 30–59 elevated, 60–100 high.",
    ]
    return RiskAssessment(score=score, level=level, explanations=explanations)


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
                name="Data quality circuit breaker",
                status="triggered",
                observed=data_coverage.status if data_coverage else "unavailable",
                threshold="Any missing, stale, insufficient, or blocked module",
                reason="Incomplete inputs block confident downstream interpretation.",
            )
        )

    unusual_count = sum(
        signal.is_unusual_move for signal in price_signals.values()
    )
    if unusual_count:
        results.append(
            StrategyRuleResult(
                name="Unusual price move review",
                status="triggered",
                observed=f"{unusual_count} assets",
                threshold="At least one deterministic price/volume trigger",
                reason="One or more assets crossed the existing move detector.",
            )
        )

    sector_magnitude = abs(sector_rotation.risk_on_score)
    if sector_magnitude >= 0.35:
        status = "triggered"
    elif sector_magnitude >= 0.28:
        status = "near"
    else:
        status = ""
    if status:
        results.append(
            StrategyRuleResult(
                name="Sector rotation monitor",
                status=status,
                observed=f"{sector_rotation.risk_on_score:.2f}",
                threshold="Absolute risk-on score ≥ 0.35; near at ≥ 0.28",
                reason="Sector leadership is moving toward a regime boundary.",
            )
        )

    if macro_context is not None and macro_context.overall_regime not in {
        "mixed",
        "unknown",
    }:
        results.append(
            StrategyRuleResult(
                name="Macro regime confirmation",
                status="triggered",
                observed=macro_context.overall_regime,
                threshold="Deterministic regime is neither mixed nor unknown",
                reason="Rates, USD, credit, and equity evidence align.",
            )
        )

    gaps = [
        abs(row.weight_gap)
        for row in portfolio_summary.allocations
        if row.weight_gap is not None
    ]
    if gaps:
        maximum_gap = max(gaps)
        if maximum_gap >= 0.05:
            status = "triggered"
        elif maximum_gap >= 0.04:
            status = "near"
        else:
            status = ""
        if status:
            results.append(
                StrategyRuleResult(
                    name="Target allocation drift",
                    status=status,
                    observed=_format_percent(maximum_gap),
                    threshold="Absolute target gap ≥ 5%; near at ≥ 4%",
                    reason="At least one configured allocation is outside its review band.",
                )
            )

    if portfolio_summary.usd_coverage_days is not None:
        days = portfolio_summary.usd_coverage_days
        status = "triggered" if days < 90 else "near" if days < 120 else ""
        if status:
            results.append(
                StrategyRuleResult(
                    name="USD coverage review",
                    status=status,
                    observed=f"{days:.1f} days",
                    threshold="< 90 days; near below 120 days",
                    reason="Supplied USD cash is close to or below the coverage band.",
                )
            )

    divergences = [
        row.symbol
        for row in evidence
        if row.short_term_state in {"countertrend_rebound", "countertrend_pullback"}
    ]
    if divergences:
        results.append(
            StrategyRuleResult(
                name="Structural/short-term divergence",
                status="triggered",
                observed=", ".join(divergences),
                threshold="5D direction opposes the 20D structural trend",
                reason="Short-term movement has not yet changed the structural trend.",
            )
        )
    return results


def build_report_state(
    daily_signal_summary: DailySignalSummary | None,
    data_coverage: DataCoverage | None,
    macro_context: MacroContext | None,
    risk: RiskAssessment,
    rules: list[StrategyRuleResult],
    evidence: list[MarketEvidence],
    portfolio: PortfolioSummary,
) -> ReportState:
    return ReportState(
        executive_status=(
            daily_signal_summary.status
            if daily_signal_summary is not None
            else "not_available"
        ),
        data_quality_status=(
            data_coverage.status if data_coverage is not None else "unavailable"
        ),
        macro_regime=(
            macro_context.overall_regime
            if macro_context is not None
            else "unavailable"
        ),
        risk_score=risk.score,
        risk_level=risk.level,
        triggered_rules=tuple(
            sorted(f"{rule.name}:{rule.status}" for rule in rules)
        ),
        structural_trends=tuple(
            sorted(f"{row.symbol}:{row.structural_trend}" for row in evidence)
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
        if line.startswith(REPORT_STATE_PREFIX) and line.endswith(
            REPORT_STATE_SUFFIX
        ):
            payload = line[len(REPORT_STATE_PREFIX) : -len(REPORT_STATE_SUFFIX)]
            data = json.loads(payload)
            return ReportState(
                executive_status=data["executive_status"],
                data_quality_status=data["data_quality_status"],
                macro_regime=data["macro_regime"],
                risk_score=int(data["risk_score"]),
                risk_level=data["risk_level"],
                triggered_rules=tuple(data["triggered_rules"]),
                structural_trends=tuple(data["structural_trends"]),
                portfolio_gaps=tuple(data["portfolio_gaps"]),
            )
    return None


def compare_report_states(
    previous: ReportState | None,
    current: ReportState,
) -> list[str]:
    if previous is None:
        return ["Baseline created; no previous comparable report state was found."]
    changes: list[str] = []
    labels = {
        "executive_status": "Executive status",
        "data_quality_status": "Data quality",
        "macro_regime": "Macro regime",
        "risk_score": "Risk score",
        "risk_level": "Risk level",
        "triggered_rules": "Triggered/near rules",
        "structural_trends": "Structural trends",
        "portfolio_gaps": "Portfolio target gaps",
    }
    for field_name, label in labels.items():
        old = getattr(previous, field_name)
        new = getattr(current, field_name)
        if old != new:
            changes.append(f"{label}: {_state_value(old)} → {_state_value(new)}.")
    return changes or ["No state changes detected."]


def build_gpt_questions(
    profile: ReportProfile,
    changes: list[str],
    rules: list[StrategyRuleResult],
    evidence: list[MarketEvidence],
) -> list[str]:
    questions: list[str] = []
    if any("Baseline created" not in change and "No state changes" not in change for change in changes):
        questions.append(
            "哪些新增状态变化最重要，它们是否改变了此前的核心判断？"
        )
    if rules:
        names = "、".join(rule.name for rule in rules[:4])
        questions.append(f"如何解释已触发或接近触发的规则（{names}）？")
    divergences = [
        row.symbol
        for row in evidence
        if row.short_term_state in {"countertrend_rebound", "countertrend_pullback"}
    ]
    if divergences:
        questions.append(
            f"{'、'.join(divergences)} 的短期走势与结构趋势背离，确认与失效条件是什么？"
        )
    questions.extend(profile.gpt_questions)
    return _deduplicate(questions)[:6]


def _market_evidence(signal: PriceSignal) -> MarketEvidence:
    structural = _structural_trend(signal.return_20d)
    short_term = _short_term_state(signal.return_5d, signal.return_20d)
    reason = signal.reason or _trend_detection_reason(structural, short_term)
    return MarketEvidence(
        symbol=signal.symbol,
        latest=signal.latest,
        return_1d=signal.return_1d,
        return_5d=signal.return_5d,
        return_20d=signal.return_20d,
        structural_trend=structural,
        short_term_state=short_term,
        detection_reason=reason,
    )


def _structural_trend(return_20d: float | None) -> str:
    if return_20d is None:
        return "unknown"
    if return_20d >= 0.03:
        return "structural_uptrend"
    if return_20d <= -0.03:
        return "structural_downtrend"
    return "range"


def _short_term_state(
    return_5d: float | None,
    return_20d: float | None,
) -> str:
    if return_5d is None or return_20d is None:
        return "unknown"
    if return_5d >= 0.01 and return_20d <= -0.03:
        return "countertrend_rebound"
    if return_5d <= -0.01 and return_20d >= 0.03:
        return "countertrend_pullback"
    if return_5d >= 0.01:
        return "short_term_strength"
    if return_5d <= -0.01:
        return "short_term_weakness"
    return "flat"


def _trend_detection_reason(structural: str, short_term: str) -> str:
    return f"20D={structural}; 5D={short_term}"


def _fx_rates(
    portfolio_state: PortfolioReportState,
    base_currency: str,
    price_signals: dict[str, PriceSignal],
) -> dict[str, float]:
    rates = {base_currency: 1.0}
    usd_cnh = price_signals.get("USD/CNH")
    if base_currency == "CNY" and usd_cnh and usd_cnh.latest:
        rates["USD"] = usd_cnh.latest
    if "USD" not in rates and base_currency == "CNY":
        conversions = [
            conversion
            for conversion in portfolio_state.fx_conversions
            if conversion.sold_currency == "CNY"
            and conversion.bought_currency == "USD"
        ]
        if conversions:
            latest = max(conversions, key=lambda item: item.fx_date)
            rates["USD"] = float(latest.effective_rate)
    return rates


def _state_value(value) -> str:
    if isinstance(value, tuple):
        return ", ".join(value) if value else "none"
    return str(value)


def _format_percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2%}"


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
