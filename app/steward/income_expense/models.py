from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Literal


EntryType = Literal["income", "expense"]
EntryCategory = Literal["income", "essential", "discretionary", "investment"]


@dataclass(frozen=True)
class IncomeExpenseEntry:
    institution: str
    account_label: str
    transaction_date: date
    transaction_time: time | None
    currency: str
    entry_type: EntryType
    category: EntryCategory
    amount: Decimal
    balance: Decimal | None
    summary: str
    channel: str | None
    raw_text: str
