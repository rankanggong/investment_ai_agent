from dataclasses import dataclass
from decimal import Decimal

from app.steward.models import StoredCashTransaction


_MAX_DATE_GAP_DAYS = 3
_MIN_AMOUNT_TOLERANCE = Decimal("1.00")
_RELATIVE_AMOUNT_TOLERANCE = Decimal("0.001")


@dataclass(frozen=True)
class AccountProfile:
    institution: str
    account_label: str
    currency: str
    ownership: str
    role: str


@dataclass(frozen=True)
class TransferDecision:
    outgoing_transaction_id: int
    incoming_transaction_id: int
    status: str


@dataclass(frozen=True)
class TransferMatch:
    outgoing_transaction_id: int
    incoming_transaction_id: int
    currency: str
    amount: Decimal
    fee: Decimal
    date_gap_days: int
    status: str
    reason: str


@dataclass(frozen=True)
class ReconciliationResult:
    confirmed: list[TransferMatch]
    suggested: list[TransferMatch]
    warnings: list[str]


def reconcile_transfers(
    transactions: list[StoredCashTransaction],
    accounts: list[AccountProfile],
    decisions: list[TransferDecision],
) -> ReconciliationResult:
    """Link statement rows without changing the imported facts."""
    transactions_by_id = {transaction.id: transaction for transaction in transactions}
    account_keys = {
        (account.institution, account.account_label, account.currency)
        for account in accounts
        if account.ownership == "owned"
    }
    rejected_pairs = {
        (decision.outgoing_transaction_id, decision.incoming_transaction_id)
        for decision in decisions
        if decision.status == "rejected"
    }
    confirmed: list[TransferMatch] = []
    used_ids: set[int] = set()
    warnings: list[str] = []

    for decision in decisions:
        if decision.status != "confirmed":
            continue
        outgoing = transactions_by_id.get(decision.outgoing_transaction_id)
        incoming = transactions_by_id.get(decision.incoming_transaction_id)
        if outgoing is None or incoming is None:
            warnings.append(
                "Confirmed transfer decision references a missing statement transaction: "
                f"{decision.outgoing_transaction_id}->{decision.incoming_transaction_id}."
            )
            continue
        if (
            _account_key(outgoing) not in account_keys
            or _account_key(incoming) not in account_keys
        ):
            warnings.append(
                "Confirmed transfer decision legs are not both registered as owned: "
                f"{decision.outgoing_transaction_id}->{decision.incoming_transaction_id}."
            )
            continue
        if _same_account(outgoing, incoming):
            warnings.append(
                "Confirmed transfer decision references the same account twice: "
                f"{decision.outgoing_transaction_id}->{decision.incoming_transaction_id}."
            )
            continue
        match = _build_match(outgoing, incoming, status="confirmed", require_candidate=False)
        if match is None:
            warnings.append(
                "Confirmed transfer decision has incompatible statement legs: "
                f"{decision.outgoing_transaction_id}->{decision.incoming_transaction_id}."
            )
            continue
        if outgoing.id in used_ids or incoming.id in used_ids:
            warnings.append(
                "Confirmed transfer decision reuses a statement transaction: "
                f"{decision.outgoing_transaction_id}->{decision.incoming_transaction_id}."
            )
            continue
        confirmed.append(match)
        used_ids.update((outgoing.id, incoming.id))

    candidates: list[tuple[Decimal, int, int, int, TransferMatch]] = []
    outgoing_legs = [transaction for transaction in transactions if transaction.amount < 0]
    incoming_legs = [transaction for transaction in transactions if transaction.amount > 0]
    for outgoing in outgoing_legs:
        if outgoing.id in used_ids or _account_key(outgoing) not in account_keys:
            continue
        for incoming in incoming_legs:
            pair = (outgoing.id, incoming.id)
            if (
                incoming.id in used_ids
                or pair in rejected_pairs
                or _account_key(incoming) not in account_keys
                or _same_account(outgoing, incoming)
            ):
                continue
            match = _build_match(outgoing, incoming, status="suggested", require_candidate=True)
            if match is None:
                continue
            candidates.append(
                (
                    match.fee,
                    match.date_gap_days,
                    outgoing.id,
                    incoming.id,
                    match,
                )
            )

    suggested: list[TransferMatch] = []
    for _, _, outgoing_id, incoming_id, match in sorted(candidates):
        if outgoing_id in used_ids or incoming_id in used_ids:
            continue
        suggested.append(match)
        used_ids.update((outgoing_id, incoming_id))

    return ReconciliationResult(
        confirmed=confirmed,
        suggested=suggested,
        warnings=warnings,
    )


def _build_match(
    outgoing: StoredCashTransaction,
    incoming: StoredCashTransaction,
    status: str,
    require_candidate: bool,
) -> TransferMatch | None:
    if outgoing.amount >= 0 or incoming.amount <= 0 or outgoing.currency != incoming.currency:
        return None
    date_gap = abs((incoming.transaction_date - outgoing.transaction_date).days)
    outgoing_amount = -outgoing.amount
    incoming_amount = incoming.amount
    if incoming_amount > outgoing_amount:
        return None
    fee = outgoing_amount - incoming_amount
    tolerance = max(
        _MIN_AMOUNT_TOLERANCE,
        max(outgoing_amount, incoming_amount) * _RELATIVE_AMOUNT_TOLERANCE,
    )
    if require_candidate and (date_gap > _MAX_DATE_GAP_DAYS or fee > tolerance):
        return None
    return TransferMatch(
        outgoing_transaction_id=outgoing.id,
        incoming_transaction_id=incoming.id,
        currency=outgoing.currency,
        amount=min(outgoing_amount, incoming_amount),
        fee=fee,
        date_gap_days=date_gap,
        status=status,
        reason=(
            "Manual decision."
            if status == "confirmed"
            else "Owned accounts; opposite directions; compatible amount, currency, and date."
        ),
    )


def _account_key(transaction: StoredCashTransaction) -> tuple[str, str, str]:
    return (
        transaction.institution,
        transaction.account_label,
        transaction.currency,
    )


def _same_account(
    left: StoredCashTransaction,
    right: StoredCashTransaction,
) -> bool:
    return (
        left.institution == right.institution
        and left.account_label == right.account_label
        and left.currency == right.currency
    )
