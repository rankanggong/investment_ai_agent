from datetime import date
from pathlib import Path

from app.models.analysis import (
    EarningsEstimateObservation,
    ValuationObservation,
)
from app.storage.db import connect


class FundamentalRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def upsert_valuations(self, rows: list[ValuationObservation]) -> None:
        with connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO valuation_observations
                  (symbol, as_of_date, metric, value, currency, period, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, as_of_date, metric, source) DO UPDATE SET
                  value = excluded.value,
                  currency = excluded.currency,
                  period = excluded.period
                """,
                [
                    (
                        row.symbol, row.as_of_date.isoformat(), row.metric,
                        row.value, row.currency, row.period, row.source,
                    )
                    for row in rows
                ],
            )

    def upsert_earnings_estimates(
        self, rows: list[EarningsEstimateObservation]
    ) -> None:
        with connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO earnings_estimate_observations
                  (symbol, as_of_date, fiscal_period, metric, value, source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                  symbol, as_of_date, fiscal_period, metric, source
                ) DO UPDATE SET value = excluded.value
                """,
                [
                    (
                        row.symbol, row.as_of_date.isoformat(), row.fiscal_period,
                        row.metric, row.value, row.source,
                    )
                    for row in rows
                ],
            )

    def get_valuations(self) -> list[ValuationObservation]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT symbol, as_of_date, metric, value, currency, period, source
                FROM valuation_observations
                ORDER BY symbol, metric, as_of_date
                """
            ).fetchall()
        return [
            ValuationObservation(
                row["symbol"], date.fromisoformat(row["as_of_date"]),
                row["metric"], float(row["value"]), row["source"],
                row["currency"], row["period"],
            )
            for row in rows
        ]

    def get_earnings_estimates(self) -> list[EarningsEstimateObservation]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT symbol, as_of_date, fiscal_period, metric, value, source
                FROM earnings_estimate_observations
                ORDER BY symbol, fiscal_period, metric, as_of_date
                """
            ).fetchall()
        return [
            EarningsEstimateObservation(
                row["symbol"], date.fromisoformat(row["as_of_date"]),
                row["fiscal_period"], row["metric"], float(row["value"]),
                row["source"],
            )
            for row in rows
        ]
