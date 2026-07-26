from datetime import date

from app.analyzers.decision_evidence_analyzer import analyze_decision_evidence
from app.models.analysis import (
    ActionReadiness,
    EarningsRevision,
    EtfEvent,
    FundamentalEvidenceState,
    NewsQualityGate,
    PortfolioAllocation,
    PortfolioSummary,
    StrategyDecisionState,
    ValuationObservation,
)


def portfolio() -> PortfolioSummary:
    return PortfolioSummary(
        "CNY",
        1000,
        [
            PortfolioAllocation("QQQ", 600, 0.6, None, None, None),
            PortfolioAllocation("VOO", 400, 0.4, None, None, None),
        ],
        None,
        0,
        None,
        None,
    )


def decision() -> StrategyDecisionState:
    return StrategyDecisionState(
        (),
        ActionReadiness(
            "ready", "pause", "QQQ", "negative_revision", ("triggered",)
        ),
    )


def test_decision_evidence_maps_p2_data_to_relevant_assets_without_sentiment():
    state = analyze_decision_evidence(
        portfolio(),
        decision(),
        FundamentalEvidenceState(
            "available",
            "available",
            (
                ValuationObservation(
                    "QQQ", date(2026, 7, 25), "forward_pe", 25, "provider"
                ),
            ),
            (
                EarningsRevision(
                    "QQQ", "FY2027", "eps", date(2026, 7, 1),
                    date(2026, 7, 25), 10, 9, -0.1, "negative", True,
                    "provider",
                ),
            ),
            {"QQQ.earnings_revision_negative": True},
        ),
        NewsQualityGate(
            1.0, 0.8, "available", None, None, "unavailable"
        ),
        [
            EtfEvent(
                "fee_change",
                "QQQ",
                "QQQ announces a fee change",
                "Example",
                ["https://example.com/qqq"],
                0.99,
                1,
                "2026-07-25",
            )
        ],
    )

    assert state.status == "degraded"
    assert state.uncovered_symbols == ("VOO",)
    qqq = next(item for item in state.assets if item.symbol == "QQQ")
    assert qqq.relevance == ("portfolio_holding", "decision_candidate")
    assert qqq.valuations[0].value == 25
    assert qqq.revisions[0].direction == "negative"
    assert qqq.news_events[0].review_type == "etf_event_review"
    assert "QQQ:material_negative_earnings_revision" in qqq.review_flags
    assert "QQQ:news_event_requires_primary_source_review" in qqq.review_flags
    assert all("positive_news" not in flag for flag in state.review_flags)
    assert any(ref.startswith("VALUATION:QQQ") for ref in state.evidence_refs)
    assert any(ref.startswith("NEWS_EVENT:QQQ") for ref in state.evidence_refs)


def test_decision_evidence_discards_news_events_when_entity_gate_fails():
    state = analyze_decision_evidence(
        portfolio(),
        decision(),
        FundamentalEvidenceState("blocked", "blocked", (), (), {}, ()),
        NewsQualityGate(
            0.5,
            0.8,
            "data_quality_review",
            None,
            None,
            "unavailable",
            ["precision below threshold"],
        ),
        [
            EtfEvent(
                "fee_change", "QQQ", "headline", "Example",
                ["https://example.com/qqq"], 0.99, 1, "2026-07-25",
            )
        ],
    )

    assert state.status == "blocked"
    assert all(not item.news_events for item in state.assets)
    assert "news_entity_pipeline_data_quality_review" in state.reasons
    assert "decision_relevant_evidence_not_available" in state.reasons
