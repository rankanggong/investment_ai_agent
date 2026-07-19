from datetime import date
from decimal import Decimal

from app.steward.models import StoredCashTransaction
from app.steward.reconciliation import (
    AccountProfile,
    TransferDecision,
    reconcile_transfers,
)


def _transaction(
    transaction_id: int,
    institution: str,
    account: str,
    amount: str,
    transaction_date: date = date(2026, 7, 15),
    currency: str = "CNY",
) -> StoredCashTransaction:
    return StoredCashTransaction(
        id=transaction_id,
        institution=institution,
        account_label=account,
        transaction_date=transaction_date,
        currency=currency,
        amount=Decimal(amount),
        balance=None,
        summary="transfer",
        raw_text=f"{transaction_id}:{amount}",
        source_hash=f"source-{transaction_id}",
    )


def _owned(institution: str, account: str, currency: str = "CNY") -> AccountProfile:
    return AccountProfile(
        institution=institution,
        account_label=account,
        currency=currency,
        ownership="owned",
        role="bank",
    )


def test_reconcile_transfers_suggests_equal_and_opposite_owned_account_legs():
    outgoing = _transaction(1, "cmb", "bank", "-10000.00")
    incoming = _transaction(
        2,
        "broker",
        "cash",
        "9999.50",
        transaction_date=date(2026, 7, 17),
    )

    result = reconcile_transfers(
        [outgoing, incoming],
        [_owned("cmb", "bank"), _owned("broker", "cash")],
        [],
    )

    assert result.confirmed == []
    assert len(result.suggested) == 1
    match = result.suggested[0]
    assert match.outgoing_transaction_id == 1
    assert match.incoming_transaction_id == 2
    assert match.amount == Decimal("9999.50")
    assert match.fee == Decimal("0.50")
    assert match.date_gap_days == 2
    assert match.status == "suggested"


def test_reconcile_transfers_requires_distinct_owned_accounts_and_same_currency():
    transactions = [
        _transaction(1, "cmb", "bank", "-100.00"),
        _transaction(2, "cmb", "bank", "100.00"),
        _transaction(3, "broker", "cash", "100.00", currency="USD"),
        _transaction(4, "unknown", "wallet", "100.00"),
    ]

    result = reconcile_transfers(
        transactions,
        [_owned("cmb", "bank"), _owned("broker", "cash", "USD")],
        [],
    )

    assert result.confirmed == []
    assert result.suggested == []


def test_reconcile_transfers_does_not_treat_excess_incoming_value_as_a_fee():
    result = reconcile_transfers(
        [
            _transaction(1, "cmb", "bank", "-100.00"),
            _transaction(2, "broker", "cash", "100.50"),
        ],
        [_owned("cmb", "bank"), _owned("broker", "cash")],
        [],
    )

    assert result.suggested == []


def test_reconcile_transfers_uses_each_statement_transaction_at_most_once():
    result = reconcile_transfers(
        [
            _transaction(1, "cmb", "bank", "-100.00"),
            _transaction(2, "broker-a", "cash", "100.00"),
            _transaction(3, "broker-b", "cash", "100.00"),
        ],
        [
            _owned("cmb", "bank"),
            _owned("broker-a", "cash"),
            _owned("broker-b", "cash"),
        ],
        [],
    )

    assert len(result.suggested) == 1


def test_reconcile_transfers_applies_confirmed_and_rejected_decisions():
    transactions = [
        _transaction(1, "cmb", "bank", "-100.00"),
        _transaction(2, "broker", "cash", "100.00"),
        _transaction(3, "icbc", "bank", "-200.00"),
        _transaction(4, "broker", "cash", "200.00"),
    ]
    accounts = [
        _owned("cmb", "bank"),
        _owned("icbc", "bank"),
        _owned("broker", "cash"),
    ]
    decisions = [
        TransferDecision(1, 2, "confirmed"),
        TransferDecision(3, 4, "rejected"),
    ]

    result = reconcile_transfers(transactions, accounts, decisions)

    assert [(item.outgoing_transaction_id, item.incoming_transaction_id) for item in result.confirmed] == [(1, 2)]
    assert result.confirmed[0].status == "confirmed"
    assert result.suggested == []


def test_confirmed_decision_requires_both_accounts_to_remain_owned():
    result = reconcile_transfers(
        [
            _transaction(1, "cmb", "bank", "-100.00"),
            _transaction(2, "broker", "cash", "100.00"),
        ],
        [_owned("cmb", "bank")],
        [TransferDecision(1, 2, "confirmed")],
    )

    assert result.confirmed == []
    assert "not both registered as owned" in result.warnings[0]
