import argparse
import os
from pathlib import Path

from app.collectors.price_collector import load_price_csv
from app.collectors.yfinance_price_collector import collect_yfinance_prices
from app.config import load_watchlist
from app.jobs.daily_market_job import generate_daily_report
from app.steward.job import generate_steward_report, import_steward_inbox
from app.steward.holdings import import_holdings_csv
from app.steward.reconciliation import AccountProfile, TransferDecision
from app.steward.storage import StewardRepository, initialize_steward_database
from app.storage.db import initialize_database
from app.storage.repositories.price_repo import PriceRepository


DEFAULT_DB_PATH = Path(os.environ.get("FINANCE_AGENT_DB_PATH", "data/finance.db"))
DEFAULT_WATCHLIST_PATH = Path("config/watchlist.yaml")
DEFAULT_REPORT_DIR = Path(os.environ.get("FINANCE_AGENT_REPORT_DIR", "data/reports"))
DEFAULT_STEWARD_DB_PATH = Path(
    os.environ.get("FINANCE_AGENT_STEWARD_DB_PATH", "data/steward/steward.db")
)
DEFAULT_STEWARD_INBOX_PATH = Path(
    os.environ.get("FINANCE_AGENT_STEWARD_INBOX", "data/steward/inbox")
)
DEFAULT_STEWARD_REPORT_DIR = Path(
    os.environ.get("FINANCE_AGENT_STEWARD_REPORT_DIR", "data/steward/reports")
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finance-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Initialize the SQLite database")
    init_db.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    collect = subparsers.add_parser("collect", help="Collect or import data")
    collect_subparsers = collect.add_subparsers(dest="collect_command", required=True)
    prices = collect_subparsers.add_parser("prices", help="Collect daily price data")
    price_source = prices.add_mutually_exclusive_group(required=True)
    price_source.add_argument("--csv", type=Path)
    price_source.add_argument("--yfinance", action="store_true")
    prices.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    prices.add_argument("--source", default="csv")
    prices.add_argument("--symbols", nargs="+")
    prices.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST_PATH)

    report = subparsers.add_parser("report", help="Generate reports")
    report_subparsers = report.add_subparsers(dest="report_command", required=True)
    daily = report_subparsers.add_parser("daily", help="Generate daily market report")
    daily.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    daily.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST_PATH)
    daily.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)

    steward = subparsers.add_parser("steward", help="Import and report personal cash/FX state")
    steward_subparsers = steward.add_subparsers(dest="steward_command", required=True)
    steward_init_db = steward_subparsers.add_parser(
        "init-db",
        help="Initialize the steward SQLite database",
    )
    steward_init_db.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)

    steward_import = steward_subparsers.add_parser(
        "import",
        help="Import bank/payment statements from a local folder",
    )
    steward_import.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    steward_import.add_argument("--inbox", type=Path, default=DEFAULT_STEWARD_INBOX_PATH)

    steward_report = steward_subparsers.add_parser(
        "report",
        help="Generate a steward cash/FX review report",
    )
    steward_report.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    steward_report.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_STEWARD_REPORT_DIR,
    )

    steward_account = steward_subparsers.add_parser(
        "account",
        help="Register account ownership and role",
    )
    account_subparsers = steward_account.add_subparsers(
        dest="account_command",
        required=True,
    )
    account_set = account_subparsers.add_parser("set", help="Set an account profile")
    account_set.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    account_set.add_argument("--institution", required=True)
    account_set.add_argument("--account", dest="account_label", required=True)
    account_set.add_argument("--currency", required=True)
    account_set.add_argument(
        "--ownership",
        choices=("owned", "external", "unknown"),
        required=True,
    )
    account_set.add_argument(
        "--role",
        choices=("bank", "brokerage", "payment", "wallet", "other"),
        required=True,
    )

    steward_transfer = steward_subparsers.add_parser(
        "transfer",
        help="Confirm or reject a transfer candidate",
    )
    transfer_subparsers = steward_transfer.add_subparsers(
        dest="transfer_command",
        required=True,
    )
    for command in ("confirm", "reject"):
        transfer_command = transfer_subparsers.add_parser(command)
        transfer_command.add_argument(
            "--db",
            type=Path,
            default=DEFAULT_STEWARD_DB_PATH,
        )
        transfer_command.add_argument("--outgoing-id", type=int, required=True)
        transfer_command.add_argument("--incoming-id", type=int, required=True)

    steward_holding = steward_subparsers.add_parser(
        "holding",
        help="Manage manually supplied investment holdings",
    )
    holding_subparsers = steward_holding.add_subparsers(
        dest="holding_command",
        required=True,
    )
    holding_import = holding_subparsers.add_parser(
        "import",
        help="Import holdings from a CSV file and link USD rows to FX data",
    )
    holding_import.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    holding_import.add_argument("--csv", type=Path, required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-db":
        initialize_database(args.db)
        print(f"Initialized database at {args.db}")
        return 0

    if args.command == "collect" and args.collect_command == "prices":
        initialize_database(args.db)
        if args.csv:
            bars = load_price_csv(args.csv, source=args.source)
            failed_symbols: list[str] = []
            failure_reasons: dict[str, str] = {}
        else:
            symbols = (
                [symbol.upper() for symbol in args.symbols]
                if args.symbols
                else [asset.symbol for asset in load_watchlist(args.watchlist).assets]
            )
            collection = collect_yfinance_prices(symbols)
            bars = collection.bars
            failed_symbols = collection.failed_symbols
            failure_reasons = collection.failure_reasons

        PriceRepository(args.db).upsert_many(bars)
        print(f"Imported {len(bars)} price rows into {args.db}")
        if failed_symbols:
            print(f"Failed symbols: {', '.join(failed_symbols)}")
            for symbol in failed_symbols:
                reason = failure_reasons.get(symbol, "Unknown error")
                print(f"  {symbol}: {reason}")
            if any(
                reason.startswith("YFRateLimitError")
                for reason in failure_reasons.values()
            ):
                print(
                    "Yahoo rejected this network route; "
                    "this can happen without prior requests."
                )
                print("Try another network later or import a CSV.")
        return 0

    if args.command == "report" and args.report_command == "daily":
        initialize_database(args.db)
        path = generate_daily_report(args.db, args.watchlist, args.report_dir)
        print(f"Wrote daily report to {path}")
        return 0

    if args.command == "steward" and args.steward_command == "init-db":
        initialize_steward_database(args.db)
        print(f"Initialized steward database at {args.db}")
        return 0

    if args.command == "steward" and args.steward_command == "import":
        summary = import_steward_inbox(args.db, args.inbox)
        print(
            f"Imported {summary.imported_transactions} steward transactions "
            f"from {summary.documents_seen} files into {args.db}"
        )
        if summary.warnings:
            print("Warnings:")
            for warning in summary.warnings:
                print(f"  {warning}")
        return 0

    if args.command == "steward" and args.steward_command == "report":
        path = generate_steward_report(args.db, args.report_dir)
        print(f"Wrote steward report to {path}")
        return 0

    if (
        args.command == "steward"
        and args.steward_command == "account"
        and args.account_command == "set"
    ):
        initialize_steward_database(args.db)
        profile = AccountProfile(
            institution=args.institution,
            account_label=args.account_label,
            currency=args.currency.upper(),
            ownership=args.ownership,
            role=args.role,
        )
        StewardRepository(args.db).upsert_account_profile(profile)
        print(
            "Saved steward account profile for "
            f"{profile.institution} / {profile.account_label} / {profile.currency}"
        )
        return 0

    if args.command == "steward" and args.steward_command == "transfer":
        if args.outgoing_id == args.incoming_id:
            parser.error("Transfer legs must use different statement transaction IDs")
        initialize_steward_database(args.db)
        status = "confirmed" if args.transfer_command == "confirm" else "rejected"
        decision = TransferDecision(
            outgoing_transaction_id=args.outgoing_id,
            incoming_transaction_id=args.incoming_id,
            status=status,
        )
        StewardRepository(args.db).upsert_transfer_decision(decision)
        verb = "Confirmed" if status == "confirmed" else "Rejected"
        print(
            f"{verb} transfer candidate "
            f"{decision.outgoing_transaction_id} -> {decision.incoming_transaction_id}"
        )
        return 0

    if (
        args.command == "steward"
        and args.steward_command == "holding"
        and args.holding_command == "import"
    ):
        try:
            summary = import_holdings_csv(args.db, args.csv)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(
            f"Imported {summary.imported_holdings} of {summary.rows_seen} holding rows; "
            f"automatically linked {summary.linked_fx_holdings} USD holdings to FX data"
        )
        if summary.warnings:
            print("Warnings:")
            for warning in summary.warnings:
                print(f"  {warning}")
        return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
