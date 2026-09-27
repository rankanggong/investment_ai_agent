import argparse
from datetime import date
from decimal import Decimal
import os
from pathlib import Path

from app.collectors.price_collector import load_price_csv
from app.collectors.fundamental_csv_collector import load_fundamental_csv
from app.collectors.yfinance_price_collector import (
    choose_yfinance_period,
    collect_yfinance_prices,
)
from app.config import load_watchlist
from app.jobs.daily_market_job import generate_daily_report
from app.steward.job import (
    generate_steward_state_report,
    import_steward_state_csv,
)
from app.steward.income_expense.job import (
    calculate_monthly_allowance,
    import_income_expense_statement,
    render_monthly_summary,
    summarize_month,
)
from app.steward.storage import initialize_steward_database
from app.storage.db import initialize_database
from app.storage.repositories.price_repo import PriceRepository
from app.storage.repositories.fundamental_repo import FundamentalRepository


DEFAULT_DB_PATH = Path(os.environ.get("FINANCE_AGENT_DB_PATH", "data/finance.db"))
DEFAULT_WATCHLIST_PATH = Path("config/watchlist.yaml")
DEFAULT_REPORT_PROFILE_PATH = Path("config/report_profile.json")
DEFAULT_REPORT_DIR = Path(os.environ.get("FINANCE_AGENT_REPORT_DIR", "data/reports"))
DEFAULT_STEWARD_DB_PATH = Path(
    os.environ.get("FINANCE_AGENT_STEWARD_DB_PATH", "data/steward/steward.db")
)
DEFAULT_STEWARD_REPORT_DIR = Path(
    os.environ.get("FINANCE_AGENT_STEWARD_REPORT_DIR", "data/steward/reports")
)
DEFAULT_INCOME_EXPENSE_DB_PATH = Path(
    os.environ.get(
        "FINANCE_AGENT_INCOME_EXPENSE_DB_PATH",
        "data/steward/income_expense.db",
    )
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
    prices.add_argument(
        "--period",
        help=(
            "Force one Yahoo history period for every symbol, such as 5d or 1y. "
            "By default the collector chooses an incremental period per symbol."
        ),
    )

    fundamentals = collect_subparsers.add_parser(
        "fundamentals", help="Import valuation and earnings-estimate observations"
    )
    fundamentals.add_argument("--csv", type=Path, required=True)
    fundamentals.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    report = subparsers.add_parser("report", help="Generate reports")
    report_subparsers = report.add_subparsers(dest="report_command", required=True)
    daily = report_subparsers.add_parser("daily", help="Generate daily market report")
    daily.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    daily.add_argument("--watchlist", type=Path, default=DEFAULT_WATCHLIST_PATH)
    daily.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    daily.add_argument("--steward-db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    daily.add_argument(
        "--report-profile",
        type=Path,
        default=DEFAULT_REPORT_PROFILE_PATH,
    )

    steward = subparsers.add_parser(
        "steward",
        help="Import and report cash, holdings, and FX state",
    )
    steward_subparsers = steward.add_subparsers(dest="steward_command", required=True)
    steward_init_db = steward_subparsers.add_parser(
        "init-db",
        help="Initialize the steward SQLite database",
    )
    steward_init_db.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)

    steward_import = steward_subparsers.add_parser(
        "import",
        help="Replace steward state from a unified CSV file",
    )
    steward_import.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    steward_import.add_argument("--csv", type=Path, required=True)

    steward_report = steward_subparsers.add_parser(
        "report",
        help="Generate a cash, holdings, and FX state report",
    )
    steward_report.add_argument("--db", type=Path, default=DEFAULT_STEWARD_DB_PATH)
    steward_report.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_STEWARD_REPORT_DIR,
    )

    income_expense = steward_subparsers.add_parser(
        "income-expense",
        help="Parse daily income and expenses without investment analysis",
    )
    income_expense_subparsers = income_expense.add_subparsers(
        dest="income_expense_command",
        required=True,
    )
    income_expense_import = income_expense_subparsers.add_parser(
        "import",
        help="Import a bank statement PDF to CSV or a separate SQLite database",
    )
    income_expense_import.add_argument("--pdf", type=Path, required=True)
    income_expense_import.add_argument("--csv", type=Path)
    income_expense_import.add_argument("--db", type=Path)
    income_expense_summary = income_expense_subparsers.add_parser(
        "summary",
        help="Show monthly income and expense totals",
    )
    income_expense_summary.add_argument(
        "--db", type=Path, default=DEFAULT_INCOME_EXPENSE_DB_PATH
    )
    income_expense_summary.add_argument("--month", required=True, help="YYYY-MM")
    income_expense_summary.add_argument("--currency", default="CNY")
    income_expense_summary.add_argument("--as-of", type=date.fromisoformat)
    income_expense_summary.add_argument("--expected-income", type=Decimal)
    income_expense_summary.add_argument("--essential-budget", type=Decimal)
    income_expense_summary.add_argument("--investment-target", type=Decimal)
    income_expense_summary.add_argument(
        "--investment-rate", type=Decimal, default=Decimal("0.20")
    )
    income_expense_summary.add_argument("--safety-buffer", type=Decimal)
    income_expense_summary.add_argument(
        "--buffer-rate", type=Decimal, default=Decimal("0.10")
    )

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
            price_repo = PriceRepository(args.db)
            periods_by_symbol = None
            if args.period is None:
                periods_by_symbol = {
                    symbol: choose_yfinance_period(
                        *price_repo.get_history_coverage(symbol),
                        as_of_date=date.today(),
                    )
                    for symbol in symbols
                }
                plan_counts: dict[str, int] = {}
                for collection_period in periods_by_symbol.values():
                    plan_counts[collection_period] = (
                        plan_counts.get(collection_period, 0) + 1
                    )
                plan = ", ".join(
                    f"{collection_period}: {count}"
                    for collection_period, count in sorted(plan_counts.items())
                )
                print(f"Yahoo collection plan: {plan}")
            collection = collect_yfinance_prices(
                symbols,
                period=args.period or "1y",
                periods_by_symbol=periods_by_symbol,
            )
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

    if args.command == "collect" and args.collect_command == "fundamentals":
        initialize_database(args.db)
        imported = load_fundamental_csv(args.csv)
        repo = FundamentalRepository(args.db)
        repo.upsert_valuations(imported.valuations)
        repo.upsert_earnings_estimates(imported.earnings_estimates)
        print(
            f"Imported {len(imported.valuations)} valuation rows and "
            f"{len(imported.earnings_estimates)} earnings-estimate rows into "
            f"{args.db}"
        )
        return 0

    if args.command == "report" and args.report_command == "daily":
        initialize_database(args.db)
        path = generate_daily_report(
            args.db,
            args.watchlist,
            args.report_dir,
            steward_db_path=args.steward_db,
            report_profile_path=args.report_profile,
        )
        print(f"Wrote daily report to {path}")
        return 0

    if args.command == "steward" and args.steward_command == "init-db":
        initialize_steward_database(args.db)
        print(f"Initialized steward database at {args.db}")
        return 0

    if args.command == "steward" and args.steward_command == "import":
        try:
            summary = import_steward_state_csv(args.db, args.csv)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(
            f"Imported {summary.rows_seen} state rows: "
            f"{summary.cash_positions} cash, {summary.holdings} holdings, "
            f"{summary.fx_conversions} FX conversions into {args.db}"
        )
        return 0

    if args.command == "steward" and args.steward_command == "report":
        path = generate_steward_state_report(args.db, args.report_dir)
        print(f"Wrote steward report to {path}")
        return 0

    if (
        args.command == "steward"
        and args.steward_command == "income-expense"
        and args.income_expense_command == "import"
    ):
        db_path = args.db
        if args.csv is None and db_path is None:
            db_path = DEFAULT_INCOME_EXPENSE_DB_PATH
        try:
            summary = import_income_expense_statement(
                args.pdf,
                csv_path=args.csv,
                db_path=db_path,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            parser.error(str(exc))
        destinations = []
        if args.csv is not None:
            destinations.append(str(args.csv))
        if db_path is not None:
            destinations.append(str(db_path))
        print(
            f"Parsed {summary.parsed_entries} {summary.institution} "
            f"income/expense rows into {', '.join(destinations)}"
        )
        return 0

    if (
        args.command == "steward"
        and args.steward_command == "income-expense"
        and args.income_expense_command == "summary"
    ):
        try:
            summary = summarize_month(args.db, args.month, currency=args.currency)
            allowance = calculate_monthly_allowance(
                args.db,
                summary,
                as_of=args.as_of,
                expected_income=args.expected_income,
                essential_budget=args.essential_budget,
                investment_target=args.investment_target,
                safety_buffer=args.safety_buffer,
                investment_rate=args.investment_rate,
                buffer_rate=args.buffer_rate,
            )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(render_monthly_summary(summary, allowance))
        return 0

    parser.error("Unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
