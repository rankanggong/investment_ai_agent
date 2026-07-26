from __future__ import annotations

from app.models.analysis import (
    AssetEvent,
    DecisionAssetEvidence,
    DecisionEvidenceState,
    DecisionNewsEvidence,
    DecisionRevisionEvidence,
    DecisionValuationEvidence,
    FundamentalEvidenceState,
    NewsQualityGate,
    PortfolioSummary,
    StrategyDecisionState,
)


def analyze_decision_evidence(
    portfolio: PortfolioSummary,
    decision: StrategyDecisionState,
    fundamental: FundamentalEvidenceState,
    news_quality: NewsQualityGate,
    asset_events: list[AssetEvent],
) -> DecisionEvidenceState:
    """Map quality-gated P2 evidence to held assets and the decision candidate."""
    weights = {
        item.symbol: item.current_weight
        for item in portfolio.allocations
        if item.current_weight is not None and item.current_weight > 0
    }
    candidate = decision.action_readiness.symbol
    relevant_symbols = set(weights)
    if candidate:
        relevant_symbols.add(candidate)
    trusted_events = asset_events if news_quality.status == "available" else []

    assets = tuple(
        _asset_evidence(
            symbol,
            weights.get(symbol),
            symbol == candidate,
            fundamental,
            trusted_events,
        )
        for symbol in sorted(relevant_symbols)
    )
    uncovered_symbols = tuple(
        item.symbol
        for item in assets
        if not (item.valuations or item.revisions or item.news_events)
    )
    review_flags = tuple(
        flag for item in assets for flag in item.review_flags
    )
    evidence_refs = tuple(
        dict.fromkeys(ref for item in assets for ref in item.evidence_refs)
    )
    reasons = [*fundamental.reasons, *news_quality.reasons]
    if not relevant_symbols:
        reasons.append("decision_relevant_assets_not_identified")
    if uncovered_symbols:
        reasons.append(
            "decision_evidence_missing_for:" + ",".join(uncovered_symbols)
        )
    if news_quality.status != "available":
        reasons.append(f"news_entity_pipeline_{news_quality.status}")
    if not evidence_refs:
        status = "blocked"
        reasons.append("decision_relevant_evidence_not_available")
    elif (
        uncovered_symbols
        or fundamental.valuation_status != "available"
        or fundamental.earnings_revision_status != "available"
        or news_quality.status != "available"
    ):
        status = "degraded"
    else:
        status = "available"
    return DecisionEvidenceState(
        status=status,
        valuation_status=fundamental.valuation_status,
        earnings_revision_status=fundamental.earnings_revision_status,
        news_entity_status=news_quality.status,
        assets=assets,
        uncovered_symbols=uncovered_symbols,
        review_flags=tuple(dict.fromkeys(review_flags)),
        reasons=tuple(dict.fromkeys(reasons)),
        evidence_refs=evidence_refs,
    )


def _asset_evidence(
    symbol: str,
    portfolio_weight: float | None,
    is_candidate: bool,
    fundamental: FundamentalEvidenceState,
    asset_events: list[AssetEvent],
) -> DecisionAssetEvidence:
    valuations = tuple(
        DecisionValuationEvidence(
            item.metric,
            item.value,
            item.source,
            item.as_of_date.isoformat(),
            item.currency,
            item.period,
            _valuation_ref(
                item.symbol, item.metric, item.as_of_date.isoformat(), item.source
            ),
        )
        for item in fundamental.valuations
        if item.symbol == symbol
    )
    revisions = tuple(
        DecisionRevisionEvidence(
            item.fiscal_period,
            item.metric,
            item.direction,
            item.change_pct,
            item.material,
            item.source,
            item.current_date.isoformat(),
            _revision_ref(
                item.symbol,
                item.fiscal_period,
                item.metric,
                item.current_date.isoformat(),
                item.source,
            ),
        )
        for item in fundamental.revisions
        if item.symbol == symbol
    )
    events = tuple(
        DecisionNewsEvidence(
            item.event_type,
            item.event_date,
            item.headline,
            item.confidence,
            item.article_count,
            item.review_type,
            tuple(item.source_urls),
            _news_ref(item.related_symbol, item.event_type, item.event_date),
        )
        for item in asset_events
        if item.related_symbol == symbol
    )
    directions = {item.direction for item in revisions}
    flags: list[str] = []
    if valuations:
        flags.append(f"{symbol}:valuation_observation_has_no_action_threshold")
    if {"positive", "negative"} <= directions:
        flags.append(f"{symbol}:mixed_earnings_revision_directions")
    if any(item.material is None for item in revisions):
        flags.append(f"{symbol}:earnings_revision_materiality_unknown")
    if any(item.material is True and item.direction == "negative" for item in revisions):
        flags.append(f"{symbol}:material_negative_earnings_revision")
    if any(item.material is True and item.direction == "positive" for item in revisions):
        flags.append(f"{symbol}:material_positive_earnings_revision")
    if events:
        flags.append(f"{symbol}:news_event_requires_primary_source_review")
    evidence_refs = tuple(
        [
            *(item.evidence_ref for item in valuations),
            *(item.evidence_ref for item in revisions),
            *(item.evidence_ref for item in events),
        ]
    )
    relevance = tuple(
        name
        for name, applies in (
            ("portfolio_holding", portfolio_weight is not None),
            ("decision_candidate", is_candidate),
        )
        if applies
    )
    return DecisionAssetEvidence(
        symbol,
        relevance,
        portfolio_weight,
        valuations,
        revisions,
        events,
        tuple(flags),
        evidence_refs,
    )


def _valuation_ref(
    symbol: str, metric: str, as_of_date: str, source: str
) -> str:
    return f"VALUATION:{symbol}:{metric}:{as_of_date}:{source}"


def _revision_ref(
    symbol: str, fiscal_period: str, metric: str, as_of_date: str, source: str
) -> str:
    return (
        f"EARNINGS_REVISION:{symbol}:{fiscal_period}:{metric}:{as_of_date}:{source}"
    )


def _news_ref(symbol: str, event_type: str, event_date: str) -> str:
    return f"NEWS_EVENT:{symbol}:{event_type}:{event_date}"
