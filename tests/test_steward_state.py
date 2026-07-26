from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.steward.job import (
    generate_steward_state_report,
    import_steward_state_csv,
)
from app.steward.storage import StewardRepository


HEADER = (
    "record_type,as_of_date,institution,account_label,currency,cash_balance,"
    "cash_role,symbol,asset_name,quantity,unit_cost,acquired_on,fx_date,sold_currency,"
    "sold_amount,bought_currency,bought_amount,fee_currency,fee_amount,notes\n"
)


def test_import_steward_state_csv_replaces_cash_holdings_and_fx(tmp_path):
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "state.csv"
    csv_path.write_text(
        HEADER
        + "cash,2026-07-19,CMB,cmb_rmb,RMB,1200000,investable,,,,,,,,,,,,,\n"
        + "holding,2026-07-19,其他,黄金账户,CNY,,,XAU-GRAM,黄金（克）,"
        "5.6724,881.46110994,,,,,,,,,总成本 5000 CNY\n"
        + "fx,2026-07-19,ICBC,icbc_usd,,,,,,,,,2026-07-15,CNY,"
        "13587.6,USD,2000,CNY,0,\n",
        encoding="utf-8",
    )

    summary = import_steward_state_csv(db_path, csv_path)
    state = StewardRepository(db_path).load_state()

    assert summary.rows_seen == 3
    assert summary.cash_positions == 1
    assert summary.holdings == 1
    assert summary.fx_conversions == 1
    assert state.cash_positions[0].currency == "CNY"
    assert state.cash_positions[0].balance == Decimal("1200000")
    assert state.cash_positions[0].cash_role == "investment_cash"
    assert state.holdings[0].symbol == "XAU-GRAM"
    assert state.holdings[0].quantity == Decimal("5.6724")
    assert state.holdings[0].total_cost.quantize(Decimal("0.01")) == Decimal("5000.00")
    assert state.holdings[0].acquired_on is None
    assert state.fx_conversions[0].effective_rate == Decimal("6.7938")

    csv_path.write_text(
        HEADER
        + "cash,2026-07-20,BOA,boa_usd,USD,9000,reserved,,,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    import_steward_state_csv(db_path, csv_path)
    replaced = StewardRepository(db_path).load_state()

    assert [item.account_label for item in replaced.cash_positions] == ["boa_usd"]
    assert replaced.holdings == []
    assert replaced.fx_conversions == []


def test_import_steward_state_csv_rejects_invalid_rows_without_replacing_state(
    tmp_path,
):
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "state.csv"
    csv_path.write_text(
        HEADER + "cash,2026-07-19,CMB,cmb_rmb,CNY,100,reserved,,,,,,,,,,,,,\n",
        encoding="utf-8",
    )
    import_steward_state_csv(db_path, csv_path)
    csv_path.write_text(
        HEADER
        + "cash,2026-07-20,CMB,cmb_rmb,CNY,not-a-number,reserved,,,,,,,,,,,,,\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="row 2"):
        import_steward_state_csv(db_path, csv_path)

    state = StewardRepository(db_path).load_state()
    assert state.cash_positions[0].balance == Decimal("100")
    assert state.cash_positions[0].as_of_date == date(2026, 7, 19)


def test_generate_steward_state_report_contains_only_state_sections(tmp_path):
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "state.csv"
    report_dir = tmp_path / "reports"
    csv_path.write_text(
        HEADER
        + "cash,2026-07-19,ICBC,icbc_usd,USD,1940,investable,,,,,,,,,,,,,\n"
        + "holding,2026-07-19,摩根上投,基金账户,USD,,,QQQ,"
        "NASDAQ ETF QDII,32.56,1.8416,2026-07-15,,,,,,,,\n"
        + "fx,2026-07-19,ICBC,icbc_usd,,,,,,,,,2026-07-15,CNY,"
        "13587.6,USD,2000,CNY,0,\n",
        encoding="utf-8",
    )
    import_steward_state_csv(db_path, csv_path)

    path = generate_steward_state_report(
        db_path,
        report_dir,
        report_date=date(2026, 7, 19),
    )
    content = path.read_text(encoding="utf-8")

    assert "## 1. Cash Positions" in content
    assert "## 2. Holdings" in content
    assert "| QQQ | NASDAQ ETF QDII | USD | 32.56 | 1.8416 | 59.96 |" in content
    assert "## 3. FX Conversions" in content
    assert "| 2026-07-15 | ICBC / icbc_usd | CNY 13587.60 | USD 2000.00 | 6.7938 CNY/USD | CNY 0.00 |" in content
    assert "Cashflow" not in content
    assert "Transfer" not in content
    assert "Recent Cash Transactions" not in content


def test_repository_state_template_is_importable_and_includes_gold(tmp_path):
    template = Path("data/steward/templates/steward_state_template.csv")

    summary = import_steward_state_csv(tmp_path / "steward.db", template)
    state = StewardRepository(tmp_path / "steward.db").load_state()
    gold = next(item for item in state.holdings if item.symbol == "XAU-GRAM")

    assert summary.cash_positions == 3
    assert summary.holdings == 4
    assert summary.fx_conversions == 1
    assert gold.quantity == Decimal("5.6724")
    assert gold.total_cost.quantize(Decimal("0.01")) == Decimal("5000.00")
    assert {item.cash_role for item in state.cash_positions} == {
        "investment_cash",
        "investment_source",
        "reserved",
    }
