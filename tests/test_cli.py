from datetime import date

import app.main
from app.collectors.yfinance_price_collector import YFinanceCollectionResult
from app.main import build_parser
from app.models.price import PriceBar
from app.storage.repositories.price_repo import PriceRepository


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
    assert parser.parse_args(["report", "daily"]).report_command == "daily"


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

    def collect(symbols):
        received_symbols.extend(symbols)
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

    def collect(symbols):
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
