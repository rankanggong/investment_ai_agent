from datetime import date
from decimal import Decimal

from app.steward.models import CashTransaction, Holding
from app.steward.reconciliation import AccountProfile, TransferDecision
from app.steward.storage import StewardRepository, initialize_steward_database


def test_steward_repository_records_documents_and_transactions_idempotently(tmp_path):
    db_path = tmp_path / "steward.db"
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)

    first_id = repo.record_source_document(
        path="/tmp/example.pdf",
        source_hash="abc123",
        institution="cmb",
        source_type="pdf",
        status="imported",
        warnings=[],
    )
    second_id = repo.record_source_document(
        path="/tmp/example-copy.pdf",
        source_hash="abc123",
        institution="cmb",
        source_type="pdf",
        status="imported",
        warnings=[],
    )
    repo.upsert_cash_transactions(
        "abc123",
        [
            CashTransaction(
                institution="cmb",
                account_label="6214********3949",
                transaction_date=date(2026, 7, 13),
                transaction_time=None,
                currency="CNY",
                amount=Decimal("-88.50"),
                balance=Decimal("1011.50"),
                summary="快捷支付",
                raw_text="2026-07-13 CNY -88.50 1,011.50 快捷支付",
            )
        ],
    )
    repo.upsert_cash_transactions(
        "abc123",
        [
            CashTransaction(
                institution="cmb",
                account_label="6214********3949",
                transaction_date=date(2026, 7, 13),
                transaction_time=None,
                currency="CNY",
                amount=Decimal("-88.50"),
                balance=Decimal("1011.50"),
                summary="快捷支付",
                raw_text="2026-07-13 CNY -88.50 1,011.50 快捷支付",
            )
        ],
    )

    assert first_id == second_id
    assert repo.count_source_documents() == 1
    transactions = repo.list_cash_transactions()
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("-88.50")
    assert transactions[0].balance == Decimal("1011.50")
    assert transactions[0].source_hash == "abc123"
    assert transactions[0].id > 0


def test_steward_repository_upserts_account_profiles_and_transfer_decisions(tmp_path):
    db_path = tmp_path / "steward.db"
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)

    repo.upsert_account_profile(
        AccountProfile("cmb", "bank", "CNY", "owned", "bank")
    )
    repo.upsert_account_profile(
        AccountProfile("cmb", "bank", "CNY", "owned", "primary-bank")
    )
    repo.upsert_transfer_decision(TransferDecision(10, 20, "confirmed"))
    repo.upsert_transfer_decision(TransferDecision(10, 20, "rejected"))

    assert repo.list_account_profiles() == [
        AccountProfile("cmb", "bank", "CNY", "owned", "primary-bank")
    ]
    assert repo.list_transfer_decisions() == [
        TransferDecision(10, 20, "rejected")
    ]


def test_steward_repository_upserts_manual_holdings(tmp_path):
    db_path = tmp_path / "steward.db"
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)
    holding = Holding(
        institution="broker",
        account_label="taxable",
        symbol="VOO",
        name="Vanguard S&P 500 ETF",
        quantity=Decimal("2.5"),
        currency="USD",
        unit_cost=Decimal("500.00"),
        acquired_on=date(2026, 7, 13),
        fx_transaction_id=23,
    )

    repo.upsert_holding(holding)
    repo.upsert_holding(
        Holding(
            institution="broker",
            account_label="taxable",
            symbol="VOO",
            name="Vanguard S&P 500 ETF",
            quantity=Decimal("3.0"),
            currency="USD",
            unit_cost=Decimal("501.00"),
            acquired_on=date(2026, 7, 13),
            fx_transaction_id=24,
        )
    )

    holdings = repo.list_holdings()
    assert len(holdings) == 1
    assert holdings[0].id > 0
    assert holdings[0].symbol == "VOO"
    assert holdings[0].quantity == Decimal("3.0")
    assert holdings[0].unit_cost == Decimal("501.00")
    assert holdings[0].fx_transaction_id == 24
