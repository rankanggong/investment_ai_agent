from datetime import date
from decimal import Decimal

from app.steward.analyzer import analyze_cash_state
from app.steward.job import generate_steward_report, import_steward_inbox
from app.steward.models import CashTransaction
from app.steward.reconciliation import AccountProfile, TransferDecision, reconcile_transfers
from app.steward.storage import StewardRepository


def test_import_steward_inbox_imports_supported_local_files_idempotently(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "支付宝交易明细.csv").write_text(
        "交易创建时间,金额（元）,收/支,交易状态,交易对方,商品名称\n"
        "2026-07-15 09:30:00,120.00,收入,交易成功,示例用户,转账收款\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "steward.db"

    first = import_steward_inbox(db_path, inbox)
    second = import_steward_inbox(db_path, inbox)

    repo = StewardRepository(db_path)
    transactions = repo.list_cash_transactions()
    assert first.documents_seen == 1
    assert first.imported_transactions == 1
    assert second.documents_seen == 1
    assert second.imported_transactions == 0
    assert repo.count_source_documents() == 1
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("120.00")


def test_analyze_cash_state_and_generate_steward_report(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "支付宝交易明细.csv").write_text(
        "交易创建时间,金额（元）,收/支,交易状态,交易对方,商品名称\n"
        "2026-07-15 09:30:00,120.00,收入,交易成功,示例用户,转账收款\n"
        "2026-07-15 10:00:00,20.00,支出,交易成功,示例商户,午餐\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "steward.db"
    report_dir = tmp_path / "reports"
    import_steward_inbox(db_path, inbox)

    transactions = StewardRepository(db_path).list_cash_transactions()
    summary = analyze_cash_state(transactions)
    path = generate_steward_report(db_path, report_dir, report_date=date(2026, 7, 15))

    assert summary.cashflows[0].currency == "CNY"
    assert summary.cashflows[0].inflow == Decimal("120.00")
    assert summary.cashflows[0].outflow == Decimal("20.00")
    assert summary.cashflows[0].net == Decimal("100.00")
    content = path.read_text(encoding="utf-8")
    assert "# Portfolio Steward Report - 2026-07-15" in content
    assert "## 3. External Cashflow By Currency" in content
    assert "| CNY | 120.00 | 20.00 | 100.00 |" in content
    assert "No multi-currency cash exposure detected" in content


def test_confirmed_transfer_is_excluded_from_external_cashflow_and_reported(tmp_path):
    db_path = tmp_path / "steward.db"
    report_dir = tmp_path / "reports"
    repo = StewardRepository(db_path)
    from app.steward.storage import initialize_steward_database

    initialize_steward_database(db_path)
    repo.record_source_document("bank.pdf", "bank-source", "cmb", "pdf", "imported", [])
    repo.record_source_document(
        "broker.csv", "broker-source", "broker", "csv", "imported", []
    )
    repo.upsert_cash_transactions(
        "bank-source",
        [
            CashTransaction(
                institution="cmb",
                account_label="bank",
                transaction_date=date(2026, 7, 15),
                currency="CNY",
                amount=Decimal("-10000.00"),
                balance=Decimal("5000.00"),
                summary="broker funding",
                raw_text="bank-out",
            )
        ],
    )
    repo.upsert_cash_transactions(
        "broker-source",
        [
            CashTransaction(
                institution="broker",
                account_label="cash",
                transaction_date=date(2026, 7, 16),
                currency="CNY",
                amount=Decimal("9999.50"),
                balance=Decimal("9999.50"),
                summary="deposit",
                raw_text="broker-in",
            )
        ],
    )
    transactions = repo.list_cash_transactions()
    outgoing, incoming = transactions
    accounts = [
        AccountProfile("cmb", "bank", "CNY", "owned", "bank"),
        AccountProfile("broker", "cash", "CNY", "owned", "brokerage"),
    ]
    decision = TransferDecision(outgoing.id, incoming.id, "confirmed")
    for account in accounts:
        repo.upsert_account_profile(account)
    repo.upsert_transfer_decision(decision)
    repo.upsert_transfer_decision(TransferDecision(999, 1000, "confirmed"))

    reconciliation = reconcile_transfers(transactions, accounts, [decision])
    state = analyze_cash_state(transactions, reconciliation)
    path = generate_steward_report(db_path, report_dir, date(2026, 7, 17))
    content = path.read_text(encoding="utf-8")

    assert state.statement_cashflows[0].inflow == Decimal("9999.50")
    assert state.statement_cashflows[0].outflow == Decimal("10000.00")
    assert state.cashflows[0].inflow == Decimal("0")
    assert state.cashflows[0].outflow == Decimal("0.50")
    assert state.cashflows[0].net == Decimal("-0.50")
    assert len(state.confirmed_transfers) == 1
    assert "## 4. Statement Cashflow By Currency" in content
    assert "| CNY | 9999.50 | 10000.00 | -0.50 |" in content
    assert "## 5. Confirmed Internal Transfers" in content
    assert f"| {outgoing.id} | {incoming.id} |" in content
    assert "| CNY | 0.00 | 0.50 | -0.50 |" in content
    assert "references a missing statement transaction: 999->1000" in content


def test_suggested_transfer_does_not_change_external_cashflow():
    from app.steward.models import StoredCashTransaction

    transactions = [
        StoredCashTransaction(
            id=1,
            institution="cmb",
            account_label="bank",
            transaction_date=date(2026, 7, 15),
            currency="CNY",
            amount=Decimal("-100.00"),
            balance=None,
            summary="transfer",
        ),
        StoredCashTransaction(
            id=2,
            institution="broker",
            account_label="cash",
            transaction_date=date(2026, 7, 15),
            currency="CNY",
            amount=Decimal("100.00"),
            balance=None,
            summary="deposit",
        ),
    ]
    accounts = [
        AccountProfile("cmb", "bank", "CNY", "owned", "bank"),
        AccountProfile("broker", "cash", "CNY", "owned", "brokerage"),
    ]

    reconciliation = reconcile_transfers(transactions, accounts, [])
    state = analyze_cash_state(transactions, reconciliation)

    assert len(state.suggested_transfers) == 1
    assert state.cashflows == state.statement_cashflows
