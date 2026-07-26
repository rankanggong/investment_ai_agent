from dataclasses import replace
from datetime import date
from pathlib import Path

from app.analyzers.company_price_bounds_analyzer import analyze_company_price_bounds
from app.analyzers.data_coverage_analyzer import analyze_data_coverage
from app.analyzers.daily_report_state_analyzer import (
    analyze_fx_state,
    analyze_market_breadth,
    analyze_portfolio_summary,
    assess_market_risk,
    assess_portfolio_decision_risk,
    build_gpt_tasks,
    build_report_state,
    build_report_use_states,
    combine_data_quality,
    compare_report_states,
    evaluate_strategy_rules,
    extract_report_state,
    select_key_market_evidence,
)
from app.analyzers.daily_signal_summary_analyzer import analyze_daily_signal_summary
from app.analyzers.macro_context_analyzer import analyze_macro_context
from app.analyzers.price_move_analyzer import analyze_price_moves
from app.analyzers.portfolio_impact_analyzer import analyze_portfolio_impact
from app.analyzers.report_signal_analyzer import analyze_report_signals
from app.analyzers.sector_rotation_analyzer import analyze_sector_rotation
from app.analyzers.strategy_rule_engine import evaluate_strategy_decision
from app.config import load_report_profile, load_watchlist
from app.models.analysis import NewsQualityGate
from app.outputs.markdown_writer import render_daily_report, write_daily_report
from app.steward.models import PortfolioReportState
from app.steward.storage import StewardRepository, initialize_steward_database
from app.storage.db import initialize_database
from app.storage.repositories.price_repo import PriceRepository
from app.storage.repositories.report_repo import ReportRepository


