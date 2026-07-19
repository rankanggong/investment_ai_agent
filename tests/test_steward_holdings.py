from datetime import date
from decimal import Decimal

import pytest

from app.steward.holdings import import_holdings_csv, match_usd_fx_transaction
from app.steward.job import generate_steward_report
from app.steward.models import CashTransaction, Holding, StoredCashTransaction
from app.steward.storage import StewardRepository, initialize_steward_database


def _transaction(
    transaction_id: int,
    institution: str,
    account_label: str,
    transaction_date: date,
    currency: str = "美元",
    amount: str = "1000.00",
    summary: str = "个人购汇",
) -> StoredCashTransaction:
    return StoredCashTransaction(
        id=transaction_id,
        source_hash=f"source-{transaction_id}",
        institution=institution,
        account_label=account_label,
        transaction_date=transaction_date,
        currency=currency,
        amount=Decimal(amount),
        balance=None,
        summary=summary,
        raw_text=f"transaction-{transaction_id}",
    )


def test_match_usd_fx_transaction_prefers_same_account_before_date_distance():
    holding = Holding(
        institution="broker",
        account_label="taxable",
        symbol="VOO",
        name="Vanguard S&P 500 ETF",
        quantity=Decimal("1"),
        currency="USD",
        unit_cost=Decimal("500"),
        acquired_on=date(2026, 7, 15),
    )
    same_account = _transaction(
        1,
        "broker",
        "taxable",
        date(2026, 7, 10),
    )
    closer_other_account = _transaction(
        2,
        "icbc",
        "bank",
        date(2026, 7, 14),
    )

    match = match_usd_fx_transaction(
        holding,
        [closer_other_account, same_account],
    )

    assert match is not None
    assert match.id == 1


def test_match_usd_fx_transaction_ignores_non_fx_future_and_negative_rows():
    holding = Holding(
        institution="broker",
        account_label="taxable",
        symbol="VOO",
        name="Vanguard S&P 500 ETF",
        quantity=Decimal("1"),
        currency="USD",
        unit_cost=Decimal("500"),
        acquired_on=date(2026, 7, 15),
    )

    assert (
        match_usd_fx_transaction(
            holding,
            [
                _transaction(1, "icbc", "bank", date(2026, 7, 14), summary="工资"),
                _transaction(2, "icbc", "bank", date(2026, 7, 14), amount="-1000"),
                _transaction(3, "icbc", "bank", date(2026, 7, 16)),
            ],
        )
        is None
    )


def test_import_holdings_csv_normalizes_currency_and_links_only_usd(tmp_path):
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "holdings.csv"
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)
    repo.record_source_document("fx.pdf", "fx-source", "icbc", "pdf", "imported", [])
    repo.upsert_cash_transactions(
        "fx-source",
        [
            CashTransaction(
                institution="icbc",
                account_label="bank",
                transaction_date=date(2026, 7, 13),
                currency="美元",
                amount=Decimal("1000.00"),
                balance=Decimal("1000.00"),
                summary="个人购汇",
                raw_text="fx-in",
            )
        ],
    )
    csv_path.write_text(
        "institution,account_label,symbol,name,quantity,currency,unit_cost,acquired_on\n"
        "broker,taxable,VOO,Vanguard S&P 500 ETF,1.5,美元,500.00,2026-07-15\n"
        "broker,taxable,510300,沪深300ETF,100,CNY,4.10,2026-07-15\n",
        encoding="utf-8",
    )

    summary = import_holdings_csv(db_path, csv_path)
    holdings = repo.list_holdings()

    assert summary.rows_seen == 2
    assert summary.imported_holdings == 2
    assert summary.linked_fx_holdings == 1
    assert summary.warnings == []
    assert holdings[0].symbol == "510300"
    assert holdings[0].currency == "CNY"
    assert holdings[0].fx_transaction_id is None
    assert holdings[1].symbol == "VOO"
    assert holdings[1].currency == "USD"
    assert holdings[1].fx_transaction_id is not None


def test_import_holdings_csv_reports_invalid_rows_and_unmatched_usd(tmp_path):
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text(
        "institution,account_label,symbol,name,quantity,currency,unit_cost,acquired_on\n"
        "broker,taxable,VOO,Vanguard S&P 500 ETF,1,USD,500,2026-07-15\n"
        "broker,taxable,BAD,Bad holding,not-a-number,USD,10,2026-07-15\n",
        encoding="utf-8",
    )

    summary = import_holdings_csv(db_path, csv_path)

    assert summary.rows_seen == 2
    assert summary.imported_holdings == 1
    assert summary.linked_fx_holdings == 0
    assert "row 2: no eligible USD FX transaction found" in summary.warnings
    assert "row 3:" in summary.warnings[1]


def test_import_holdings_csv_requires_all_columns(tmp_path):
    csv_path = tmp_path / "holdings.csv"
    csv_path.write_text("symbol,quantity\nVOO,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        import_holdings_csv(tmp_path / "steward.db", csv_path)


def test_manual_holdings_and_fx_links_appear_in_steward_report(tmp_path):
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "holdings.csv"
    report_dir = tmp_path / "reports"
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)
    repo.record_source_document("fx.pdf", "fx-source", "icbc", "pdf", "imported", [])
    repo.upsert_cash_transactions(
        "fx-source",
        [
            CashTransaction(
                institution="icbc",
                account_label="bank",
                transaction_date=date(2026, 7, 13),
                currency="USD",
                amount=Decimal("1000.00"),
                balance=Decimal("1000.00"),
                summary="个人购汇",
                raw_text="fx-in",
            )
        ],
    )
    fx_transaction_id = repo.list_cash_transactions()[0].id
    csv_path.write_text(
        "institution,account_label,symbol,name,quantity,currency,unit_cost,acquired_on\n"
        "broker,taxable,VOO,Vanguard S&P 500 ETF,1.5,USD,500.00,2026-07-15\n",
        encoding="utf-8",
    )
    import_holdings_csv(db_path, csv_path)

    report_path = generate_steward_report(
        db_path,
        report_dir,
        report_date=date(2026, 7, 18),
    )
    content = report_path.read_text(encoding="utf-8")

    assert "## 2A. Manual Holdings" in content
    assert "| broker | taxable | VOO | Vanguard S&P 500 ETF |" in content
    assert f"| USD | 1.50 | 500.00 | 750.00 | 2026-07-15 | {fx_transaction_id} |" in content
