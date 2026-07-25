from datetime import date

from app.models.price import PriceBar
from app.storage.db import initialize_database
from app.storage.repositories.price_repo import PriceRepository
from app.storage.repositories.report_repo import ReportRepository


def test_price_repository_upserts_and_reads_prices(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = PriceRepository(db_path)

    repo.upsert_many(
        [
            PriceBar(
                symbol="SPY",
                date=date(2026, 5, 14),
                open=100,
                high=102,
                low=99,
                close=101,
                adjusted_close=101,
                volume=1000,
                source="test",
            ),
            PriceBar(
                symbol="SPY",
                date=date(2026, 5, 15),
                open=101,
                high=104,
                low=100,
                close=103,
                adjusted_close=103,
                volume=1500,
                source="test",
            ),
        ]
    )
    repo.upsert_many(
        [
            PriceBar(
                symbol="SPY",
                date=date(2026, 5, 15),
                open=101,
                high=104,
                low=100,
                close=104,
                adjusted_close=104,
                volume=1700,
                source="test",
            )
        ]
    )

    bars = repo.get_prices("SPY")

    assert len(bars) == 2
    assert bars[-1].close == 104
    assert bars[-1].volume == 1700
    assert repo.get_history_coverage("SPY") == (
        2,
        date(2026, 5, 14),
        date(2026, 5, 15),
    )


def test_report_repository_reads_latest_report_before_current_date(tmp_path):
    db_path = tmp_path / "finance.db"
    initialize_database(db_path)
    repo = ReportRepository(db_path)
    repo.insert_report("daily", date(2026, 7, 23), "Older", "older state")
    repo.insert_report("daily", date(2026, 7, 25), "Current", "current state")

    assert repo.get_previous_content("daily", date(2026, 7, 25)) == "older state"
