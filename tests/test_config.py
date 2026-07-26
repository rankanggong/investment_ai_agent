import json
from pathlib import Path

import pytest

from app.config import load_report_profile, load_watchlist


def test_load_watchlist_expands_grouped_assets():
    watchlist = load_watchlist(Path("config/watchlist.yaml"))

    symbols = [asset.symbol for asset in watchlist.assets]

    assert "SPY" in symbols
    assert "QQQ" in symbols
    assert "XLK" in symbols
    assert "AAPL" in symbols
    assert "NVDA" in symbols
    assert watchlist.asset_by_symbol("SPY").role == "us_equity_core"
    assert watchlist.asset_by_symbol("XLK").role == "sector"
    assert watchlist.asset_by_symbol("AAPL").role == "popular_company"
    assert watchlist.asset_by_symbol("AAPL").group == "popular_companies"
    assert "MSFT" in watchlist.symbols_for_group("popular_companies")
    assert watchlist.symbols_for_group("macro_actual") == [
        "^TNX",
        "DX-Y.NYB",
        "^VIX",
    ]
    assert watchlist.symbols_for_group("breadth") == ["RSP"]


def test_load_report_profile_reads_targets_budgets_and_questions(tmp_path):
    path = tmp_path / "report-profile.json"
    path.write_text(
        json.dumps(
            {
                "base_currency": "cny",
                "target_allocations": {"qqq": 0.6, "voo": 0.4},
                "daily_investment_budget": 500,
                "usd_daily_spend": 40,
                "gpt_questions": ["What changed?"],
                "strategy_rules": [
                    {
                        "id": "qqq_level_1",
                        "symbol": "qqq",
                        "action": "manual_add_level_1",
                        "priority": 20,
                        "conditions": [
                            {
                                "metric": "drawdown_from_252d_high",
                                "operator": "<=",
                                "value": -0.08,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    profile = load_report_profile(path)

    assert profile.base_currency == "CNY"
    assert profile.target_allocations == {"QQQ": 0.6, "VOO": 0.4}
    assert profile.daily_investment_budget == 500.0
    assert profile.usd_daily_spend == 40.0
    assert profile.gpt_questions == ["What changed?"]
    assert profile.strategy_rules[0].rule_id == "qqq_level_1"
    assert profile.strategy_rules[0].symbol == "QQQ"
    assert profile.strategy_rules[0].conditions[0].expected == -0.08


def test_load_report_profile_rejects_targets_that_do_not_sum_to_one(tmp_path):
    path = tmp_path / "report-profile.json"
    path.write_text(
        json.dumps({"target_allocations": {"QQQ": 0.6, "VOO": 0.3}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must sum to 1.0"):
        load_report_profile(path)


def test_load_report_profile_rejects_unknown_strategy_metric(tmp_path):
    path = tmp_path / "report-profile.json"
    path.write_text(
        json.dumps(
            {
                "strategy_rules": [
                    {
                        "id": "bad",
                        "symbol": "QQQ",
                        "action": "manual_add",
                        "conditions": [
                            {"metric": "invented", "operator": ">", "value": 1}
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid condition"):
        load_report_profile(path)


def test_load_report_profile_reads_structured_target_budget_and_action_sizing(
    tmp_path,
):
    path = tmp_path / "report-profile.json"
    path.write_text(
        json.dumps(
            {
                "base_currency": "CNY",
                "target_allocation": {
                    "basis": "supplied_invested_holding_cost",
                    "weights": {"QQQ": 0.6, "VOO": 0.4},
                    "tolerance": 0.03,
                },
                "daily_budget": {
                    "amount": 1000,
                    "currency": "CNY",
                    "minimum_action_amount": 100,
                    "maximum_action_amount": 600,
                },
                "action_sizing": [
                    {
                        "action": "manual_add_level_1",
                        "method": "daily_budget_fraction",
                        "budget_fraction": 0.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    profile = load_report_profile(path)

    assert profile.target_allocations == {"QQQ": 0.6, "VOO": 0.4}
    assert profile.target_allocation.tolerance == 0.03
    assert profile.daily_investment_budget == 1000
    assert profile.daily_budget.maximum_action_amount == 600
    assert profile.action_sizing[0].budget_fraction == 0.5
