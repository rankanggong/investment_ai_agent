import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.steward.models import (
    CashPosition,
    FxConversion,
    HoldingPosition,
    StewardState,
)


_REQUIRED_COLUMNS = {
    "record_type",
    "as_of_date",
    "institution",
    "account_label",
    "currency",
    "cash_balance",
    "symbol",
    "asset_name",
    "quantity",
    "unit_cost",
    "acquired_on",
    "fx_date",
    "sold_currency",
    "sold_amount",
    "bought_currency",
    "bought_amount",
    "fee_currency",
    "fee_amount",
    "notes",
}
_CURRENCY_ALIASES = {
    "RMB": "CNY",
    "人民币": "CNY",
    "美元": "USD",
    "US$": "USD",
    "$": "USD",
    "港币": "HKD",
    "港元": "HKD",
}


def read_steward_state_csv(csv_path: Path) -> StewardState:
    cash_positions: list[CashPosition] = []
    holdings: list[HoldingPosition] = []
    fx_conversions: list[FxConversion] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(_REQUIRED_COLUMNS - set(reader.fieldnames or []))
        if missing:
            raise ValueError(
                "steward state CSV missing required columns: " + ", ".join(missing)
            )
        for row_number, source_row in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in source_row.items()}
            if not any(row.values()):
                continue
            try:
                record_type = row["record_type"].casefold()
                if record_type == "cash":
                    cash_positions.append(_parse_cash(row))
                elif record_type == "holding":
                    holdings.append(_parse_holding(row))
                elif record_type == "fx":
                    fx_conversions.append(_parse_fx(row))
                else:
                    raise ValueError(
                        "record_type must be cash, holding, or fx"
                    )
            except ValueError as exc:
                raise ValueError(f"row {row_number}: {exc}") from exc

    return StewardState(
        cash_positions=cash_positions,
        holdings=holdings,
        fx_conversions=fx_conversions,
    )


def _parse_cash(row: dict[str, str]) -> CashPosition:
    _require(row, "as_of_date", "institution", "account_label", "currency", "cash_balance")
    return CashPosition(
        institution=row["institution"],
        account_label=row["account_label"],
        currency=normalize_currency(row["currency"]),
        balance=_decimal(row["cash_balance"], "cash_balance"),
        as_of_date=_date(row["as_of_date"], "as_of_date"),
        notes=row["notes"],
    )


def _parse_holding(row: dict[str, str]) -> HoldingPosition:
    _require(
        row,
        "as_of_date",
        "institution",
        "account_label",
        "currency",
        "symbol",
        "asset_name",
        "quantity",
        "unit_cost",
    )
    quantity = _decimal(row["quantity"], "quantity")
    unit_cost = _decimal(row["unit_cost"], "unit_cost")
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    if unit_cost < 0:
        raise ValueError("unit_cost must not be negative")
    return HoldingPosition(
        institution=row["institution"],
        account_label=row["account_label"],
        symbol=row["symbol"].upper(),
        name=row["asset_name"],
        quantity=quantity,
        currency=normalize_currency(row["currency"]),
        unit_cost=unit_cost,
        as_of_date=_date(row["as_of_date"], "as_of_date"),
        acquired_on=_date(row["acquired_on"], "acquired_on")
        if row["acquired_on"]
        else None,
        notes=row["notes"],
    )


def _parse_fx(row: dict[str, str]) -> FxConversion:
    _require(
        row,
        "institution",
        "account_label",
        "fx_date",
        "sold_currency",
        "sold_amount",
        "bought_currency",
        "bought_amount",
    )
    sold_amount = _decimal(row["sold_amount"], "sold_amount")
    bought_amount = _decimal(row["bought_amount"], "bought_amount")
    fee_amount = _decimal(row["fee_amount"], "fee_amount") if row["fee_amount"] else Decimal("0")
    if sold_amount <= 0 or bought_amount <= 0:
        raise ValueError("sold_amount and bought_amount must be greater than zero")
    if fee_amount < 0:
        raise ValueError("fee_amount must not be negative")
    if fee_amount and not row["fee_currency"]:
        raise ValueError("fee_currency is required when fee_amount is non-zero")
    return FxConversion(
        institution=row["institution"],
        account_label=row["account_label"],
        fx_date=_date(row["fx_date"], "fx_date"),
        sold_currency=normalize_currency(row["sold_currency"]),
        sold_amount=sold_amount,
        bought_currency=normalize_currency(row["bought_currency"]),
        bought_amount=bought_amount,
        fee_currency=normalize_currency(row["fee_currency"])
        if row["fee_currency"]
        else None,
        fee_amount=fee_amount,
        notes=row["notes"],
    )


def normalize_currency(value: str) -> str:
    stripped = value.strip()
    return _CURRENCY_ALIASES.get(stripped, stripped.upper())


def _require(row: dict[str, str], *fields: str) -> None:
    missing = [field for field in fields if not row[field]]
    if missing:
        raise ValueError("missing required values: " + ", ".join(missing))


def _decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a decimal number") from exc


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD") from exc
