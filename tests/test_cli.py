from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import app.main
import pytest
from app.collectors.yfinance_price_collector import YFinanceCollectionResult
from app.collectors.google_news_collector import NewsCollectionResult
from app.main import build_parser
from app.models.price import PriceBar
from app.storage.repositories.price_repo import PriceRepository
from app.storage.repositories.fundamental_repo import FundamentalRepository
from app.storage.repositories.news_repo import NewsRepository
from app.models.analysis import NewsItem


def test_cli_exposes_phase_1_commands():
    parser = build_parser()

    assert parser.parse_args(["init-db"]).command == "init-db"
    assert (
        parser.parse_args(["collect", "prices", "--csv", "prices.csv"]).collect_command
        == "prices"
    )
    live_args = parser.parse_args(["collect", "prices", "--yfinance"])
    assert live_args.yfinance is True
    assert live_args.symbols is None
    assert live_args.period is None
    daily_args = parser.parse_args(["report", "daily"])
    assert daily_args.report_command == "daily"
    assert daily_args.steward_db == app.main.DEFAULT_STEWARD_DB_PATH
    assert daily_args.report_profile == app.main.DEFAULT_REPORT_PROFILE_PATH


def test_cli_exposes_phase_3_collection_commands():
    parser = build_parser()

    news = parser.parse_args(["collect", "news", "--google-rss"])
    fundamentals = parser.parse_args(
        ["collect", "fundamentals", "--csv", "fundamentals.csv"]
    )

    assert news.collect_command == "news"
    assert news.google_rss is True
    assert fundamentals.collect_command == "fundamentals"
    assert fundamentals.csv == Path("fundamentals.csv")


def test_fundamental_cli_imports_observations(tmp_path):
    db_path = tmp_path / "finance.db"
    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "record_type,symbol,as_of_date,metric,value,period,currency,source\n"
        "valuation,QQQ,2026-07-25,forward_pe,25,NTM,,provider_a\n",
        encoding="utf-8",
    )

    result = app.main.main(
        [
            "collect", "fundamentals", "--csv", str(csv_path),
            "--db", str(db_path),
        ]
    )

    assert result == 0
    assert FundamentalRepository(db_path).get_valuations()[0].value == 25


