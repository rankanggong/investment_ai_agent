from datetime import date
from decimal import Decimal

from app.analyzers.daily_report_state_analyzer import (
    analyze_portfolio_summary,
    build_report_state,
    compare_report_states,
    evaluate_strategy_rules,
    extract_report_state,
    select_key_market_evidence,
    serialize_report_state,
)
from app.config import ReportProfile
from app.models.analysis import (
    DataCoverage,
    DataCoverageRow,
    DailySignalSummary,
    MacroContext,
    PriceSignal,
    RiskAssessment,
    SectorRotation,
)
from app.steward.models import CashPosition, HoldingPosition, PortfolioReportState


def signal(
    symbol: str,
    return_5d: float,
    return_20d: float,
    *,
    latest: float = 100.0,
    unusual: bool = False,
) -> PriceSignal:
    return PriceSignal(
        symbol=symbol,
        return_1d=0.01,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=1.0,
        volatility_zscore=0.0,
        is_unusual_move=unusual,
        reason="threshold crossed" if unusual else "",
        latest=latest,
        latest_date=date(2026, 7, 23),
    )


def test_portfolio_summary_aggregates_cost_and_computes_target_gap_and_coverage():
    state = PortfolioReportState(
        holdings=[
            HoldingPosition(
                "broker",
                "cny",
                "QQQ",
                "QQQ fund",
                Decimal("10"),
                "CNY",
                Decimal("100"),
                date(2026, 7, 23),
            ),
            HoldingPosition(
                "broker",
                "usd",
                "VOO",
                "VOO fund",
                Decimal("10"),
                "USD",
                Decimal("10"),
                date(2026, 7, 23),
            ),
        ],
        fx_conversions=[],
        cash_positions=[
            CashPosition(
                "bank",
                "usd",
                "USD",
                Decimal("1200"),
                date(2026, 7, 23),
            )
        ],
    )
    profile = ReportProfile(
        base_currency="CNY",
        target_allocations={"QQQ": 0.5, "VOO": 0.5},
        daily_investment_budget=100.0,
        usd_daily_spend=10.0,
    )

    result = analyze_portfolio_summary(
        state,
        profile,
        {"USD/CNH": signal("USD/CNH", 0.0, 0.0, latest=7.0)},
    )

    assert result.total_holding_cost == 1700.0
    assert result.usd_coverage_days == 120.0
    qqq = next(row for row in result.allocations if row.symbol == "QQQ")
    assert round(qqq.current_weight or 0, 4) == 0.5882
    assert round(qqq.weight_gap or 0, 4) == -0.0882
    assert round(qqq.target_value_gap or 0, 2) == -150.0


def test_key_evidence_limits_rows_and_separates_countertrend_rebound():
    signals = {
        f"X{index}": signal(
            f"X{index}",
            0.04 if index == 0 else 0.0,
            -0.08 if index == 0 else 0.0,
            unusual=index > 5,
        )
        for index in range(14)
    }

    result = select_key_market_evidence(signals)

    assert len(result) == 10
    x0 = next(row for row in result if row.symbol == "X0")
    assert x0.structural_trend == "structural_downtrend"
    assert x0.short_term_state == "countertrend_rebound"


def test_strategy_rules_only_return_triggered_or_near_rules():
    coverage = DataCoverage(
        rows=[DataCoverageRow("Macro", "^TNX", "missing", 0, "N/A", "Missing.")],
        impacts=[],
    )
    rotation = SectorRotation([], [], 0.30, "mixed", "mixed", [])
    signals = {"QQQ": signal("QQQ", 0.04, -0.08, unusual=True)}
    evidence = select_key_market_evidence(signals)
    portfolio = analyze_portfolio_summary(None, ReportProfile(), signals)

    rules = evaluate_strategy_rules(
        signals,
        rotation,
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        coverage,
        portfolio,
        evidence,
    )

    statuses = {rule.name: rule.status for rule in rules}
    assert statuses == {
        "Data quality circuit breaker": "triggered",
        "Unusual price move review": "triggered",
        "Sector rotation monitor": "near",
        "Structural/short-term divergence": "triggered",
    }


def test_report_state_round_trips_and_only_reports_changed_fields():
    summary = DailySignalSummary("monitor", [], "Monitor.")
    coverage = DataCoverage([], [], status="available")
    macro = MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", [])
    risk = RiskAssessment(20, "low", [])
    portfolio = analyze_portfolio_summary(None, ReportProfile(), {})
    old = build_report_state(summary, coverage, macro, risk, [], [], portfolio)
    restored = extract_report_state(serialize_report_state(old))

    new = build_report_state(
        summary,
        coverage,
        macro,
        RiskAssessment(35, "elevated", []),
        [],
        [],
        portfolio,
    )
    changes = compare_report_states(restored, new)

    assert changes == [
        "Risk score: 20 → 35.",
        "Risk level: low → elevated.",
    ]
