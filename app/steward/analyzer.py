from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.steward.models import StoredCashTransaction
from app.steward.reconciliation import ReconciliationResult, TransferMatch


@dataclass(frozen=True)
class AccountBalance:
    institution: str
    account_label: str
    currency: str
    balance: Decimal
    as_of: date


@dataclass(frozen=True)
class CurrencyCashflow:
    currency: str
    inflow: Decimal
    outflow: Decimal
    net: Decimal


@dataclass(frozen=True)
class TransferActivity:
    outgoing_transaction_id: int
    incoming_transaction_id: int
    outgoing_institution: str
    outgoing_account: str
    outgoing_date: date
    incoming_institution: str
    incoming_account: str
    incoming_date: date
    currency: str
    amount: Decimal
    fee: Decimal
    status: str


@dataclass(frozen=True)
class CashState:
    account_balances: list[AccountBalance]
    statement_cashflows: list[CurrencyCashflow]
    cashflows: list[CurrencyCashflow]
    recent_transactions: list[StoredCashTransaction]
    confirmed_transfers: list[TransferActivity]
    suggested_transfers: list[TransferActivity]
    reconciliation_warnings: list[str]
    fx_review: list[str]


def analyze_cash_state(
    transactions: list[StoredCashTransaction],
    reconciliation: ReconciliationResult | None = None,
) -> CashState:
    balances_by_account: dict[tuple[str, str, str], AccountBalance] = {}

    for txn in transactions:
        if txn.balance is not None:
            key = (txn.institution, txn.account_label, txn.currency)
            current = balances_by_account.get(key)
            if current is None or txn.transaction_date >= current.as_of:
                balances_by_account[key] = AccountBalance(
                    institution=txn.institution,
                    account_label=txn.account_label,
                    currency=txn.currency,
                    balance=txn.balance,
                    as_of=txn.transaction_date,
                )

    effective_reconciliation = reconciliation or ReconciliationResult([], [], [])
    confirmed_ids = {
        transaction_id
        for match in effective_reconciliation.confirmed
        for transaction_id in (
            match.outgoing_transaction_id,
            match.incoming_transaction_id,
        )
    }
    currencies = {transaction.currency for transaction in transactions}
    statement_cashflows = _summarize_cashflows(transactions, currencies=currencies)
    transfer_fees: dict[str, Decimal] = {}
    for match in effective_reconciliation.confirmed:
        transfer_fees[match.currency] = transfer_fees.get(
            match.currency, Decimal("0")
        ) + match.fee
    cashflows = _summarize_cashflows(
        transactions,
        currencies=currencies,
        excluded_ids=confirmed_ids,
        additional_outflows=transfer_fees,
    )
    transactions_by_id = {transaction.id: transaction for transaction in transactions}
    fx_review = _build_fx_review(currencies)
    return CashState(
        account_balances=sorted(
            balances_by_account.values(),
            key=lambda item: (item.institution, item.account_label, item.currency),
        ),
        statement_cashflows=statement_cashflows,
        cashflows=cashflows,
        recent_transactions=sorted(
            transactions,
            key=lambda item: (
                item.transaction_date,
                item.transaction_time is not None,
                item.transaction_time,
            ),
            reverse=True,
        )[:10],
        confirmed_transfers=_build_transfer_activities(
            effective_reconciliation.confirmed,
            transactions_by_id,
        ),
        suggested_transfers=_build_transfer_activities(
            effective_reconciliation.suggested,
            transactions_by_id,
        ),
        reconciliation_warnings=effective_reconciliation.warnings,
        fx_review=fx_review,
    )


def _summarize_cashflows(
    transactions: list[StoredCashTransaction],
    currencies: set[str],
    excluded_ids: set[int] | None = None,
    additional_outflows: dict[str, Decimal] | None = None,
) -> list[CurrencyCashflow]:
    excluded = excluded_ids or set()
    totals_by_currency = {
        currency: {"inflow": Decimal("0"), "outflow": Decimal("0")}
        for currency in currencies
    }
    for transaction in transactions:
        if transaction.id in excluded:
            continue
        totals = totals_by_currency[transaction.currency]
        if transaction.amount >= 0:
            totals["inflow"] += transaction.amount
        else:
            totals["outflow"] += -transaction.amount
    for currency, amount in (additional_outflows or {}).items():
        totals_by_currency.setdefault(
            currency,
            {"inflow": Decimal("0"), "outflow": Decimal("0")},
        )["outflow"] += amount
    return [
        CurrencyCashflow(
            currency=currency,
            inflow=totals["inflow"],
            outflow=totals["outflow"],
            net=totals["inflow"] - totals["outflow"],
        )
        for currency, totals in sorted(totals_by_currency.items())
    ]


def _build_transfer_activities(
    matches: list[TransferMatch],
    transactions_by_id: dict[int, StoredCashTransaction],
) -> list[TransferActivity]:
    activities: list[TransferActivity] = []
    for match in matches:
        outgoing = transactions_by_id.get(match.outgoing_transaction_id)
        incoming = transactions_by_id.get(match.incoming_transaction_id)
        if outgoing is None or incoming is None:
            continue
        activities.append(
            TransferActivity(
                outgoing_transaction_id=outgoing.id,
                incoming_transaction_id=incoming.id,
                outgoing_institution=outgoing.institution,
                outgoing_account=outgoing.account_label,
                outgoing_date=outgoing.transaction_date,
                incoming_institution=incoming.institution,
                incoming_account=incoming.account_label,
                incoming_date=incoming.transaction_date,
                currency=match.currency,
                amount=match.amount,
                fee=match.fee,
                status=match.status,
            )
        )
    return activities


def _build_fx_review(currencies: set[str]) -> list[str]:
    if not currencies:
        return ["No cash transactions imported yet, so FX exposure is unknown."]
    if len(currencies) == 1:
        return [
            "No multi-currency cash exposure detected in imported transactions.",
            "FX suggestions need at least two currencies or configured target bands.",
        ]
    return [
        "Multiple cash currencies detected. Review balances against target bands before any conversion.",
        "No automatic FX action is generated by the steward.",
    ]
