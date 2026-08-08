from __future__ import annotations

from app.config import PortfolioFactorDefinition
from app.models.analysis import (
    MarketFactorContribution,
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
    unmapped_symbols = tuple(sorted(set(weights) - mapped_symbols))
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
        unmapped_symbols,
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
        component_contributions = tuple(
            MarketFactorContribution(
                "risk_component",
                component,
                market_risk.components.get(component, 0),
            )
            for component in definition.risk_components
            if market_risk.components.get(component, 0) > 0
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
        cluster_contributions = tuple(
            MarketFactorContribution(
                "risk_cluster", item.cluster, item.points, item.evidence_refs
            )
            for item in clusters
        )
        asset_contributions = tuple(
            MarketFactorContribution(
                "single_asset_alert",
                item.symbol,
                0,
                (item.evidence_ref,),
            )
            for item in alerts
        )
        contributions = (
            *component_contributions,
            *cluster_contributions,
            *asset_contributions,
        )
        risk_points = min(100, sum(item.risk_points for item in contributions))
        impact_score = min(100, round(exposure.weight * risk_points))
        drivers = tuple(
            f"{item.source_kind}:{item.source_id}={item.risk_points}"
            for item in contributions
        )
        evidence_refs = tuple(
            dict.fromkeys(
                ref for item in contributions for ref in item.evidence_refs
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
                contributions,
            )
        )
    dominant = max(items, key=lambda item: item.impact_score, default=None)
    return PortfolioImpactAssessment(
        "available",
        tuple(items),
        dominant_factor_id=dominant.factor_id if dominant else None,
        dominant_impact_score=dominant.impact_score if dominant else None,
        level=dominant.level if dominant else "low",
    )


def _impact_level(score: int) -> str:
    if score >= 30:
        return "high"
    if score >= 15:
        return "elevated"
    if score >= 5:
        return "watch"
    return "low"
