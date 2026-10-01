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

CREATE TABLE IF NOT EXISTS income_expense_manual_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_date TEXT NOT NULL,
  currency TEXT NOT NULL,
  entry_type TEXT NOT NULL CHECK(entry_type IN ('income', 'expense')),
  category TEXT NOT NULL,
  amount TEXT NOT NULL,
  summary TEXT NOT NULL,
  account_label TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS income_expense_adjustments (
  entry_kind TEXT NOT NULL CHECK(entry_kind IN ('pdf', 'manual')),
  entry_id INTEGER NOT NULL,
  transaction_date TEXT,
  amount TEXT,
  category TEXT NOT NULL,
  summary TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(entry_kind, entry_id)
);

CREATE TABLE IF NOT EXISTS income_expense_budgets (
  month TEXT NOT NULL,
  currency TEXT NOT NULL,
  expected_income TEXT,
  essential_budget TEXT,
  investment_target TEXT,
  safety_buffer TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(month, currency)
);

CREATE TABLE IF NOT EXISTS income_expense_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  actor TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


_EFFECTIVE_ENTRIES = """
SELECT 'pdf' AS entry_kind, e.id AS entry_id,
       COALESCE(a.transaction_date, e.transaction_date) AS transaction_date,
       e.currency, e.entry_type, COALESCE(a.category, e.category) AS category,
       COALESCE(a.amount, e.amount) AS amount,
       COALESCE(a.summary, e.summary) AS summary
FROM income_expense_entries e
LEFT JOIN income_expense_adjustments a
  ON a.entry_kind = 'pdf' AND a.entry_id = e.id
UNION ALL
SELECT 'manual', m.id, COALESCE(a.transaction_date, m.transaction_date),
       m.currency, m.entry_type,
       COALESCE(a.category, m.category), COALESCE(a.amount, m.amount),
       COALESCE(a.summary, m.summary)
FROM income_expense_manual_entries m
LEFT JOIN income_expense_adjustments a
  ON a.entry_kind = 'manual' AND a.entry_id = m.id
"""


def effective_entries_sql() -> str:
    return _EFFECTIVE_ENTRIES


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
                WHERE institution IS NOT excluded.institution
                   OR account_label IS NOT excluded.account_label
                   OR transaction_date IS NOT excluded.transaction_date
                   OR transaction_time IS NOT excluded.transaction_time
                   OR currency IS NOT excluded.currency
                   OR entry_type IS NOT excluded.entry_type
                   OR category IS NOT excluded.category
                   OR amount IS NOT excluded.amount
                   OR balance IS NOT excluded.balance
                   OR summary IS NOT excluded.summary
                   OR channel IS NOT excluded.channel
                   OR raw_text IS NOT excluded.raw_text
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
