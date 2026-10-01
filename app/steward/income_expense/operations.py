"""Operations shared by the CLI and future interactive adapters."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from app.steward.income_expense.models import EntryCategory, EntryType
from app.steward.income_expense.storage import (
    effective_entries_sql,
    initialize_income_expense_database,
)
from app.steward.parsers.registry import parse_statement_file

if TYPE_CHECKING:
    from app.steward.income_expense.job import (
        MonthlyAllowance,
        MonthlyIncomeExpenseSummary,
    )


_CATEGORIES = {"income", "essential", "discretionary", "investment", "excluded"}


@dataclass(frozen=True)
class ImportPreview:
    source_hash: str
    institution: str
    row_count: int
    first_date: date
    last_date: date
    income: Decimal
    essential: Decimal
    discretionary: Decimal
    investment: Decimal
    excluded: Decimal
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class BudgetSettings:
    month: str
    currency: str
    expected_income: Decimal | None = None
    essential_budget: Decimal | None = None
    investment_target: Decimal | None = None
    safety_buffer: Decimal | None = None


@dataclass(frozen=True)
class EntryView:
    reference: str
    transaction_date: date
    currency: str
    entry_type: EntryType
    category: str
    amount: Decimal
    summary: str


def preview_import(pdf_path: Path) -> ImportPreview:
    if pdf_path.suffix.lower() != ".pdf" or not pdf_path.is_file():
        raise ValueError("A readable PDF statement is required.")
    parsed = parse_statement_file(pdf_path)
    if not parsed.transactions:
        raise ValueError("No supported statement transactions were parsed.")
    from app.steward.income_expense.job import _hash_file, _to_entry

    entries = [_to_entry(transaction) for transaction in parsed.transactions]
    totals = {category: Decimal("0") for category in _CATEGORIES}
    for entry in entries:
        if entry.category != "investment" or entry.entry_type == "expense":
            totals[entry.category] += entry.amount
    return ImportPreview(
        source_hash=_hash_file(pdf_path),
        institution=parsed.institution,
        row_count=len(entries),
        first_date=min(entry.transaction_date for entry in entries),
        last_date=max(entry.transaction_date for entry in entries),
        income=totals["income"],
        essential=totals["essential"],
        discretionary=totals["discretionary"],
        investment=totals["investment"],
        excluded=totals["excluded"],
        warnings=tuple(parsed.warnings),
    )


def confirm_import(db_path: Path, pdf_path: Path, expected_hash: str, *, actor: str) -> int:
    _actor(actor)
    from app.steward.income_expense.job import _hash_file

    current_hash = _hash_file(pdf_path)
    if current_hash != expected_hash:
        raise ValueError("The PDF changed after preview; preview it again.")
    from app.steward.income_expense.job import import_income_expense_statement

    result = import_income_expense_statement(pdf_path, db_path=db_path)
    with _connect(db_path) as conn:
        _audit(
            conn, "confirm_import", expected_hash, actor, None,
            {"path": str(pdf_path), "parsed_entries": result.parsed_entries},
        )
    return result.parsed_entries


def list_entries(
    db_path: Path,
    month: str,
    *,
    currency: str = "CNY",
    limit: int = 50,
) -> list[EntryView]:
    _month(month)
    currency = _currency(currency)
    if limit < 1 or limit > 200:
        raise ValueError("Limit must be between 1 and 200.")
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT entry_kind, entry_id, transaction_date, currency, entry_type,
                   category, amount, summary
            FROM ({effective_entries_sql()})
            WHERE substr(transaction_date, 1, 7) = ? AND currency = ?
            ORDER BY transaction_date DESC, entry_kind, entry_id DESC
            LIMIT ?
            """,
            (month, currency, limit),
        ).fetchall()
    return [
        EntryView(
            reference=f"{kind}:{entry_id}",
            transaction_date=date.fromisoformat(day),
            currency=row_currency,
            entry_type=entry_type,
            category=category,
            amount=Decimal(amount),
            summary=summary,
        )
        for kind, entry_id, day, row_currency, entry_type, category, amount, summary
        in rows
    ]