def generate_daily_report(
    db_path: Path,
    watchlist_path: Path,
    report_dir: Path,
    report_date: date | None = None,
    steward_db_path: Path | None = None,
    report_profile_path: Path | None = None,
) -> Path:
    initialize_database(db_path)
    watchlist = load_watchlist(watchlist_path)
    report_profile = load_report_profile(report_profile_path)
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
        macro_symbols=[
            "SPY",
            "TLT",
            "UUP",
            "HYG",
            "LQD",
            "GLD",
            *watchlist.symbols_for_group("macro_actual"),
        ],
        popular_company_symbols=watchlist.symbols_for_group("popular_companies"),
    )
    company_price_bounds = analyze_company_price_bounds(
        history,
        watchlist.symbols_for_group("popular_companies"),
    )
    news_quality = NewsQualityGate(
        entity_precision=None,
        precision_threshold=0.80,
        status="disabled",
        news_score=None,
        fundamental_score=None,
        portfolio_action="unavailable",
        reasons=["News collection is disabled."],
    )
    daily_signal_summary = analyze_daily_signal_summary(
        signals,
        sector_rotation,
        macro_context,
        news_quality=news_quality,
    )
    report_signals = analyze_report_signals(
        price_signals=signals,
        sector_rotation=sector_rotation,
        macro_context=macro_context,
        news_clusters=[],
        fundamental_events=[],
        data_coverage=data_coverage,
    )
    portfolio_state = None
    if steward_db_path is not None:
        initialize_steward_database(steward_db_path)
        steward_state = StewardRepository(steward_db_path).load_state()
        portfolio_state = PortfolioReportState(
            holdings=steward_state.holdings,
            fx_conversions=steward_state.fx_conversions,
            cash_positions=steward_state.cash_positions,
        )
    effective_date = report_date or _latest_report_date(history) or date.today()
    data_coverage = combine_data_quality(
        data_coverage,
        news_quality,
        portfolio_state,
        effective_date,
    )
    portfolio_summary = analyze_portfolio_summary(
        portfolio_state,
        report_profile,
        signals,
        effective_date,
    )
    key_evidence = select_key_market_evidence(signals)
    market_breadth = analyze_market_breadth(signals, history)
    market_risk = assess_market_risk(
        signals,
        market_breadth,
    )
    portfolio_decision_risk = assess_portfolio_decision_risk(portfolio_summary)
    fx_state = analyze_fx_state(
        portfolio_state,
        portfolio_summary,
        history.get("USD/CNH", []),
    )
    use_states = build_report_use_states(
        market_risk,
        macro_context,
        sector_rotation,
        data_coverage,
        portfolio_summary,
        portfolio_decision_risk,
        news_quality,
        report_profile,
        fx_state,
    )
    portfolio_impact = analyze_portfolio_impact(
        portfolio_summary,
        report_profile.portfolio_factors,
        market_risk,
        use_states.market.actionability,
    )
    monitoring_rules = evaluate_strategy_rules(
        signals,
        sector_rotation,
        portfolio_summary,
        key_evidence,
        use_states,
    )
    strategy_decision = evaluate_strategy_decision(
        report_profile.strategy_rules,
        signals,
        macro_context,
        market_breadth,
        use_states,
        daily_budget=report_profile.daily_budget,
        action_sizing=report_profile.action_sizing,
    )
    strategy_rules = [*strategy_decision.rules, *monitoring_rules]
    report_state = build_report_state(
        use_states,
        market_risk,
        portfolio_decision_risk,
        strategy_rules,
        key_evidence,
        portfolio_summary,
        fx_state,
        strategy_decision,
        portfolio_impact,
    )
    report_repo = ReportRepository(db_path)
    previous_state = extract_report_state(
        report_repo.get_previous_content("daily", effective_date)
        or _previous_report_file_content(report_dir, effective_date)
    )
    changes = compare_report_states(previous_state, report_state)
    gpt_tasks = build_gpt_tasks(
        report_profile,
        changes,
        strategy_rules,
        key_evidence,
        use_states,
        strategy_decision,
    )
    report_state = replace(
        report_state,
        gpt_task_ids=tuple(task.task_id for task in gpt_tasks),
    )
    price_sources = {
        symbol: bars[-1].source
        for symbol, bars in history.items()
        if bars
    }
    content = render_daily_report(
        report_date=effective_date,
        price_signals=signals,
        sector_rotation=sector_rotation,
        macro_context=macro_context,
        daily_signal_summary=daily_signal_summary,
        data_coverage=data_coverage,
        company_price_bounds=company_price_bounds,
        report_signals=report_signals,
        portfolio_state=portfolio_state,
        news_quality=news_quality,
        portfolio_summary=portfolio_summary,
        risk_assessment=market_risk,
        portfolio_decision_risk=portfolio_decision_risk,
        use_states=use_states,
        market_breadth=market_breadth,
        fx_costs=list(fx_state.comparisons),
        fx_state=fx_state,
        key_evidence=key_evidence,
        strategy_rules=strategy_rules,
        strategy_decision=strategy_decision,
        portfolio_impact=portfolio_impact,
        changes=changes,
        gpt_tasks=gpt_tasks,
        report_state=report_state,
        price_sources=price_sources,
    )
    path = write_daily_report(report_dir, effective_date, content)
    report_repo.insert_report(
        report_type="daily",
        report_date=effective_date,
        title=f"Daily Market State - {effective_date.isoformat()}",
        content=content,
    )
    report_repo.upsert_decision_state(effective_date, strategy_decision)
    return path


def _latest_report_date(history: dict[str, list]) -> date | None:
    dates = [bars[-1].date for bars in history.values() if bars]
    if not dates:
        return None
    return max(dates)


def _previous_report_file_content(
    report_dir: Path,
    before_date: date,
) -> str | None:
    candidates: list[tuple[date, Path]] = []
    for path in report_dir.glob("daily-market-brief-*.md"):
        try:
            report_day = date.fromisoformat(
                path.stem.removeprefix("daily-market-brief-")
            )
        except ValueError:
            continue
        if report_day < before_date:
            candidates.append((report_day, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1].read_text(
        encoding="utf-8"
    )
