from datetime import date
from pathlib import Path

import app.main
import pytest
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


def test_cli_does_not_expose_news_collection():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["collect", "news", "--google-rss"])


def test_cli_exposes_steward_commands():
    parser = build_parser()

    init_args = parser.parse_args(["steward", "init-db"])
    assert init_args.command == "steward"
    assert init_args.steward_command == "init-db"
    import_args = parser.parse_args(["steward", "import"])
    assert import_args.steward_command == "import"
    report_args = parser.parse_args(["steward", "report"])
    assert report_args.steward_command == "report"
    account_args = parser.parse_args(
        [
            "steward",
            "account",
            "set",
            "--institution",
            "cmb",
            "--account",
            "bank",
            "--currency",
            "CNY",
            "--ownership",
            "owned",
            "--role",
            "bank",
        ]
    )
    assert account_args.steward_command == "account"
    assert account_args.account_command == "set"
    transfer_args = parser.parse_args(
        [
            "steward",
            "transfer",
            "confirm",
            "--outgoing-id",
            "10",
            "--incoming-id",
            "20",
        ]
    )
    assert transfer_args.steward_command == "transfer"
    assert transfer_args.transfer_command == "confirm"
    holding_args = parser.parse_args(
        ["steward", "holding", "import", "--csv", "holdings.csv"]
    )
    assert holding_args.steward_command == "holding"
    assert holding_args.holding_command == "import"
    assert holding_args.csv == Path("holdings.csv")


def test_steward_cli_commands_delegate_to_job_functions(tmp_path, monkeypatch, capsys):
    calls = []

    def init_db(db_path):
        calls.append(("init", db_path))

    def import_inbox(db_path, inbox_path):
        calls.append(("import", db_path, inbox_path))

        class Summary:
            documents_seen = 1
            parsed_documents = 1
            imported_transactions = 2
            warnings = ["sample warning"]

        return Summary()

    def report(db_path, report_dir):
        calls.append(("report", db_path, report_dir))
        return report_dir / "portfolio-steward-report-2026-07-15.md"

    monkeypatch.setattr(app.main, "initialize_steward_database", init_db)
    monkeypatch.setattr(app.main, "import_steward_inbox", import_inbox)
    monkeypatch.setattr(app.main, "generate_steward_report", report)

    db_path = tmp_path / "steward.db"
    inbox = tmp_path / "inbox"
    report_dir = tmp_path / "reports"

    assert app.main.main(["steward", "init-db", "--db", str(db_path)]) == 0
    assert (
        app.main.main(
            [
                "steward",
                "import",
                "--db",
                str(db_path),
                "--inbox",
                str(inbox),
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
        ("import", db_path, inbox),
        ("report", db_path, report_dir),
    ]
    output = capsys.readouterr().out
    assert "Imported 2 steward transactions from 1 files" in output
    assert "sample warning" in output
    assert "Wrote steward report" in output


def test_steward_cli_persists_account_and_transfer_review(tmp_path, monkeypatch, capsys):
    calls = []

    class FakeRepository:
        def __init__(self, db_path):
            calls.append(("repo", db_path))

        def upsert_account_profile(self, account):
            calls.append(("account", account))

        def upsert_transfer_decision(self, decision):
            calls.append(("transfer", decision))

    monkeypatch.setattr(app.main, "StewardRepository", FakeRepository)
    monkeypatch.setattr(
        app.main,
        "initialize_steward_database",
        lambda db_path: calls.append(("init", db_path)),
    )
    db_path = tmp_path / "steward.db"

    assert (
        app.main.main(
            [
                "steward",
                "account",
                "set",
                "--db",
                str(db_path),
                "--institution",
                "cmb",
                "--account",
                "bank",
                "--currency",
                "cny",
                "--ownership",
                "owned",
                "--role",
                "bank",
            ]
        )
        == 0
    )
    assert (
        app.main.main(
            [
                "steward",
                "transfer",
                "reject",
                "--db",
                str(db_path),
                "--outgoing-id",
                "10",
                "--incoming-id",
                "20",
            ]
        )
        == 0
    )

    account = next(call[1] for call in calls if call[0] == "account")
    decision = next(call[1] for call in calls if call[0] == "transfer")
    assert account.currency == "CNY"
    assert account.ownership == "owned"
    assert account.role == "bank"
    assert decision.outgoing_transaction_id == 10
    assert decision.incoming_transaction_id == 20
    assert decision.status == "rejected"
    output = capsys.readouterr().out
    assert "Saved steward account profile" in output
    assert "Rejected transfer candidate 10 -> 20" in output


def test_steward_cli_imports_manual_holdings(tmp_path, monkeypatch, capsys):
    calls = []

    class Summary:
        rows_seen = 3
        imported_holdings = 2
        linked_fx_holdings = 1
        warnings = ["row 4: invalid quantity"]

    monkeypatch.setattr(
        app.main,
        "import_holdings_csv",
        lambda db_path, csv_path: calls.append((db_path, csv_path)) or Summary(),
    )
    db_path = tmp_path / "steward.db"
    csv_path = tmp_path / "holdings.csv"

    result = app.main.main(
        [
            "steward",
            "holding",
            "import",
            "--db",
            str(db_path),
            "--csv",
            str(csv_path),
        ]
    )

    assert result == 0
    assert calls == [(db_path, csv_path)]
    output = capsys.readouterr().out
    assert "Imported 2 of 3 holding rows" in output
    assert "automatically linked 1 USD holdings" in output
    assert "row 4: invalid quantity" in output


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
