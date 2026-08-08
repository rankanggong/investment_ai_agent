import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def initialize_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _migrate_decision_journal(conn)
        _migrate_fundamental_asset_types(conn)


def _migrate_decision_journal(conn: sqlite3.Connection) -> None:
    """Add P1 journal fields to databases created by older releases."""
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(decision_states)")
    }
    additions = {
        "execution_status": "TEXT NOT NULL DEFAULT 'blocked'",
        "permission_status": "TEXT NOT NULL DEFAULT 'unknown'",
        "proposed_amount": "REAL",
        "proposed_currency": "TEXT",
        "execution_reasons_json": "TEXT NOT NULL DEFAULT '[]'",
        "evidence_refs_json": "TEXT NOT NULL DEFAULT '[]'",
        "context_json": "TEXT NOT NULL DEFAULT '{}'",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(
                f"ALTER TABLE decision_states ADD COLUMN {name} {definition}"
            )


def _migrate_fundamental_asset_types(conn: sqlite3.Connection) -> None:
    for table in (
        "valuation_observations",
        "earnings_estimate_observations",
    ):
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "asset_type" not in columns:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN asset_type "
                "TEXT NOT NULL DEFAULT 'unknown'"
            )


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
