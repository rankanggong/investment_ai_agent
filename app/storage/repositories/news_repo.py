from datetime import datetime
from pathlib import Path

from app.models.analysis import NewsItem
from app.storage.db import connect


class NewsRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def upsert_many(self, items: list[NewsItem]) -> None:
        with connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO news_items (
                  title, url, publisher, published_at, related_symbol, source
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                  title = excluded.title,
                  publisher = excluded.publisher,
                  published_at = excluded.published_at,
                  related_symbol = excluded.related_symbol,
                  source = excluded.source
                """,
                [
                    (
                        item.title,
                        item.url,
                        item.publisher,
                        item.published_at.isoformat() if item.published_at else None,
                        item.related_symbol,
                        item.source,
                    )
                    for item in items
                ],
            )

    def get_recent_items(self, limit: int = 100) -> list[NewsItem]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT title, url, publisher, published_at, related_symbol, source
                FROM news_items
                ORDER BY COALESCE(published_at, created_at) DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            NewsItem(
                title=row["title"],
                url=row["url"],
                publisher=row["publisher"],
                published_at=(
                    datetime.fromisoformat(row["published_at"])
                    if row["published_at"]
                    else None
                ),
                related_symbol=row["related_symbol"],
                source=row["source"],
            )
            for row in rows
        ]
