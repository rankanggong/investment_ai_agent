from datetime import date, datetime, timezone
import json
from decimal import Decimal

from app.jobs.daily_market_job import generate_daily_report
from app.models.analysis import (
    EarningsEstimateObservation,
    NewsItem,
    ValuationObservation,
)
from app.steward.models import CashPosition, FxConversion, HoldingPosition, StewardState
from app.steward.storage import StewardRepository, initialize_steward_database
from app.storage.db import initialize_database
from app.storage.repositories.report_repo import ReportRepository
from app.storage.repositories.fundamental_repo import FundamentalRepository
from app.storage.repositories.news_repo import NewsRepository


def test_daily_market_report_loads_portfolio_summary_and_account_detail(tmp_path):
    finance_db = tmp_path / "finance.db"
    steward_db = tmp_path / "steward.db"
    report_dir = tmp_path / "reports"
    watchlist = tmp_path / "watchlist.yaml"
    report_profile = tmp_path / "report-profile.json"
    watchlist.write_text("assets:\n  core:\n    - SPY\n", encoding="utf-8")
    report_profile.write_text(
        json.dumps(
            {
                "portfolio_factors": [
                    {
                        "id": "us_equity",
                        "symbols": ["VOO"],
                        "risk_components": ["breadth", "volatility"],
                        "risk_clusters": ["broad_equity_growth"],
                    }
                ],
                "fundamental_policy": {
                    "valuation_stale_after_days": 30,
                    "earnings_revision_stale_after_days": 30,
                    "earnings_revision_materiality": 0.05,
                },
                "strategy_rules": [
                    {
                        "id": "qqq_pause_on_negative_revision",
                        "symbol": "QQQ",
                        "action": "pause",
                        "priority": 100,
                        "blocking": True,
                        "conditions": [
                            {
                                "metric": "earnings_revision_negative",
                                "operator": "==",
                                "value": True,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    initialize_database(finance_db)
    fundamental_repo = FundamentalRepository(finance_db)
    fundamental_repo.upsert_valuations(
        [
            ValuationObservation(
                "SPY", date(2026, 7, 20), "forward_pe", 22.0, "provider_a"
            )
        ]
    )
    fundamental_repo.upsert_earnings_estimates(
        [
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 1), "FY2027", "eps", 10, "provider_a"
            ),
            EarningsEstimateObservation(
                "QQQ", date(2026, 7, 20), "FY2027", "eps", 9, "provider_a"
            ),
        ]
    )
    NewsRepository(finance_db).upsert_many(
        [
            NewsItem(
                "SPY announces expense ratio fee cut",
                "https://example.com/spy-fee",
                "Example",
                datetime(2026, 7, 20, tzinfo=timezone.utc),
                "SPY",
                "google_news_rss",
                query_symbol="SPY",
            )
        ]
    )
    initialize_steward_database(steward_db)
    StewardRepository(steward_db).replace_state(
        StewardState(
            cash_positions=[
                CashPosition(
                    institution="bank",
                    account_label="cash",
                    currency="USD",
                    balance=Decimal("9000"),
                    as_of_date=date(2026, 7, 19),
                    cash_role="investment_cash",
                )
            ],
            holdings=[
                HoldingPosition(
                    institution="broker",
                    account_label="fund",
                    symbol="VOO",
                    name="Vanguard S&P 500 ETF",
                    quantity=Decimal("10.74"),
                    currency="CNY",
                    unit_cost=Decimal("2.7933"),
                    as_of_date=date(2026, 7, 19),
                )
            ],
            fx_conversions=[
                FxConversion(
                    institution="bank",
                    account_label="usd",
                    fx_date=date(2026, 7, 15),
                    sold_currency="CNY",
                    sold_amount=Decimal("13587.60"),
                    bought_currency="USD",
                    bought_amount=Decimal("2000"),
                )
            ],
        )
    )

    path = generate_daily_report(
        db_path=finance_db,
        watchlist_path=watchlist,
        report_dir=report_dir,
        report_date=date(2026, 7, 21),
        steward_db_path=steward_db,
        report_profile_path=report_profile,
    )

    content = path.read_text(encoding="utf-8")
    assert "## 2. Portfolio Summary" in content
    assert "### Invested Sleeve Allocation" in content
    assert "### Total Liquid Asset Allocation" in content
    assert "Basis: supplied_holding_cost_plus_cash_balance" in content
    assert "| VOO | CNY 30.00 | 100.00% | N/A | N/A | N/A |" in content
    assert "### B. Account Detail" in content
    assert "| broker | fund | VOO | Vanguard S&P 500 ETF |" in content
    assert "#### FX Conversions" in content
    assert "| 2026-07-15 | bank / usd | CNY 13587.60 | USD 2000.00 |" in content
    assert "| bank | cash | USD | 9000 | investment_cash | 2026-07-19 |" in content
    assert "Status: degraded" in content
    assert "- Weighted all-in cost basis: 6.79" in content
    assert "- Reason: usd_cnh_spot_unavailable" in content
    assert "Action Readiness: ready" in content
    assert "Execution Readiness: blocked" in content
    assert "rule_execution_permission_not_configured" in content
    assert "Decision Context:" in content
    assert "- Transition: baseline" in content
    assert "Decision evidence: degraded" in content
    assert "QQQ:material_negative_earnings_revision" in content
    assert "### Portfolio Factor Exposure and Market Impact" in content
    assert "| us_equity | 100.00% | VOO |" in content
    assert "Portfolio impact status: blocked" in content
    assert "- Impact reason: market_analysis_not_available" in content
    assert '"action_readiness_status": "ready"' in content
    assert '"rule_execution_permission_status": "missing"' in content
    assert '"portfolio_factor_exposures": {"us_equity": 1.0}' in content
    assert "Valuation status: available" in content
    assert "Earnings revision status: available" in content
    assert "| QQQ | FY2027 | eps |" in content
    assert "News Entity Pipeline:" in content
    assert "- Status: available" in content
    assert "- Deduplicated asset events: 1" in content
    assert '"valuation_status": "available"' in content
    assert '"earnings_revision_status": "available"' in content
    assert '"decision_evidence_status": "degraded"' in content
    assert '"news_entity_pipeline_status": "available"' in content
    assert '"QQQ:FY2027:eps": "negative"' in content
    assert '"qqq_pause_on_negative_revision": "triggered"' in content
    assert '"gpt_task_ids": [' in content
    decisions = ReportRepository(finance_db).list_decision_states()
    assert len(decisions) == 1
    assert decisions[0].report_date == date(2026, 7, 21)
    assert decisions[0].readiness_status == "ready"
    assert decisions[0].execution_status == "blocked"
    assert decisions[0].permission_status == "missing"
    assert decisions[0].context["candidate_rule_id"] == (
        "qqq_pause_on_negative_revision"
    )
    assert decisions[0].context["transition"] == "baseline"
    assert decisions[0].context["dominant_factor_id"] is None
    assert decisions[0].context["decision_evidence"]["status"] == "degraded"
    assert decisions[0].context["decision_evidence"]["assets"][0][
        "symbol"
    ] == "QQQ"
