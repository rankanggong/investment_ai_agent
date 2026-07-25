from datetime import date
from decimal import Decimal

from app.jobs.daily_market_job import generate_daily_report
from app.steward.models import CashPosition, FxConversion, HoldingPosition, StewardState
from app.steward.storage import StewardRepository, initialize_steward_database
from app.storage.db import initialize_database


def test_daily_market_report_loads_portfolio_summary_and_account_detail(tmp_path):
    finance_db = tmp_path / "finance.db"
    steward_db = tmp_path / "steward.db"
    report_dir = tmp_path / "reports"
    watchlist = tmp_path / "watchlist.yaml"
    watchlist.write_text("assets:\n  core:\n    - SPY\n", encoding="utf-8")
    initialize_database(finance_db)
    initialize_steward_database(steward_db)
    StewardRepository(steward_db).replace_state(
        StewardState(
            cash_positions=[
                CashPosition(
                    institution="bank",
                    account_label="cash",
                    currency="USD",
                    balance=Decimal("9000"),
                    as_of_date=date(2026, 7, 19),
                )
            ],
            holdings=[
                HoldingPosition(
                    institution="broker",
                    account_label="fund",
                    symbol="VOO",
                    name="Vanguard S&P 500 ETF",
                    quantity=Decimal("10.74"),
                    currency="CNY",
                    unit_cost=Decimal("2.7933"),
                    as_of_date=date(2026, 7, 19),
                )
            ],
            fx_conversions=[
                FxConversion(
                    institution="bank",
                    account_label="usd",
                    fx_date=date(2026, 7, 15),
                    sold_currency="CNY",
                    sold_amount=Decimal("13587.60"),
                    bought_currency="USD",
                    bought_amount=Decimal("2000"),
                )
            ],
        )
    )

    path = generate_daily_report(
        db_path=finance_db,
        watchlist_path=watchlist,
        report_dir=report_dir,
        report_date=date(2026, 7, 21),
        steward_db_path=steward_db,
    )

    content = path.read_text(encoding="utf-8")
    assert "## 2. Portfolio Summary" in content
    assert "| VOO | CNY 30.00 | 100.00% | N/A | N/A | N/A |" in content
    assert "### B. Account Detail" in content
    assert "| broker | fund | VOO | Vanguard S&P 500 ETF |" in content
    assert "#### FX Conversions" in content
    assert "| 2026-07-15 | bank / usd | CNY 13587.60 | USD 2000.00 |" in content
    assert "| bank | cash | USD | 9000 | 2026-07-19 |" in content
