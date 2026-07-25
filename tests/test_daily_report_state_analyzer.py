from datetime import date
from decimal import Decimal

from app.analyzers.daily_report_state_analyzer import (
    analyze_fx_costs,
    analyze_market_breadth,
    analyze_portfolio_summary,
    assess_market_risk,
    assess_portfolio_risk,
    build_gpt_tasks,
    build_report_state,
    combine_data_quality,
    compare_report_states,
    extract_report_state,
    select_key_market_evidence,
    serialize_report_state,
)
from app.config import ReportProfile
from app.models.analysis import (
    DataCoverage,
    DailySignalSummary,
    MacroContext,
    NewsQualityGate,
    PriceSignal,
)
from app.models.price import PriceBar
from app.steward.models import (
    CashPosition,
    FxConversion,
    HoldingPosition,
    PortfolioReportState,
)


def signal(
    symbol: str,
    *,
    latest: float = 100.0,
    r5: float = 0.0,
    r20: float = 0.0,
    unusual: bool = False,
    zscore: float = 0.0,
    atr: float = 0.0,
    percentile: float = 0.5,
    sma50: float | None = 95.0,
    sma200: float | None = 90.0,
) -> PriceSignal:
    return PriceSignal(
        symbol,
        0.01,
        r5,
        r20,
        1.0,
        zscore,
        unusual,
        "standardized trigger",
        latest=latest,
        latest_date=date(2026, 7, 24),
        sma_50=sma50,
        sma_200=sma200,
        drawdown_from_high=-0.05,
        atr_multiple=atr,
        return_zscore_60d=zscore,
        historical_percentile=percentile,
    )


def bar(day: date, close: float) -> PriceBar:
    return PriceBar(
        "USD/CNH", day, close, close, close, close, close, None, "test"
    )


def portfolio_state() -> PortfolioReportState:
    return PortfolioReportState(
        holdings=[
            HoldingPosition(
                "broker", "fund", "QQQ", "QQQ", Decimal("10"), "CNY",
                Decimal("100"), date(2026, 7, 24),
            )
        ],
        fx_conversions=[
            FxConversion(
                "bank", "usd", date(2026, 7, 15), "CNY", Decimal("700"),
                "USD", Decimal("100"), "CNY", Decimal("7"),
            )
        ],
        cash_positions=[
            CashPosition(
                "bank", "usd", "USD", Decimal("1200"), date(2026, 7, 24),
                cash_role="investable",
            ),
            CashPosition(
                "bank", "reserve", "CNY", Decimal("5000"),
                date(2026, 7, 24), cash_role="reserved",
            ),
        ],
    )


def test_portfolio_summary_separates_cash_roles_and_invested_holdings():
    profile = ReportProfile(
        base_currency="CNY",
        target_allocations={"QQQ": 1.0},
        usd_daily_spend=10.0,
    )
    result = analyze_portfolio_summary(
        portfolio_state(),
        profile,
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )

    assert result.total_holding_cost == 1000.0
    assert result.allocations[0].current_weight == 1.0
    assert result.investable_cash == 8400.0
    assert result.reserved_cash == 5000.0
    assert result.usd_coverage_days == 120.0
    assert "invested holding cost" in result.notes[0]


def test_market_risk_counts_correlated_assets_once_per_cluster():
    signals = {
        "AAPL": signal("AAPL", unusual=True, zscore=3.0),
        "MSFT": signal("MSFT", unusual=True, atr=2.0),
        "TLT": signal("TLT", unusual=True, percentile=0.99),
    }
    breadth = analyze_market_breadth(signals, {})
    result = assess_market_risk(signals, breadth)

    assert [item.cluster for item in result.clusters] == [
        "mega_cap_companies",
        "rates_duration",
    ]
    assert result.explanations[0].startswith("Unusual-move risk: 2 risk clusters")