def get_month_report(
    db_path: Path,
    month: str,
    *,
    as_of: date | None = None,
    currency: str = "CNY",
) -> tuple[MonthlyIncomeExpenseSummary, MonthlyAllowance]:
    from app.steward.income_expense.job import (
        calculate_monthly_allowance,
        summarize_month,
    )

    summary = summarize_month(db_path, month, currency=currency)
    return summary, calculate_monthly_allowance(db_path, summary, as_of=as_of)


def add_entry(
    db_path: Path,
    *,
    transaction_date: date,
    currency: str,
    entry_type: EntryType,
    category: EntryCategory | str,
    amount: Decimal,
    summary: str,
    actor: str,
    account_label: str = "",
) -> str:
    _validate_entry(entry_type, category, amount, summary)
    _actor(actor)
    currency = _currency(currency)
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO income_expense_manual_entries
              (transaction_date, currency, entry_type, category, amount,
               summary, account_label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction_date.isoformat(), currency, entry_type, category,
                str(amount), summary.strip(), account_label.strip(),
            ),
        )
        reference = f"manual:{cursor.lastrowid}"
        _audit(
            conn, "add_entry", reference, actor, None,
            {"date": transaction_date.isoformat(), "currency": currency,
             "entry_type": entry_type, "category": category, "amount": str(amount),
             "summary": summary.strip()},
        )
    return reference


