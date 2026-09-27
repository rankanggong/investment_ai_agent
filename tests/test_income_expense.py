import csv
import sqlite3
from datetime import date
from decimal import Decimal

from app.steward.income_expense import job
from app.steward.models import CashTransaction, ParseResult


def _parsed_statement() -> ParseResult:
    return ParseResult(
        institution="cmb",
        source_type="pdf_text",
        transactions=[
            CashTransaction(
                institution="cmb",
                account_label="masked-account",
                transaction_date=date(2026, 8, 1),
                currency="CNY",
                amount=Decimal("8000.00"),
                balance=Decimal("10000.00"),
                summary="工资",
                raw_text="income row",
            ),
            CashTransaction(
                institution="cmb",
                account_label="masked-account",
                transaction_date=date(2026, 8, 2),
                currency="CNY",
                amount=Decimal("-25.50"),
                balance=Decimal("9974.50"),
                summary="餐饮",
                raw_text="expense row",
            ),
        ],
    )


def test_import_statement_writes_income_and_expense_csv(tmp_path, monkeypatch):
    pdf_path = tmp_path / "statement.pdf"
    pdf_path.write_bytes(b"synthetic pdf")
    csv_path = tmp_path / "income-expense.csv"
    monkeypatch.setattr(job, "parse_statement_file", lambda path: _parsed_statement())

    summary = job.import_income_expense_statement(pdf_path, csv_path=csv_path)

    assert summary.parsed_entries == 2
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["entry_type"] == "income"
    assert rows[0]["category"] == "income"
    assert rows[0]["amount"] == "8000.00"
    assert rows[1]["entry_type"] == "expense"
    assert rows[1]["category"] == "essential"
    assert rows[1]["amount"] == "25.50"


def test_import_statement_writes_separate_idempotent_sqlite(tmp_path, monkeypatch):
    pdf_path = tmp_path / "statement.pdf"
    pdf_path.write_bytes(b"synthetic pdf")
    db_path = tmp_path / "income-expense.db"
    monkeypatch.setattr(job, "parse_statement_file", lambda path: _parsed_statement())

    first = job.import_income_expense_statement(pdf_path, db_path=db_path)
    second = job.import_income_expense_statement(pdf_path, db_path=db_path)

    assert first.written_entries == 2
    assert second.written_entries == 2
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT entry_type, category, amount "
            "FROM income_expense_entries ORDER BY id"
        ).fetchall()
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert rows == [
        ("income", "income", "8000.00"),
        ("expense", "essential", "25.50"),
    ]
    assert "steward_holdings" not in table_names


def test_import_preserves_identical_statement_rows(tmp_path, monkeypatch):
    parsed = _parsed_statement()
    duplicate = parsed.transactions[1]
    repeated = ParseResult(
        institution=parsed.institution,
        source_type=parsed.source_type,
        transactions=[duplicate, duplicate],
    )
    pdf_path = tmp_path / "statement.pdf"
    pdf_path.write_bytes(b"synthetic pdf")
    db_path = tmp_path / "income-expense.db"
    monkeypatch.setattr(job, "parse_statement_file", lambda path: repeated)

    job.import_income_expense_statement(pdf_path, db_path=db_path)
    job.import_income_expense_statement(pdf_path, db_path=db_path)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM income_expense_entries"
        ).fetchone()[0]
    assert count == 2


def test_monthly_summary_renders_requested_four_lines(tmp_path, monkeypatch):
    pdf_path = tmp_path / "statement.pdf"
    pdf_path.write_bytes(b"synthetic pdf")
    db_path = tmp_path / "income-expense.db"
    monkeypatch.setattr(job, "parse_statement_file", lambda path: _parsed_statement())
    job.import_income_expense_statement(pdf_path, db_path=db_path)

    summary = job.summarize_month(db_path, "2026-08")

    assert job.render_monthly_summary(summary) == (
        "本月收入          ¥8,000.00\n"
        "必要支出          ¥25.50\n"
        "自由消费          ¥0.00\n"
        "投资              ¥0.00"
    )


