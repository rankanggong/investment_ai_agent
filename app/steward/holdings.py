import csv
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.steward.models import Holding, StoredCashTransaction
from app.steward.storage import StewardRepository, initialize_steward_database


_REQUIRED_COLUMNS = {
    "institution",
    "account_label",
    "symbol",
    "name",
    "quantity",
    "currency",
    "unit_cost",
    "acquired_on",
}
_CURRENCY_ALIASES = {
    "美元": "USD",
    "US$": "USD",
    "$": "USD",
    "人民币": "CNY",
    "RMB": "CNY",
    "港币": "HKD",
    "港元": "HKD",
}
_FX_SUMMARY_MARKERS = ("购汇", "结汇", "外汇", "fx", "foreign exchange", "currency exchange")


@dataclass(frozen=True)
class HoldingImportSummary:
    rows_seen: int
    imported_holdings: int
    linked_fx_holdings: int
    warnings: list[str] = field(default_factory=list)


def import_holdings_csv(db_path: Path, csv_path: Path) -> HoldingImportSummary:
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)
    transactions = repo.list_cash_transactions()
    rows_seen = 0
    imported_holdings = 0
    linked_fx_holdings = 0
    warnings: list[str] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(_REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(
                "holdings CSV missing required columns: " + ", ".join(missing)
            )

        for row_number, row in enumerate(reader, start=2):
            rows_seen += 1
            try:
                holding = _parse_holding(row)
            except ValueError as exc:
                warnings.append(f"row {row_number}: {exc}")
                continue

            if holding.currency == "USD":
                fx_transaction = match_usd_fx_transaction(holding, transactions)
                if fx_transaction is None:
                    warnings.append(
                        f"row {row_number}: no eligible USD FX transaction found"
                    )
                else:
                    holding = replace(
                        holding,
                        fx_transaction_id=fx_transaction.id,
                    )
                    linked_fx_holdings += 1

            repo.upsert_holding(holding)
            imported_holdings += 1

    return HoldingImportSummary(
        rows_seen=rows_seen,
        imported_holdings=imported_holdings,
        linked_fx_holdings=linked_fx_holdings,
        warnings=warnings,
    )


def match_usd_fx_transaction(
    holding: Holding,
    transactions: list[StoredCashTransaction],
) -> StoredCashTransaction | None:
    if normalize_currency(holding.currency) != "USD":
        return None

    candidates = [
        transaction
        for transaction in transactions
        if normalize_currency(transaction.currency) == "USD"
        and transaction.amount > 0
        and transaction.transaction_date <= holding.acquired_on
        and _looks_like_fx(transaction.summary)
    ]
    if not candidates:
        return None

    return min(
        candidates,
        key=lambda transaction: (
            0
            if (
                transaction.institution == holding.institution
                and transaction.account_label == holding.account_label
            )
            else 1,
            0 if transaction.institution == holding.institution else 1,
            (holding.acquired_on - transaction.transaction_date).days,
            -transaction.id,
        ),
    )


def normalize_currency(value: str) -> str:
    stripped = value.strip()
    return _CURRENCY_ALIASES.get(stripped, stripped.upper())


def _parse_holding(row: dict[str, str | None]) -> Holding:
    values = {key: (row.get(key) or "").strip() for key in _REQUIRED_COLUMNS}
    empty = sorted(key for key, value in values.items() if not value)
    if empty:
        raise ValueError("empty required values: " + ", ".join(empty))

    try:
        quantity = Decimal(values["quantity"])
        unit_cost = Decimal(values["unit_cost"])
    except InvalidOperation as exc:
        raise ValueError("quantity and unit_cost must be decimal numbers") from exc
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    if unit_cost < 0:
        raise ValueError("unit_cost must not be negative")
    try:
        acquired_on = date.fromisoformat(values["acquired_on"])
    except ValueError as exc:
        raise ValueError("acquired_on must use YYYY-MM-DD") from exc

    return Holding(
        institution=values["institution"],
        account_label=values["account_label"],
        symbol=values["symbol"].upper(),
        name=values["name"],
        quantity=quantity,
        currency=normalize_currency(values["currency"]),
        unit_cost=unit_cost,
        acquired_on=acquired_on,
    )


def _looks_like_fx(summary: str) -> bool:
    normalized = summary.casefold()
    return any(marker in normalized for marker in _FX_SUMMARY_MARKERS)