def test_key_evidence_uses_medium_term_trend_and_standardized_metrics():
    result = select_key_market_evidence(
        {
            "QQQ": signal(
                "QQQ",
                latest=80,
                r5=0.03,
                unusual=True,
                zscore=2.5,
                atr=1.8,
                percentile=0.97,
                sma50=90,
                sma200=100,
            )
        }
    )[0]

    assert result.medium_term_trend == "medium_term_downtrend"
    assert result.short_term_state == "countertrend_rebound"
    assert result.return_zscore == 2.5
    assert result.evidence_ref == "PRICE:QQQ:2026-07-24"


def test_combined_data_quality_prioritizes_news_blocked_and_portfolio_stale():
    state = portfolio_state()
    stale_state = PortfolioReportState(
        state.holdings,
        state.fx_conversions,
        [
            CashPosition(
                "bank", "usd", "USD", Decimal("100"), date(2026, 7, 1),
                cash_role="unclassified",
            )
        ],
    )
    quality = combine_data_quality(
        DataCoverage([], [], status="available"),
        NewsQualityGate(
            None, 0.8, "disabled", None, None, "unavailable",
            ["News collection is disabled."],
        ),
        stale_state,
        date(2026, 7, 25),
    )

    assert quality.status == "blocked"
    statuses = {(row.category, row.item): row.status for row in quality.rows}
    assert statuses[("News", "entity pipeline")] == "blocked"
    assert statuses[("Portfolio", "cash and holdings")] == "stale"
    assert statuses[("Portfolio", "cash roles")] == "degraded"


def test_fx_cost_compares_all_in_rate_with_historical_usd_cnh():
    result = analyze_fx_costs(
        portfolio_state(),
        [
            bar(date(2026, 7, 14), 6.9),
            bar(date(2026, 7, 15), 7.0),
        ],
    )[0]

    assert result.effective_rate == 7.0
    assert result.all_in_rate == 7.07
    assert result.spot_rate == 7.0
    assert round(result.spot_premium or 0, 4) == 0.01
    assert "offshore approximation" in result.benchmark_note


def test_market_and_portfolio_state_round_trip_and_compare():
    summary = analyze_portfolio_summary(
        portfolio_state(),
        ReportProfile(),
        {"USD/CNH": signal("USD/CNH", latest=7.0)},
        date(2026, 7, 25),
    )
    breadth = analyze_market_breadth({}, {})
    market = assess_market_risk({}, breadth)
    portfolio = assess_portfolio_risk(summary)
    state = build_report_state(
        DailySignalSummary("monitor", [], "Monitor."),
        DataCoverage([], [], status="available"),
        MacroContext("mixed", "mixed", "mixed", "mixed", "mixed", []),
        market,
        portfolio,
        [],
        [],
        summary,
    )
    restored = extract_report_state(serialize_report_state(state))

    assert compare_report_states(restored, state) == ["No state changes detected."]


def test_extract_report_state_renames_legacy_structural_trend_values():
    content = (
        '<!-- report-state: {"executive_status":"review_required",'
        '"data_quality_status":"degraded","macro_regime":"mixed",'
        '"risk_score":20,"risk_level":"moderate","triggered_rules":[],'
        '"structural_trends":["SPY:structural_downtrend"],'
        '"portfolio_gaps":[]} -->'
    )

    restored = extract_report_state(content)

    assert restored is not None
    assert restored.medium_term_trends == ("SPY:legacy_downtrend",)


def test_gpt_tasks_include_evidence_refs_and_output_contract():
    evidence = select_key_market_evidence({"SPY": signal("SPY")})
    tasks = build_gpt_tasks(
        ReportProfile(gpt_questions=["What changed?"]),
        ["No state changes detected."],
        [],
        evidence,
    )

    assert tasks[0].evidence_refs == ("PRICE:SPY:2026-07-24",)
    assert "counterevidence" in tasks[0].expected_output
    assert "confidence" in tasks[0].confidence_requirement.lower()
