from datetime import date
from pathlib import Path

from app.models.price import PriceBar
from app.storage.db import connect


class PriceRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def upsert_many(self, bars: list[PriceBar]) -> None:
        with connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO prices (
                  symbol, date, open, high, low, close, adjusted_close, volume, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, date, source) DO UPDATE SET
                  open = excluded.open,
                  high = excluded.high,
                  low = excluded.low,
                  close = excluded.close,
                  adjusted_close = excluded.adjusted_close,
                  volume = excluded.volume
                """,
                [
                    (
                        bar.symbol,
                        bar.date.isoformat(),
                        bar.open,
                        bar.high,
                        bar.low,
                        bar.close,
                        bar.adjusted_close,
                        bar.volume,
                        bar.source,
                    )
                    for bar in bars
                ],
            )

    def get_prices(self, symbol: str) -> list[PriceBar]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT symbol, date, open, high, low, close, adjusted_close, volume, source
                FROM prices
                WHERE symbol = ?
                ORDER BY date ASC
                """,
                (symbol.upper(),),
            ).fetchall()

        return [
            PriceBar(
                symbol=row["symbol"],
                date=date.fromisoformat(row["date"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                adjusted_close=row["adjusted_close"],
                volume=row["volume"],
                source=row["source"],
            )
            for row in rows
        ]