def test_news_cli_stores_candidates(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.db"

    def collect(symbols):
        assert list(symbols) == ["SPY"]
        return NewsCollectionResult(
            [
                NewsItem(
                    "SPY fee change",
                    "https://example.com/spy",
                    "Example",
                    datetime(2026, 7, 25, tzinfo=timezone.utc),
                    "SPY",
                    "test",
                )
            ],
            [],
        )

    monkeypatch.setattr(app.main, "collect_google_news", collect)

    result = app.main.main(
        [
            "collect", "news", "--google-rss", "--symbols", "SPY",
            "--db", str(db_path),
        ]
    )

    assert result == 0
    assert NewsRepository(db_path).get_recent_items()[0].related_symbol == "SPY"


def test_cli_exposes_steward_commands():
    parser = build_parser()

    init_args = parser.parse_args(["steward", "init-db"])
    assert init_args.command == "steward"
    assert init_args.steward_command == "init-db"
    import_args = parser.parse_args(
        ["steward", "import", "--csv", "steward-state.csv"]
    )
    assert import_args.steward_command == "import"
    assert import_args.csv == Path("steward-state.csv")
    report_args = parser.parse_args(["steward", "report"])
    assert report_args.steward_command == "report"

    with pytest.raises(SystemExit):
        parser.parse_args(["steward", "import", "--inbox", "statements"])
    with pytest.raises(SystemExit):
        parser.parse_args(["steward", "holding", "import", "--csv", "holdings.csv"])


def test_steward_cli_commands_delegate_to_job_functions(tmp_path, monkeypatch, capsys):
    calls = []

    def init_db(db_path):
        calls.append(("init", db_path))

    def import_state(db_path, csv_path):
        calls.append(("import", db_path, csv_path))

        class Summary:
            rows_seen = 8
            cash_positions = 3
            holdings = 4
            fx_conversions = 1

        return Summary()

    def report(db_path, report_dir):
        calls.append(("report", db_path, report_dir))
        return report_dir / "portfolio-steward-report-2026-07-15.md"

    monkeypatch.setattr(app.main, "initialize_steward_database", init_db)
    monkeypatch.setattr(app.main, "import_steward_state_csv", import_state)
    monkeypatch.setattr(app.main, "generate_steward_state_report", report)

    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "state.csv"
    report_dir = tmp_path / "reports"

    assert app.main.main(["steward", "init-db", "--db", str(db_path)]) == 0
    assert (
        app.main.main(
            [
                "steward",
                "import",
                "--db",
                str(db_path),
                "--csv",
                str(csv_path),
            ]
        )
        == 0
    )
    assert (
        app.main.main(
            [
                "steward",
                "report",
                "--db",
                str(db_path),
                "--report-dir",
                str(report_dir),
            ]
        )
        == 0
    )

    assert calls == [
        ("init", db_path),
        ("import", db_path, csv_path),
        ("report", db_path, report_dir),
    ]
    output = capsys.readouterr().out
    assert "Imported 8 state rows: 3 cash, 4 holdings, 1 FX conversions" in output
    assert "Wrote steward report" in output


def test_yfinance_collection_uses_watchlist_and_reports_failures(
    tmp_path, monkeypatch, capsys
):
    watchlist_path = tmp_path / "watchlist.yaml"
    watchlist_path.write_text(
        "assets:\n  core:\n    - SPY\n    - QQQ\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "finance.db"
    received_symbols = []

    received_periods = {}

    def collect(symbols, period, periods_by_symbol):
        received_symbols.extend(symbols)
        received_periods.update(periods_by_symbol)
        return YFinanceCollectionResult(
            bars=[
                PriceBar(
                    symbol="SPY",
                    date=date(2026, 6, 10),
                    open=100,
                    high=102,
                    low=99,
                    close=101,
                    adjusted_close=101,
                    volume=1000,
                    source="yfinance",
                )
            ],
            failed_symbols=["QQQ"],
            failure_reasons={"QQQ": "YFRateLimitError: Too Many Requests"},
        )

    monkeypatch.setattr(app.main, "collect_yfinance_prices", collect)

    result = app.main.main(
        [
            "collect",
            "prices",
            "--yfinance",
            "--watchlist",
            str(watchlist_path),
            "--db",
            str(db_path),
        ]
    )

    assert result == 0
    assert received_symbols == ["SPY", "QQQ"]
    assert received_periods == {"SPY": "1y", "QQQ": "1y"}
    assert len(PriceRepository(db_path).get_prices("SPY")) == 1
    output = capsys.readouterr().out
    assert "Failed symbols: QQQ" in output
    assert "QQQ: YFRateLimitError: Too Many Requests" in output
    assert (
        "Yahoo rejected this network route; this can happen without prior requests."
        in output
    )
    assert "Try another network later or import a CSV." in output


def test_yfinance_collection_uses_explicit_symbols(tmp_path, monkeypatch):
    received_symbols = []

    def collect(symbols, **kwargs):
        received_symbols.extend(symbols)
        return YFinanceCollectionResult(bars=[], failed_symbols=[], failure_reasons={})

    monkeypatch.setattr(app.main, "collect_yfinance_prices", collect)

    app.main.main(
        [
            "collect",
            "prices",
            "--yfinance",
            "--symbols",
            "spy",
            "qqq",
            "--db",
            str(tmp_path / "finance.db"),
        ]
    )

    assert received_symbols == ["SPY", "QQQ"]


def test_yfinance_collection_can_force_one_period(tmp_path, monkeypatch):
    received = {}

    def collect(symbols, period, periods_by_symbol):
        received.update(
            symbols=list(symbols),
            period=period,
            periods_by_symbol=periods_by_symbol,
        )
        return YFinanceCollectionResult(bars=[], failed_symbols=[], failure_reasons={})

    monkeypatch.setattr(app.main, "collect_yfinance_prices", collect)

    app.main.main(
        [
            "collect",
            "prices",
            "--yfinance",
            "--symbols",
            "SPY",
            "--period",
            "1y",
            "--db",
            str(tmp_path / "finance.db"),
        ]
    )

    assert received == {
        "symbols": ["SPY"],
        "period": "1y",
        "periods_by_symbol": None,
    }


def test_yfinance_collection_uses_short_window_for_complete_history(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "finance.db"
    app.main.initialize_database(db_path)
    as_of_date = date.today()
    PriceRepository(db_path).upsert_many(
        [
            PriceBar(
                symbol="SPY",
                date=as_of_date - timedelta(days=(199 - index) * 2),
                open=100,
                high=101,
                low=99,
                close=100,
                adjusted_close=100,
                volume=1000,
                source="test",
            )
            for index in range(200)
        ]
    )
    received_periods = {}

    def collect(symbols, period, periods_by_symbol):
        received_periods.update(periods_by_symbol)
        return YFinanceCollectionResult(bars=[], failed_symbols=[], failure_reasons={})

    monkeypatch.setattr(app.main, "collect_yfinance_prices", collect)

    app.main.main(
        [
            "collect",
            "prices",
            "--yfinance",
            "--symbols",
            "SPY",
            "--db",
            str(db_path),
        ]
    )

    assert received_periods == {"SPY": "5d"}
