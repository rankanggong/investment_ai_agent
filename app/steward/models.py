from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal


@dataclass(frozen=True)
class CashTransaction:
    institution: str
    account_label: str
    transaction_date: date
    currency: str
    amount: Decimal
    balance: Decimal | None
    summary: str
    transaction_time: time | None = None
    channel: str | None = None
    raw_text: str = ""


@dataclass(frozen=True)
class ParseResult:
    institution: str
    source_type: str
    transactions: list[CashTransaction]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StoredCashTransaction(CashTransaction):
    id: int = 0
    source_hash: str = ""


@dataclass(frozen=True)
class Holding:
    institution: str
    account_label: str
    symbol: str
    name: str
    quantity: Decimal
    currency: str
    unit_cost: Decimal
    acquired_on: date
    fx_transaction_id: int | None = None


@dataclass(frozen=True)
class StoredHolding(Holding):
    id: int = 0


@dataclass(frozen=True)
class CashPosition:
    institution: str
    account_label: str
    currency: str
    balance: Decimal
    as_of_date: date
    notes: str = ""


@dataclass(frozen=True)
class HoldingPosition:
    institution: str
    account_label: str
    symbol: str
    name: str
    quantity: Decimal
    currency: str
    unit_cost: Decimal
    as_of_date: date
    acquired_on: date | None = None
    notes: str = ""

    @property
    def total_cost(self) -> Decimal:
        return self.quantity * self.unit_cost


@dataclass(frozen=True)
class FxConversion:
    institution: str
    account_label: str
    fx_date: date
    sold_currency: str
    sold_amount: Decimal
    bought_currency: str
    bought_amount: Decimal
    fee_currency: str | None = None
    fee_amount: Decimal = Decimal("0")
    notes: str = ""

    @property
    def effective_rate(self) -> Decimal:
        return self.sold_amount / self.bought_amount


@dataclass(frozen=True)
class StewardState:
    cash_positions: list[CashPosition]
    holdings: list[HoldingPosition]
    fx_conversions: list[FxConversion]


@dataclass(frozen=True)
class PortfolioReportState:
    """The supplied steward state used by the daily report."""

    holdings: list[HoldingPosition]
    fx_conversions: list[FxConversion]
    cash_positions: list[CashPosition] = field(default_factory=list)
