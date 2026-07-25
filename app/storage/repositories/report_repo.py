from datetime import date
from pathlib import Path

from app.storage.db import connect


class ReportRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def insert_report(self, report_type: str, report_date: date, title: str, content: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reports (report_type, report_date, title, content_markdown)
                VALUES (?, ?, ?, ?)
                """,
                (report_type, report_date.isoformat(), title, content),
            )

    def get_latest_content(self, report_type: str) -> str | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT content_markdown
                FROM reports
                WHERE report_type = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (report_type,),
            ).fetchone()
        return None if row is None else str(row["content_markdown"])

    def get_previous_content(
        self,
        report_type: str,
        before_date: date,
    ) -> str | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT content_markdown
                FROM reports
                WHERE report_type = ? AND report_date < ?
                ORDER BY report_date DESC, id DESC
                LIMIT 1
                """,
                (report_type, before_date.isoformat()),
            ).fetchone()
        return None if row is None else str(row["content_markdown"])
