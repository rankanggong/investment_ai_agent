import argparse
import os
from pathlib import Path

from app.collectors.price_collector import load_price_csv
from app.collectors.yfinance_price_collector import collect_yfinance_prices
from app.config import load_watchlist
from app.jobs.daily_market_job import generate_daily_report
from app.storage.db import initialize_database
from app.storage.repositories.price_repo import PriceRepository


DEFAULT_DB_PATH = Path(os.environ.get("FINANCE_AGENT_DB_PATH", "data/finance.db"))
DEFAULT_WATCHLIST_PATH = Path("config/watchlist.yaml")
DEFAULT_REPORT_DIR = Path(os.environ.get("FINANCE_AGENT_REPORT_DIR", "data/reports"))


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

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
