import sqlite3
from pathlib import Path

from app.steward.income_expense.models import IncomeExpenseEntry


_SCHEMA = """
CREATE TABLE IF NOT EXISTS income_expense_sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  source_hash TEXT NOT NULL UNIQUE,
  institution TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS income_expense_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_hash TEXT NOT NULL,
  source_row_index INTEGER NOT NULL,
  institution TEXT NOT NULL,
  account_label TEXT NOT NULL,
  transaction_date TEXT NOT NULL,
  transaction_time TEXT,
  currency TEXT NOT NULL,
  entry_type TEXT NOT NULL CHECK(entry_type IN ('income', 'expense')),
  category TEXT NOT NULL CHECK(
    category IN ('income', 'essential', 'discretionary', 'investment')
  ),
  amount TEXT NOT NULL,
  balance TEXT,
  summary TEXT NOT NULL,
  channel TEXT,
  raw_text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_hash, source_row_index),
  FOREIGN KEY(source_hash) REFERENCES income_expense_sources(source_hash)
);
"""


def initialize_income_expense_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(_SCHEMA)
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(income_expense_entries)"
            ).fetchall()
        }
        if "category" not in columns:
            conn.execute(
                "ALTER TABLE income_expense_entries "
                "ADD COLUMN category TEXT NOT NULL DEFAULT 'discretionary'"
            )
        if "source_row_index" not in columns:
            _migrate_entry_identity(conn)


def store_entries(
    db_path: Path,
    source_path: Path,
    source_hash: str,
    institution: str,
    entries: list[IncomeExpenseEntry],
) -> int:
    initialize_income_expense_database(db_path)
    inserted = 0
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT OR IGNORE INTO income_expense_sources
              (path, source_hash, institution)
            VALUES (?, ?, ?)
            """,
            (str(source_path), source_hash, institution),
        )
        for source_row_index, entry in enumerate(entries):
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO income_expense_entries
                  (source_hash, source_row_index, institution, account_label, transaction_date,
                   transaction_time, currency, entry_type, category, amount, balance,
                   summary, channel, raw_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_hash, source_row_index) DO UPDATE SET
                  institution = excluded.institution,
                  account_label = excluded.account_label,
                  transaction_date = excluded.transaction_date,
                  transaction_time = excluded.transaction_time,
                  currency = excluded.currency,
                  entry_type = excluded.entry_type,
                  category = excluded.category,
                  amount = excluded.amount,
                  balance = excluded.balance,
                  summary = excluded.summary,
                  channel = excluded.channel,
                  raw_text = excluded.raw_text
                """,
                (
                    source_hash,
                    source_row_index,
                    entry.institution,
                    entry.account_label,
                    entry.transaction_date.isoformat(),
                    entry.transaction_time.isoformat()
                    if entry.transaction_time is not None
                    else None,
                    entry.currency,
                    entry.entry_type,
                    entry.category,
                    str(entry.amount),
                    str(entry.balance) if entry.balance is not None else None,
                    entry.summary,
                    entry.channel,
                    entry.raw_text,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def _migrate_entry_identity(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT * FROM income_expense_entries ORDER BY source_hash, id"
    ).fetchall()
    column_names = [
        row[1] for row in conn.execute("PRAGMA table_info(income_expense_entries)")
    ]
    records = [dict(zip(column_names, row)) for row in rows]
    conn.execute("ALTER TABLE income_expense_entries RENAME TO old_income_expense_entries")
    conn.executescript(_SCHEMA)
    indexes: dict[str, int] = {}
    for record in records:
        source_hash = record["source_hash"]
        source_row_index = indexes.get(source_hash, 0)
        indexes[source_hash] = source_row_index + 1
        conn.execute(
            """
            INSERT INTO income_expense_entries
              (id, source_hash, source_row_index, institution, account_label,
               transaction_date, transaction_time, currency, entry_type, category,
               amount, balance, summary, channel, raw_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"], source_hash, source_row_index, record["institution"],
                record["account_label"], record["transaction_date"],
                record["transaction_time"], record["currency"],
                record["entry_type"], record["category"], record["amount"],
                record["balance"], record["summary"], record["channel"],
                record["raw_text"], record["created_at"],
            ),
        )
    conn.execute("DROP TABLE old_income_expense_entries")
