from app.models.analysis import (
    FundamentalEvent,
    MacroContext,
    NewsCluster,
    PlanImpact,
    PlanImpactItem,
    PriceSignal,
    SectorRotation,
)

ACCUMULATION_THRESHOLD = 2
DERISK_THRESHOLD = -2
BROAD_RISK_ASSETS = {
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "SOXX",
    "SMH",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLY",
    "XLP",
    "XLU",
    "XLI",
    "XLC",
    "XLRE",
}


def analyze_plan_impact(
    price_signals: dict[str, PriceSignal],
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    news_clusters: list[NewsCluster],
    fundamental_events: list[FundamentalEvent],
) -> PlanImpact:
    symbols = _symbols_to_score(price_signals, news_clusters, fundamental_events)
    items = [
        _score_symbol(
            symbol=symbol,
            signal=price_signals.get(symbol),
            sector_rotation=sector_rotation,
            macro_context=macro_context,
            news_clusters=news_clusters,
            fundamental_events=fundamental_events,
        )
        for symbol in symbols
    ]

    accumulation = sorted(
        [item for item in items if item.score >= ACCUMULATION_THRESHOLD],
        key=lambda item: (-item.score, item.symbol),
    )
    derisk = sorted(
        [item for item in items if item.score <= DERISK_THRESHOLD],
        key=lambda item: (item.score, item.symbol),
    )

    notes: list[str] = []
    if not accumulation and not derisk:
        notes.append("No asset crossed accumulation or de-risk review thresholds.")

    return PlanImpact(
        accumulation_review=accumulation,
        derisk_review=derisk,
        notes=notes,
    )


def _symbols_to_score(
    price_signals: dict[str, PriceSignal],
    news_clusters: list[NewsCluster],
    fundamental_events: list[FundamentalEvent],
) -> list[str]:
    symbols = {symbol.upper() for symbol in price_signals}
    for cluster in news_clusters:
        symbols.update(asset.upper() for asset in cluster.related_assets)
    for event in fundamental_events:
        symbols.add(event.related_symbol.upper())
    return sorted(symbols)


def _score_symbol(
    symbol: str,
    signal: PriceSignal | None,
    sector_rotation: SectorRotation,
    macro_context: MacroContext | None,
    news_clusters: list[NewsCluster],
    fundamental_events: list[FundamentalEvent],
) -> PlanImpactItem:
    score = 0
    evidence: list[str] = []

    price_score, price_evidence = _price_score(signal)
    score += price_score
    evidence.extend(price_evidence)

    macro_score, macro_evidence = _macro_score(symbol, macro_context)
    score += macro_score
    evidence.extend(macro_evidence)

    sector_score, sector_evidence = _sector_score(symbol, sector_rotation)
    score += sector_score
    evidence.extend(sector_evidence)

    news_score, news_evidence = _news_score(symbol, news_clusters)
    score += news_score
    evidence.extend(news_evidence)

    event_score, event_evidence = _event_score(symbol, fundamental_events)
    score += event_score
    evidence.extend(event_evidence)

    return PlanImpactItem(symbol=symbol, score=score, evidence=evidence)


def _price_score(signal: PriceSignal | None) -> tuple[int, list[str]]:
    if signal is None:
        return 0, []

    score = 0
    evidence: list[str] = []
    if signal.return_20d is not None:
        if signal.return_20d >= 0.05:
            score += 1
            evidence.append("20D trend positive")
        elif signal.return_20d <= -0.05:
            score -= 1
            evidence.append("20D trend negative")

    if signal.return_5d is not None:
        if signal.return_5d >= 0.03:
            score += 1
            evidence.append("5D momentum positive")
        elif signal.return_5d <= -0.03:
            score -= 1
            evidence.append("5D momentum negative")

    if signal.is_unusual_move and signal.return_1d is not None:
        if signal.return_1d > 0:
            score += 1
            evidence.append("unusual positive price move")
        elif signal.return_1d < 0:
            score -= 1
            evidence.append("unusual negative price move")

    return score, evidence


def _macro_score(symbol: str, macro_context: MacroContext | None) -> tuple[int, list[str]]:
    if macro_context is None:
        return 0, []

    if symbol in BROAD_RISK_ASSETS:
        if macro_context.overall_regime == "risk_on_with_macro_support":
            return 1, ["macro regime supports broad risk assets"]
        if macro_context.overall_regime == "risk_off_with_macro_pressure":
            return -1, ["macro regime pressures broad risk assets"]

    if symbol == "TLT":
        if macro_context.rates_context == "duration_supported":
            return 1, ["duration backdrop supports long-duration assets"]
        if macro_context.rates_context == "rates_pressure":
            return -1, ["rates pressure weighs on duration assets"]

    if symbol == "GLD":
        if macro_context.gold_context == "gold_supported":
            return 1, ["gold backdrop is supportive"]
        if macro_context.gold_context == "gold_pressure":
            return -1, ["gold backdrop is under pressure"]

    if symbol in {"UUP", "USD/CNH"}:
        if macro_context.usd_context == "usd_strengthening":
            return 1, ["USD backdrop is strengthening"]
        if macro_context.usd_context == "usd_weakening":
            return -1, ["USD backdrop is weakening"]

    return 0, []


def _sector_score(symbol: str, sector_rotation: SectorRotation) -> tuple[int, list[str]]:
    if symbol in sector_rotation.strong_sectors:
        return 1, ["sector rotation shows relative strength"]
    if symbol in sector_rotation.weak_sectors:
        return -1, ["sector rotation shows relative weakness"]
    return 0, []


def _news_score(symbol: str, news_clusters: list[NewsCluster]) -> tuple[int, list[str]]:
    for cluster in news_clusters:
        if symbol in {asset.upper() for asset in cluster.related_assets}:
            return 1, ["important news cluster present"]
    return 0, []


def _event_score(
    symbol: str,
    fundamental_events: list[FundamentalEvent],
) -> tuple[int, list[str]]:
    score = 0
    evidence: list[str] = []
    for event in fundamental_events:
        if event.related_symbol.upper() != symbol:
            continue
        if event.event_type == "regulatory_event":
            score -= 2
            evidence.append("regulatory event requires de-risk review")
        else:
            score += 1
            evidence.append(f"{event.event_type} requires review")
    return score, evidence
