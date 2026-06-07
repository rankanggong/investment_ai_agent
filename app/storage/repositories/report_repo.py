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

