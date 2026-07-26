from app.analyzers.portfolio_impact_analyzer import analyze_portfolio_impact
from app.config import PortfolioFactorDefinition
from app.models.analysis import (
    PortfolioAllocation,
    PortfolioSummary,
    RiskAssessment,
    RiskAssetAlert,
    RiskClusterAssessment,
)


def portfolio(*allocations: tuple[str, float]) -> PortfolioSummary:
    return PortfolioSummary(
        base_currency="CNY",
        total_holding_cost=1000,
        allocations=[
            PortfolioAllocation(symbol, weight * 1000, weight, None, None, None)
            for symbol, weight in allocations
        ],
        daily_investment_budget=None,
        usd_cash=0,
        usd_daily_spend=None,
        usd_coverage_days=None,
        snapshot_status="available",
    )


def test_factor_exposure_can_overlap_and_maps_market_risk_to_portfolio():
    result = analyze_portfolio_impact(
        portfolio(("QQQ", 0.6), ("GLD", 0.4)),
        (
            PortfolioFactorDefinition(
                "us_equity", ("QQQ", "VOO"), ("volatility",),
                ("broad_equity_growth",),
            ),
            PortfolioFactorDefinition(
                "growth_equity", ("QQQ",), ("volatility",),
                ("broad_equity_growth",),
            ),
            PortfolioFactorDefinition("gold", ("GLD",), (), ("gold",)),
        ),
        RiskAssessment(
            23,
            "elevated",
            [],
            clusters=[
                RiskClusterAssessment(
                    "broad_equity_growth", ("QQQ", "SPY"), 1.6, 8,
                    ("PRICE:QQQ", "PRICE:SPY"),
                )
            ],
            single_asset_alerts=[
                RiskAssetAlert("GLD", "gold", 1.0, 5, "PRICE:GLD")
            ],
            components={"unusual_moves": 13, "breadth": 0, "volatility": 10},
        ),
    )

    assert result.factors.status == "available"
    assert result.factors.mapped_weight == 1.0
    assert {item.factor_id: item.weight for item in result.factors.exposures} == {
        "us_equity": 0.6,
        "growth_equity": 0.6,
        "gold": 0.4,
    }
    impacts = {item.factor_id: item for item in result.impact.items}
    assert impacts["us_equity"].market_risk_points == 18
    assert impacts["us_equity"].impact_score == 11
    assert result.impact.dominant_factor_id == "us_equity"
    assert result.impact.dominant_impact_score == 11
    assert [
        (item.source_kind, item.source_id, item.risk_points)
        for item in impacts["us_equity"].contributions
    ] == [
        ("risk_component", "volatility", 10),
        ("risk_cluster", "broad_equity_growth", 8),
    ]
    assert impacts["gold"].impact_score == 2
    assert impacts["gold"].evidence_refs == ("PRICE:GLD",)


def test_incomplete_factor_mapping_blocks_portfolio_impact():
    result = analyze_portfolio_impact(
        portfolio(("QQQ", 0.6), ("OTHER", 0.4)),
        (PortfolioFactorDefinition("growth", ("QQQ",)),),
        RiskAssessment(0, "low", [], components={}),
    )

    assert result.factors.status == "degraded"
    assert result.factors.mapped_weight == 0.6
    assert result.factors.unmapped_symbols == ("OTHER",)
    assert result.impact.status == "blocked"
    assert result.impact.reasons == ("portfolio_factor_mapping_incomplete",)


def test_missing_factor_definitions_fail_closed():
    result = analyze_portfolio_impact(
        portfolio(("QQQ", 1.0)),
        (),
        RiskAssessment(0, "low", []),
    )

    assert result.factors.status == "blocked"
    assert result.impact.status == "blocked"