def test_allowance_uses_overrides_and_includes_as_of_day(tmp_path):
    summary = job.MonthlyIncomeExpenseSummary(
        month="2026-08",
        currency="CNY",
        income=Decimal("10000"),
        essential=Decimal("4000"),
        discretionary=Decimal("3000"),
        investment=Decimal("1000"),
    )

    allowance = job.calculate_monthly_allowance(
        tmp_path / "income-expense.db",
        summary,
        as_of=date(2026, 8, 22),
        expected_income=Decimal("30000"),
        essential_budget=Decimal("12000"),
        investment_target=Decimal("8000"),
        safety_buffer=Decimal("2000"),
    )

    assert allowance.remaining_monthly_allowance == Decimal("5000.00")
    assert allowance.remaining_days == 10
    assert allowance.remaining_daily_allowance == Decimal("500.00")


def test_allowance_uses_three_complete_month_average(tmp_path):
    db_path = tmp_path / "income-expense.db"
    job.initialize_income_expense_database(db_path)
    with sqlite3.connect(db_path) as conn:
        for index, (month, income, essential) in enumerate(
            (
                ("2026-05", "24000", "9000"),
                ("2026-06", "30000", "12000"),
                ("2026-07", "36000", "15000"),
            ),
            start=1,
        ):
            source_hash = f"source-{index}"
            conn.execute(
                "INSERT INTO income_expense_sources "
                "(path, source_hash, institution) VALUES (?, ?, 'cmb')",
                (f"{month}.pdf", source_hash),
            )
            for source_row_index, (category, amount) in enumerate(
                (("income", income), ("essential", essential))
            ):
                conn.execute(
                    """
                    INSERT INTO income_expense_entries
                      (source_hash, source_row_index, institution, account_label, transaction_date,
                       currency, entry_type, category, amount, summary, raw_text)
                    VALUES (?, ?, 'cmb', 'account', ?, 'CNY', ?, ?, ?, ?, ?)
                    """,
                    (
                        source_hash,
                        source_row_index,
                        f"{month}-01",
                        "income" if category == "income" else "expense",
                        category,
                        amount,
                        category,
                        f"{month}-{category}",
                    ),
                )
    current = job.MonthlyIncomeExpenseSummary(
        month="2026-08",
        currency="CNY",
        income=Decimal("5000"),
        essential=Decimal("1000"),
        discretionary=Decimal("2000"),
        investment=Decimal("0"),
    )

    allowance = job.calculate_monthly_allowance(
        db_path, current, as_of=date(2026, 8, 31)
    )

    assert allowance.history_months_used == 3
    assert allowance.expected_income == Decimal("30000.00")
    assert allowance.essential_budget == Decimal("12000.00")
    assert allowance.investment_target == Decimal("6000.00")
    assert allowance.safety_buffer == Decimal("3000.00")
    assert allowance.remaining_monthly_allowance == Decimal("7000.00")
    assert allowance.remaining_daily_allowance == Decimal("7000.00")


def test_investment_redemption_is_not_counted_as_income(tmp_path, monkeypatch):
    parsed = _parsed_statement()
    redemption = CashTransaction(
        institution="cmb",
        account_label="masked-account",
        transaction_date=date(2026, 8, 3),
        currency="CNY",
        amount=Decimal("5000.00"),
        balance=Decimal("14974.50"),
        summary="朝朝宝转出",
        raw_text="redemption row",
    )
    result = ParseResult(
        institution="cmb",
        source_type="pdf_text",
        transactions=[*parsed.transactions, redemption],
    )
    pdf_path = tmp_path / "statement.pdf"
    pdf_path.write_bytes(b"synthetic pdf")
    db_path = tmp_path / "income-expense.db"
    monkeypatch.setattr(job, "parse_statement_file", lambda path: result)

    job.import_income_expense_statement(pdf_path, db_path=db_path)
    summary = job.summarize_month(db_path, "2026-08")

    assert summary.income == Decimal("8000.00")
    assert summary.investment == Decimal("0")
