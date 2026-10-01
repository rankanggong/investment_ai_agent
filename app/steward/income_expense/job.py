import csv
import calendar
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from app.steward.income_expense.models import IncomeExpenseEntry
from app.steward.income_expense.storage import (
    effective_entries_sql,
    initialize_income_expense_database,
    store_entries,
)
from app.steward.parsers.registry import parse_statement_file


@dataclass(frozen=True)
class IncomeExpenseImportSummary:
    parsed_entries: int
    written_entries: int
    institution: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MonthlyIncomeExpenseSummary:
    month: str
    currency: str
    income: Decimal
    essential: Decimal
    discretionary: Decimal
    investment: Decimal


@dataclass(frozen=True)
class MonthlyAllowance:
    expected_income: Decimal
    essential_budget: Decimal
    investment_target: Decimal
    safety_buffer: Decimal
    remaining_monthly_allowance: Decimal
    remaining_daily_allowance: Decimal
    remaining_days: int
    history_months_used: int


_ESSENTIAL_KEYWORDS = (
    "房租", "物业", "水费", "电费", "燃气", "话费", "宽带", "交通",
    "公交", "地铁", "打车", "医疗", "医院", "药", "保险", "贷款本息",
    "还款", "餐饮", "超市", "生活缴费",
)
_INVESTMENT_KEYWORDS = (
    "投资", "理财", "基金", "证券", "股票", "券商", "朝朝宝", "余额宝",
    "赎回", "黄金账户",
)


def import_income_expense_statement(
    pdf_path: Path,
    *,
    csv_path: Path | None = None,
    db_path: Path | None = None,
) -> IncomeExpenseImportSummary:
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError("Income/expense import currently accepts a PDF statement.")
    if not pdf_path.is_file():
        raise ValueError(f"Statement PDF does not exist: {pdf_path}")
    if csv_path is None and db_path is None:
        raise ValueError("Choose at least one output with --csv or --db.")

    parsed = parse_statement_file(pdf_path)
    if parsed.institution == "unknown":
        warning = parsed.warnings[0] if parsed.warnings else "Unsupported statement."
        raise ValueError(warning)

    entries = [_to_entry(transaction) for transaction in parsed.transactions]
    if not entries:
        warning = parsed.warnings[0] if parsed.warnings else "No transactions parsed."
        raise ValueError(warning)

    written_entries = 0
    if csv_path is not None:
        _write_csv(csv_path, entries)
        written_entries = len(entries)
    if db_path is not None:
        written_entries = store_entries(
            db_path,
            pdf_path,
            _hash_file(pdf_path),
            parsed.institution,
            entries,
        )

    return IncomeExpenseImportSummary(
        parsed_entries=len(entries),
        written_entries=written_entries,
        institution=parsed.institution,
        warnings=parsed.warnings,
    )


def _to_entry(transaction) -> IncomeExpenseEntry:
    entry_type = "income" if transaction.amount >= 0 else "expense"
    return IncomeExpenseEntry(
        institution=transaction.institution,
        account_label=transaction.account_label,
        transaction_date=transaction.transaction_date,
        transaction_time=transaction.transaction_time,
        currency=transaction.currency,
        entry_type=entry_type,
        category=_categorize(entry_type, transaction.summary),
        amount=abs(transaction.amount),
        balance=transaction.balance,
        summary=transaction.summary,
        channel=transaction.channel,
        raw_text=transaction.raw_text,
    )


def _write_csv(path: Path, entries: list[IncomeExpenseEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "institution",
                "account_label",
                "transaction_date",
                "transaction_time",
                "currency",
                "entry_type",
                "category",
                "amount",
                "balance",
                "summary",
                "channel",
            ]
        )
        for entry in entries:
            writer.writerow(
                [
                    entry.institution,
                    entry.account_label,
                    entry.transaction_date.isoformat(),
                    entry.transaction_time.isoformat()
                    if entry.transaction_time is not None
                    else "",
                    entry.currency,
                    entry.entry_type,
                    entry.category,
                    str(entry.amount),
                    str(entry.balance) if entry.balance is not None else "",
                    entry.summary,
                    entry.channel or "",
                ]
            )


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _categorize(entry_type: str, summary: str) -> str:
    normalized = summary.lower()
    if any(keyword.lower() in normalized for keyword in _INVESTMENT_KEYWORDS):
        return "investment"
    if entry_type == "income":
        return "income"
    if any(keyword.lower() in normalized for keyword in _ESSENTIAL_KEYWORDS):
        return "essential"
    return "discretionary"


