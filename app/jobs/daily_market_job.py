from datetime import date
from pathlib import Path

from app.analyzers.daily_signal_summary_analyzer import analyze_daily_signal_summary
from app.analyzers.fundamental_event_analyzer import analyze_fundamental_events
from app.analyzers.macro_context_analyzer import analyze_macro_context
from app.analyzers.news_cluster_analyzer import analyze_news_clusters
from app.analyzers.price_move_analyzer import analyze_price_moves
from app.analyzers.sector_rotation_analyzer import analyze_sector_rotation
from app.config import load_watchlist
from app.outputs.markdown_writer import render_daily_report, write_daily_report
from app.storage.repositories.news_repo import NewsRepository
from app.storage.repositories.price_repo import PriceRepository
from app.storage.repositories.report_repo import ReportRepository


def generate_daily_report(
    db_path: Path,
    watchlist_path: Path,
    report_dir: Path,
    report_date: date | None = None,
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
    recent_news = NewsRepository(db_path).get_recent_items()
    news_clusters = analyze_news_clusters(recent_news)
    fundamental_events = analyze_fundamental_events(recent_news)
    daily_signal_summary = analyze_daily_signal_summary(
        signals,
        sector_rotation,
        macro_context,
        news_clusters,
        fundamental_events,
    )
    effective_date = report_date or _latest_report_date(history) or date.today()
    content = render_daily_report(
        report_date=effective_date,
        price_signals=signals,
        sector_rotation=sector_rotation,
        macro_context=macro_context,
        news_clusters=news_clusters,
        fundamental_events=fundamental_events,
        daily_signal_summary=daily_signal_summary,
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
