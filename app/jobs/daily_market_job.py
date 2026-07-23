from datetime import date
from pathlib import Path

from app.analyzers.company_price_bounds_analyzer import analyze_company_price_bounds
from app.analyzers.data_coverage_analyzer import analyze_data_coverage
from app.analyzers.daily_signal_summary_analyzer import analyze_daily_signal_summary
from app.analyzers.macro_context_analyzer import analyze_macro_context
from app.analyzers.plan_impact_analyzer import analyze_plan_impact
from app.analyzers.price_move_analyzer import analyze_price_moves
from app.analyzers.report_signal_analyzer import analyze_report_signals
from app.analyzers.sector_rotation_analyzer import analyze_sector_rotation
from app.config import load_watchlist
from app.outputs.markdown_writer import render_daily_report, write_daily_report
from app.steward.storage import StewardRepository, initialize_steward_database
from app.storage.repositories.price_repo import PriceRepository
from app.storage.repositories.report_repo import ReportRepository


def generate_daily_report(
    db_path: Path,
    watchlist_path: Path,
    report_dir: Path,
    report_date: date | None = None,
    steward_db_path: Path | None = None,
) -> Path:
    watchlist = load_watchlist(watchlist_path)
    repo = PriceRepository(db_path)
    history = {symbol: repo.get_prices(symbol) for symbol in [asset.symbol for asset in watchlist.assets]}
    signals = analyze_price_moves(history)
    sector_rotation = analyze_sector_rotation(
        signals,
        sector_symbols=watchlist.symbols_for_group("sectors"),
        benchmark_symbol="SPY",
    )
    macro_context = analyze_macro_context(signals)
    data_coverage = analyze_data_coverage(
        price_history=history,
        price_symbols=[asset.symbol for asset in watchlist.assets],
        macro_symbols=["SPY", "TLT", "UUP", "HYG", "LQD", "GLD"],
        popular_company_symbols=watchlist.symbols_for_group("popular_companies"),
    )
    company_price_bounds = analyze_company_price_bounds(
        history,
        watchlist.symbols_for_group("popular_companies"),
    )
    plan_impact = analyze_plan_impact(
        signals,
        sector_rotation,
        macro_context,
        [],
        [],
    )
    daily_signal_summary = analyze_daily_signal_summary(
        signals,
        sector_rotation,
        macro_context,
    )
    report_signals = analyze_report_signals(
        price_signals=signals,
        sector_rotation=sector_rotation,
        macro_context=macro_context,
        news_clusters=[],
        fundamental_events=[],
        data_coverage=data_coverage,
    )
    portfolio_holdings = None
    if steward_db_path is not None:
        initialize_steward_database(steward_db_path)
        portfolio_holdings = StewardRepository(steward_db_path).load_state().holdings
    effective_date = report_date or _latest_report_date(history) or date.today()
    content = render_daily_report(
        report_date=effective_date,
        price_signals=signals,
        sector_rotation=sector_rotation,
        macro_context=macro_context,
        daily_signal_summary=daily_signal_summary,
        data_coverage=data_coverage,
        plan_impact=plan_impact,
        company_price_bounds=company_price_bounds,
        report_signals=report_signals,
        portfolio_holdings=portfolio_holdings,
    )
    path = write_daily_report(report_dir, effective_date, content)
    ReportRepository(db_path).insert_report(
        report_type="daily",
        report_date=effective_date,
        title=f"Daily Market Brief - {effective_date.isoformat()}",
        content=content,
    )
    return path


def _latest_report_date(history: dict[str, list]) -> date | None:
    dates = [bars[-1].date for bars in history.values() if bars]
    if not dates:
        return None
    return max(dates)
