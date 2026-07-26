from datetime import date

import pytest

from app.analyzers.fundamental_evidence_analyzer import (
    analyze_fundamental_evidence,
)
from app.collectors.fundamental_csv_collector import load_fundamental_csv
from app.config import FundamentalPolicy
from app.models.analysis import (
    EarningsEstimateObservation,
    ValuationObservation,
)
from app.storage.db import initialize_database
from app.storage.repositories.fundamental_repo import FundamentalRepository


def test_fundamental_csv_import_and_repository_round_trip(tmp_path):
    path = tmp_path / "fundamentals.csv"
    path.write_text(
        "record_type,symbol,as_of_date,metric,value,period,currency,source\n"
        "valuation,qqq,2026-07-25,forward_pe,25.5,NTM,,provider_a\n"
        "earnings_estimate,qqq,2026-07-01,eps,10,FY2027,,provider_a\n",
        encoding="utf-8",
    )
    imported = load_fundamental_csv(path)
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = FundamentalRepository(db_path)
    repo.upsert_valuations(imported.valuations)
    repo.upsert_earnings_estimates(imported.earnings_estimates)

    assert repo.get_valuations()[0].symbol == "QQQ"
    assert repo.get_valuations()[0].metric == "forward_pe"
    assert repo.get_earnings_estimates()[0].fiscal_period == "FY2027"


def test_fundamental_evidence_derives_material_negative_revision():
    state = analyze_fundamental_evidence(
        [ValuationObservation("QQQ", date(2026, 7, 25), "forward_pe", 25, "a")],
        [
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 1), "FY2027", "eps", 10, "a"
            ),
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 25), "FY2027", "eps", 9, "a"
            ),
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 27), "FY2027", "eps", 20, "a"
            ),
        ],
        FundamentalPolicy(30, 30, 0.05),
        date(2026, 7, 26),
    )

    assert state.valuation_status == "available"
    assert state.earnings_revision_status == "available"
    assert state.revisions[0].change_pct == pytest.approx(-0.10)
    assert state.revisions[0].material is True
    assert state.fundamental_flags == {
        "QQQ.earnings_revision_negative": True
    }


def test_revision_requires_like_for_like_source_and_configured_materiality():
    state = analyze_fundamental_evidence(
        [],
        [
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 1), "FY2027", "eps", 10, "a"
            ),
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 25), "FY2027", "eps", 9, "b"
            ),
        ],
        FundamentalPolicy(),
        date(2026, 7, 26),
    )

    assert state.revisions == ()
    assert state.earnings_revision_status == "blocked"
    assert state.fundamental_flags == {}
    assert "earnings_revision_requires_two_like_for_like_observations" in state.reasons