def summarize_month(
    db_path: Path,
    month: str,
    *,
    currency: str = "CNY",
) -> MonthlyIncomeExpenseSummary:
    _parse_month(month)
    initialize_income_expense_database(db_path)
    totals = {
        "income": Decimal("0"),
        "essential": Decimal("0"),
        "discretionary": Decimal("0"),
        "investment": Decimal("0"),
    }
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT category, entry_type, amount
            FROM ({effective_entries_sql()})
            WHERE substr(transaction_date, 1, 7) = ? AND currency = ?
            """,
            (month, currency.upper()),
        ).fetchall()
    for category, entry_type, amount in rows:
        if category == "excluded":
            continue
        if category == "investment" and entry_type == "income":
            continue
        totals[category] += Decimal(amount)
    return MonthlyIncomeExpenseSummary(
        month=month,
        currency=currency.upper(),
        income=totals["income"],
        essential=totals["essential"],
        discretionary=totals["discretionary"],
        investment=totals["investment"],
    )


def calculate_monthly_allowance(
    db_path: Path,
    summary: MonthlyIncomeExpenseSummary,
    *,
    as_of: date | None = None,
    expected_income: Decimal | None = None,
    essential_budget: Decimal | None = None,
    investment_target: Decimal | None = None,
    safety_buffer: Decimal | None = None,
    investment_rate: Decimal = Decimal("0.20"),
    buffer_rate: Decimal = Decimal("0.10"),
) -> MonthlyAllowance:
    from app.steward.income_expense.operations import get_budget

    budget = get_budget(db_path, summary.month, summary.currency)
    if budget is not None:
        expected_income = (
            expected_income if expected_income is not None else budget.expected_income
        )
        essential_budget = (
            essential_budget if essential_budget is not None else budget.essential_budget
        )
        investment_target = (
            investment_target if investment_target is not None else budget.investment_target
        )
        safety_buffer = (
            safety_buffer if safety_buffer is not None else budget.safety_buffer
        )
    year, month_number = _parse_month(summary.month)
    effective_date = as_of or date.today()
    if (effective_date.year, effective_date.month) != (year, month_number):
        raise ValueError("Allowance as-of date must be inside the summary month.")
    for name, value in (
        ("investment rate", investment_rate),
        ("buffer rate", buffer_rate),
    ):
        if value < 0 or value > 1:
            raise ValueError(f"{name} must be between 0 and 1.")
    for name, value in (
        ("expected income", expected_income),
        ("essential budget", essential_budget),
        ("investment target", investment_target),
        ("safety buffer", safety_buffer),
    ):
        if value is not None and value < 0:
            raise ValueError(f"{name} cannot be negative.")

    historical_income, historical_essential, history_months = _history_averages(
        db_path,
        summary.month,
        summary.currency,
    )
    projected_income = expected_income
    if projected_income is None:
        projected_income = historical_income if history_months else summary.income
    projected_income = max(projected_income, summary.income)

    projected_essential = essential_budget
    if projected_essential is None:
        projected_essential = (
            historical_essential if history_months else summary.essential
        )
    projected_essential = max(projected_essential, summary.essential)

    target_investment = investment_target
    if target_investment is None:
        target_investment = projected_income * investment_rate
    reserved_investment = max(target_investment, summary.investment)
    reserved_buffer = (
        safety_buffer
        if safety_buffer is not None
        else projected_income * buffer_rate
    )
    if min(
        projected_income,
        projected_essential,
        target_investment,
        reserved_buffer,
    ) < 0:
        raise ValueError("Allowance inputs cannot be negative.")

    remaining = max(
        Decimal("0"),
        projected_income
        - projected_essential
        - reserved_investment
        - reserved_buffer
        - summary.discretionary,
    )
    last_day = calendar.monthrange(year, month_number)[1]
    remaining_days = last_day - effective_date.day + 1
    return MonthlyAllowance(
        expected_income=_money(projected_income),
        essential_budget=_money(projected_essential),
        investment_target=_money(target_investment),
        safety_buffer=_money(reserved_buffer),
        remaining_monthly_allowance=_money(remaining),
        remaining_daily_allowance=_money(remaining / remaining_days),
        remaining_days=remaining_days,
        history_months_used=history_months,
    )


def render_monthly_summary(
    summary: MonthlyIncomeExpenseSummary,
    allowance: MonthlyAllowance | None = None,
) -> str:
    symbol = "¥" if summary.currency == "CNY" else f"{summary.currency} "
    lines = [
        f"本月收入          {symbol}{summary.income:,.2f}",
        f"必要支出          {symbol}{summary.essential:,.2f}",
        f"自由消费          {symbol}{summary.discretionary:,.2f}",
        f"投资              {symbol}{summary.investment:,.2f}",
    ]
    if allowance is not None:
        lines.extend(
            (
                "",
                f"预计本月收入      {symbol}{allowance.expected_income:,.2f}",
                f"必要支出预算      {symbol}{allowance.essential_budget:,.2f}",
                f"投资目标          {symbol}{allowance.investment_target:,.2f}",
                f"安全缓冲          {symbol}{allowance.safety_buffer:,.2f}",
                f"本月剩余配额      {symbol}{allowance.remaining_monthly_allowance:,.2f}",
                f"单日合理配额      {symbol}{allowance.remaining_daily_allowance:,.2f}",
                f"剩余天数          {allowance.remaining_days}天",
            )
        )
    return "\n".join(lines)


def _history_averages(
    db_path: Path,
    before_month: str,
    currency: str,
) -> tuple[Decimal, Decimal, int]:
    initialize_income_expense_database(db_path)
    with sqlite3.connect(db_path) as conn:
        months = [
            row[0]
            for row in conn.execute(
                f"""
                SELECT DISTINCT substr(transaction_date, 1, 7) AS month
                FROM ({effective_entries_sql()})
                WHERE substr(transaction_date, 1, 7) < ? AND currency = ?
                ORDER BY month DESC
                LIMIT 3
                """,
                (before_month, currency),
            )
        ]
        if not months:
            return Decimal("0"), Decimal("0"), 0
        placeholders = ", ".join("?" for _ in months)
        rows = conn.execute(
            f"""
            SELECT category, entry_type, amount
            FROM ({effective_entries_sql()})
            WHERE substr(transaction_date, 1, 7) IN ({placeholders})
              AND currency = ?
            """,
            (*months, currency),
        ).fetchall()
    income = Decimal("0")
    essential = Decimal("0")
    for category, entry_type, amount in rows:
        if category == "income":
            income += Decimal(amount)
        elif category == "essential" and entry_type == "expense":
            essential += Decimal(amount)
    count = len(months)
    return income / count, essential / count, count


def _parse_month(month: str) -> tuple[int, int]:
    try:
        parsed = date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM format.") from exc
    if len(month) != 7:
        raise ValueError("Month must use YYYY-MM format.")
    return parsed.year, parsed.month


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
