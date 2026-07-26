from __future__ import annotations

from app.config import PortfolioFactorDefinition
from app.models.analysis import (
    PortfolioFactorExposure,
    PortfolioFactorState,
    PortfolioImpactAnalysis,
    PortfolioImpactAssessment,
    PortfolioImpactItem,
    PortfolioSummary,
    RiskAssessment,
)


def analyze_portfolio_impact(
    portfolio: PortfolioSummary,
    factor_definitions: tuple[PortfolioFactorDefinition, ...],
    market_risk: RiskAssessment,
    market_actionability: str = "available",
) -> PortfolioImpactAnalysis:
    """Map configured cost-basis factor tags and market drivers to impact."""
    factors = _analyze_factor_exposure(portfolio, factor_definitions)
    impact = _map_market_risk(
        factors, factor_definitions, market_risk, market_actionability
    )
    return PortfolioImpactAnalysis(factors, impact)


def _analyze_factor_exposure(
    portfolio: PortfolioSummary,
    definitions: tuple[PortfolioFactorDefinition, ...],
) -> PortfolioFactorState:
    if not definitions:
        return PortfolioFactorState(
            "blocked", None, (), ("portfolio_factor_definitions_not_configured",)
        )
    weights = {
        item.symbol: item.current_weight
        for item in portfolio.allocations
        if item.current_weight is not None and item.current_weight > 0
    }
    if not weights:
        return PortfolioFactorState(
            "blocked", None, (), ("invested_allocation_unavailable",)
        )
    freshness_status = (
        portfolio.freshness.holdings.status
        if portfolio.freshness is not None
        else portfolio.snapshot_status
    )
    exposures = tuple(
        PortfolioFactorExposure(
            factor_id=definition.factor_id,
            status="available",
            weight=sum(weights.get(symbol, 0.0) for symbol in definition.symbols),
            symbols=tuple(
                symbol for symbol in definition.symbols if symbol in weights
            ),
            basis="supplied_invested_holding_cost_factor_tags",
        )
        for definition in definitions
    )
    mapped_symbols = {
        symbol
        for definition in definitions
        for symbol in definition.symbols
        if symbol in weights
    }
    mapped_weight = sum(weights[symbol] for symbol in mapped_symbols)
    reasons: list[str] = []
    if freshness_status != "available":
        reasons.append(f"holding_freshness_{freshness_status}")
    if mapped_weight < 0.9999:
        reasons.append("portfolio_factor_mapping_incomplete")
    return PortfolioFactorState(
        "degraded" if reasons else "available",
        mapped_weight,
        exposures,
        tuple(reasons),
    )


def _map_market_risk(
    factors: PortfolioFactorState,
    definitions: tuple[PortfolioFactorDefinition, ...],
    market_risk: RiskAssessment,
    market_actionability: str,
) -> PortfolioImpactAssessment:
    if factors.status != "available":
        return PortfolioImpactAssessment(
            "blocked", (), tuple(factors.reasons or ("factor_exposure_unavailable",))
        )
    if market_risk.level == "unknown":
        return PortfolioImpactAssessment(
            "blocked", (), ("market_risk_unavailable",)
        )
    if market_actionability != "available":
        return PortfolioImpactAssessment(
            "blocked", (), ("market_analysis_not_available",)
        )
    definition_by_id = {item.factor_id: item for item in definitions}
    items: list[PortfolioImpactItem] = []
    for exposure in factors.exposures:
        if exposure.weight is None or exposure.weight <= 0:
            continue
        definition = definition_by_id[exposure.factor_id]
        component_points = sum(
            market_risk.components.get(component, 0)
            for component in definition.risk_components
        )
        clusters = [
            item for item in market_risk.clusters
            if item.cluster in definition.risk_clusters
        ]
        alerts = [
            item for item in market_risk.single_asset_alerts
            if item.category in definition.risk_clusters
            and item.symbol in definition.symbols
        ]
        risk_points = min(
            100,
            component_points
            + sum(item.points for item in clusters)
            + sum(item.points for item in alerts),
        )
        impact_score = min(100, round(exposure.weight * risk_points))
        drivers = tuple(
            [
                *(
                    f"component:{name}={market_risk.components.get(name, 0)}"
                    for name in definition.risk_components
                ),
                *(f"cluster:{item.cluster}={item.points}" for item in clusters),
                *(f"asset:{item.symbol}={item.points}" for item in alerts),
            ]
        )
        evidence_refs = tuple(
            dict.fromkeys(
                [
                    *(ref for item in clusters for ref in item.evidence_refs),
                    *(item.evidence_ref for item in alerts),
                ]
            )
        )
        items.append(
            PortfolioImpactItem(
                exposure.factor_id,
                exposure.weight,
                risk_points,
                impact_score,
                _impact_level(impact_score),
                drivers,
                evidence_refs,
            )
        )
    return PortfolioImpactAssessment("available", tuple(items))


def _impact_level(score: int) -> str:
    if score >= 30:
        return "high"
    if score >= 15:
        return "elevated"
    if score >= 5:
        return "watch"
    return "low"