def adjust_entry(
    db_path: Path,
    reference: str,
    *,
    actor: str,
    category: str | None = None,
    summary: str | None = None,
    transaction_date: date | None = None,
    amount: Decimal | None = None,
) -> None:
    _actor(actor)
    kind, entry_id = _reference(reference)
    if all(value is None for value in (category, summary, transaction_date, amount)):
        raise ValueError("Supply at least one field to adjust.")
    with _connect(db_path) as conn:
        table = (
            "income_expense_entries" if kind == "pdf"
            else "income_expense_manual_entries"
        )
        row = conn.execute(
            f"""
            SELECT e.entry_type, COALESCE(a.category, e.category),
                   COALESCE(a.summary, e.summary),
                   COALESCE(a.transaction_date, e.transaction_date),
                   COALESCE(a.amount, e.amount)
            FROM {table} e
            LEFT JOIN income_expense_adjustments a
              ON a.entry_kind = ? AND a.entry_id = e.id
            WHERE e.id = ?
            """,
            (kind, entry_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"Entry not found: {reference}")
        entry_type, old_category, old_summary, old_date, old_amount = row
        new_category = category if category is not None else old_category
        new_summary = summary.strip() if summary is not None else old_summary
        new_date = transaction_date.isoformat() if transaction_date else old_date
        new_amount = str(amount) if amount is not None else old_amount
        _validate_category(entry_type, new_category)
        if not new_summary:
            raise ValueError("Summary cannot be empty.")
        if amount is not None and (not amount.is_finite() or amount <= 0):
            raise ValueError("Amount must be finite and positive.")
        if (new_category, new_summary, new_date, Decimal(new_amount)) == (
            old_category, old_summary, old_date, Decimal(old_amount)
        ):
            return
        conn.execute(
            """
            INSERT INTO income_expense_adjustments
              (entry_kind, entry_id, transaction_date, amount, category, summary)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_kind, entry_id) DO UPDATE SET
              transaction_date = excluded.transaction_date,
              amount = excluded.amount,
              category = excluded.category, summary = excluded.summary,
              updated_at = CURRENT_TIMESTAMP
            """,
            (kind, entry_id, new_date, new_amount, new_category, new_summary),
        )
        _audit(
            conn, "adjust_entry", reference, actor,
            {"date": old_date, "amount": old_amount,
             "category": old_category, "summary": old_summary},
            {"date": new_date, "amount": new_amount,
             "category": new_category, "summary": new_summary},
        )


def set_budget(db_path: Path, settings: BudgetSettings, *, actor: str) -> None:
    _actor(actor)
    _month(settings.month)
    currency = _currency(settings.currency)
    for value in (
        settings.expected_income, settings.essential_budget,
        settings.investment_target, settings.safety_buffer,
    ):
        if value is not None and (not value.is_finite() or value < 0):
            raise ValueError("Budget amounts must be finite and nonnegative.")
    with _connect(db_path) as conn:
        before = _budget_row(conn, settings.month, currency)
        after = {
            "expected_income": _decimal_text(settings.expected_income),
            "essential_budget": _decimal_text(settings.essential_budget),
            "investment_target": _decimal_text(settings.investment_target),
            "safety_buffer": _decimal_text(settings.safety_buffer),
        }
        conn.execute(
            """
            INSERT INTO income_expense_budgets
              (month, currency, expected_income, essential_budget,
               investment_target, safety_buffer)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(month, currency) DO UPDATE SET
              expected_income = excluded.expected_income,
              essential_budget = excluded.essential_budget,
              investment_target = excluded.investment_target,
              safety_buffer = excluded.safety_buffer,
              updated_at = CURRENT_TIMESTAMP
            """,
            (settings.month, currency, *after.values()),
        )
        _audit(conn, "set_budget", f"{settings.month}:{currency}", actor, before, after)


def get_budget(db_path: Path, month: str, currency: str = "CNY") -> BudgetSettings | None:
    _month(month)
    currency = _currency(currency)
    with _connect(db_path) as conn:
        row = _budget_row(conn, month, currency)
    if row is None:
        return None
    return BudgetSettings(
        month, currency,
        **{key: Decimal(value) if value is not None else None
           for key, value in row.items()},
    )


def _budget_row(conn: sqlite3.Connection, month: str, currency: str) -> dict | None:
    row = conn.execute(
        """
        SELECT expected_income, essential_budget, investment_target, safety_buffer
        FROM income_expense_budgets WHERE month = ? AND currency = ?
        """,
        (month, currency),
    ).fetchone()
    return dict(zip(
        ("expected_income", "essential_budget", "investment_target", "safety_buffer"),
        row,
    )) if row else None


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    initialize_income_expense_database(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            yield conn


def _audit(conn, action: str, target: str, actor: str, before: dict | None, after: dict) -> None:
    conn.execute(
        """
        INSERT INTO income_expense_audit
          (action, target, actor, before_json, after_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (action, target, actor,
         json.dumps(before, ensure_ascii=False) if before is not None else None,
         json.dumps(after, ensure_ascii=False)),
    )


def _validate_entry(entry_type: str, category: str, amount: Decimal, summary: str) -> None:
    _validate_category(entry_type, category)
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be finite and positive.")
    if not summary.strip():
        raise ValueError("Summary cannot be empty.")


def _validate_category(entry_type: str, category: str) -> None:
    if entry_type not in {"income", "expense"} or category not in _CATEGORIES:
        raise ValueError("Unsupported entry type or category.")
    if entry_type == "income" and category in {"essential", "discretionary"}:
        raise ValueError("Income cannot be essential or discretionary spending.")
    if entry_type == "expense" and category == "income":
        raise ValueError("Expense cannot be income.")


def _reference(reference: str) -> tuple[str, int]:
    try:
        kind, raw_id = reference.split(":", 1)
        entry_id = int(raw_id)
    except ValueError as exc:
        raise ValueError("Entry reference must look like pdf:123 or manual:123.") from exc
    if kind not in {"pdf", "manual"} or entry_id <= 0:
        raise ValueError("Entry reference must look like pdf:123 or manual:123.")
    return kind, entry_id


def _month(value: str) -> None:
    try:
        date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM format.") from exc
    if len(value) != 7:
        raise ValueError("Month must use YYYY-MM format.")


def _currency(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("Currency must be a three-letter code.")
    return normalized


def _actor(value: str) -> None:
    if not value.strip():
        raise ValueError("Actor is required for audited changes.")


def _decimal_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None
