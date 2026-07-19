import json
import sqlite3
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from app.steward.models import (
    CashTransaction,
    Holding,
    StoredCashTransaction,
    StoredHolding,
)
from app.steward.reconciliation import AccountProfile, TransferDecision


_SCHEMA = """
CREATE TABLE IF NOT EXISTS steward_source_documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL,
  source_hash TEXT NOT NULL UNIQUE,
  institution TEXT NOT NULL,
  source_type TEXT NOT NULL,
  status TEXT NOT NULL,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS steward_cash_transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_hash TEXT NOT NULL,
  institution TEXT NOT NULL,
  account_label TEXT NOT NULL,
  transaction_date TEXT NOT NULL,
  transaction_time TEXT,
  currency TEXT NOT NULL,
  amount TEXT NOT NULL,
  balance TEXT,
  summary TEXT NOT NULL,
  channel TEXT,
  raw_text TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_hash, raw_text),
  FOREIGN KEY(source_hash) REFERENCES steward_source_documents(source_hash)
);

CREATE TABLE IF NOT EXISTS steward_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_date TEXT NOT NULL,
  title TEXT NOT NULL,
  content_markdown TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS steward_accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institution TEXT NOT NULL,
  account_label TEXT NOT NULL,
  currency TEXT NOT NULL,
  ownership TEXT NOT NULL,
  role TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(institution, account_label, currency)
);

CREATE TABLE IF NOT EXISTS steward_transfer_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  outgoing_transaction_id INTEGER NOT NULL,
  incoming_transaction_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(outgoing_transaction_id, incoming_transaction_id)
);

CREATE TABLE IF NOT EXISTS steward_holdings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  institution TEXT NOT NULL,
  account_label TEXT NOT NULL,
  symbol TEXT NOT NULL,
  name TEXT NOT NULL,
  quantity TEXT NOT NULL,
  currency TEXT NOT NULL,
  unit_cost TEXT NOT NULL,
  acquired_on TEXT NOT NULL,
  fx_transaction_id INTEGER,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(institution, account_label, symbol, acquired_on),
  FOREIGN KEY(fx_transaction_id) REFERENCES steward_cash_transactions(id)
);
"""


def initialize_steward_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)


class StewardRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def record_source_document(
        self,
        path: str,
        source_hash: str,
        institution: str,
        source_type: str,
        status: str,
        warnings: list[str],
    ) -> int:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO steward_source_documents
                  (path, source_hash, institution, source_type, status, warnings_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    path,
                    source_hash,
                    institution,
                    source_type,
                    status,
                    json.dumps(warnings, ensure_ascii=False),
                ),
            )
            row = conn.execute(
                "SELECT id FROM steward_source_documents WHERE source_hash = ?",
                (source_hash,),
            ).fetchone()
        return int(row["id"])

    def upsert_cash_transactions(
        self,
        source_hash: str,
        transactions: list[CashTransaction],
    ) -> int:
        inserted = 0
        with _connect(self.db_path) as conn:
            for txn in transactions:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO steward_cash_transactions
                      (
                        source_hash, institution, account_label, transaction_date,
                        transaction_time, currency, amount, balance, summary,
                        channel, raw_text
                      )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_hash,
                        txn.institution,
                        txn.account_label,
                        txn.transaction_date.isoformat(),
                        txn.transaction_time.isoformat()
                        if txn.transaction_time is not None
                        else None,
                        txn.currency,
                        str(txn.amount),
                        str(txn.balance) if txn.balance is not None else None,
                        txn.summary,
                        txn.channel,
                        txn.raw_text,
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def list_cash_transactions(self) -> list[StoredCashTransaction]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM steward_cash_transactions
                ORDER BY transaction_date, transaction_time, id
                """
            ).fetchall()
        return [_row_to_transaction(row) for row in rows]

    def count_source_documents(self) -> int:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM steward_source_documents"
            ).fetchone()
        return int(row["count"])

    def upsert_account_profile(self, account: AccountProfile) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO steward_accounts
                  (institution, account_label, currency, ownership, role)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(institution, account_label, currency) DO UPDATE SET
                  ownership = excluded.ownership,
                  role = excluded.role,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    account.institution,
                    account.account_label,
                    account.currency,
                    account.ownership,
                    account.role,
                ),
            )

    def list_account_profiles(self) -> list[AccountProfile]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT institution, account_label, currency, ownership, role
                FROM steward_accounts
                ORDER BY institution, account_label, currency
                """
            ).fetchall()
        return [
            AccountProfile(
                institution=row["institution"],
                account_label=row["account_label"],
                currency=row["currency"],
                ownership=row["ownership"],
                role=row["role"],
            )
            for row in rows
        ]

    def upsert_transfer_decision(self, decision: TransferDecision) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO steward_transfer_decisions
                  (outgoing_transaction_id, incoming_transaction_id, status)
                VALUES (?, ?, ?)
                ON CONFLICT(outgoing_transaction_id, incoming_transaction_id)
                DO UPDATE SET
                  status = excluded.status,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    decision.outgoing_transaction_id,
                    decision.incoming_transaction_id,
                    decision.status,
                ),
            )

    def list_transfer_decisions(self) -> list[TransferDecision]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT outgoing_transaction_id, incoming_transaction_id, status
                FROM steward_transfer_decisions
                ORDER BY outgoing_transaction_id, incoming_transaction_id
                """
            ).fetchall()
        return [
            TransferDecision(
                outgoing_transaction_id=row["outgoing_transaction_id"],
                incoming_transaction_id=row["incoming_transaction_id"],
                status=row["status"],
            )
            for row in rows
        ]

    def upsert_holding(self, holding: Holding) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO steward_holdings
                  (
                    institution, account_label, symbol, name, quantity,
                    currency, unit_cost, acquired_on, fx_transaction_id
                  )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(institution, account_label, symbol, acquired_on)
                DO UPDATE SET
                  name = excluded.name,
                  quantity = excluded.quantity,
                  currency = excluded.currency,
                  unit_cost = excluded.unit_cost,
                  fx_transaction_id = excluded.fx_transaction_id,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    holding.institution,
                    holding.account_label,
                    holding.symbol,
                    holding.name,
                    str(holding.quantity),
                    holding.currency,
                    str(holding.unit_cost),
                    holding.acquired_on.isoformat(),
                    holding.fx_transaction_id,
                ),
            )

    def list_holdings(self) -> list[StoredHolding]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM steward_holdings
                ORDER BY institution, account_label, symbol, acquired_on, id
                """
            ).fetchall()
        return [_row_to_holding(row) for row in rows]

    def insert_report(self, report_date: date, title: str, content: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO steward_reports (report_date, title, content_markdown)
                VALUES (?, ?, ?)
                """,
                (report_date.isoformat(), title, content),
            )


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_transaction(row: sqlite3.Row) -> StoredCashTransaction:
    return StoredCashTransaction(
        id=row["id"],
        source_hash=row["source_hash"],
        institution=row["institution"],
        account_label=row["account_label"],
        transaction_date=date.fromisoformat(row["transaction_date"]),
        transaction_time=time.fromisoformat(row["transaction_time"])
        if row["transaction_time"]
        else None,
        currency=row["currency"],
        amount=Decimal(row["amount"]),
        balance=Decimal(row["balance"]) if row["balance"] is not None else None,
        summary=row["summary"],
        channel=row["channel"],
        raw_text=row["raw_text"],
    )


def _row_to_holding(row: sqlite3.Row) -> StoredHolding:
    return StoredHolding(
        id=row["id"],
        institution=row["institution"],
        account_label=row["account_label"],
        symbol=row["symbol"],
        name=row["name"],
        quantity=Decimal(row["quantity"]),
        currency=row["currency"],
        unit_cost=Decimal(row["unit_cost"]),
        acquired_on=date.fromisoformat(row["acquired_on"]),
        fx_transaction_id=row["fx_transaction_id"],
    )
