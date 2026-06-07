from app.models.analysis import PriceSignal, SectorRotation


def analyze_sector_rotation(
    signals: dict[str, PriceSignal],
    sector_symbols: list[str],
    benchmark_symbol: str = "SPY",
) -> SectorRotation:
    benchmark = signals.get(benchmark_symbol)
    benchmark_return = benchmark.return_5d if benchmark and benchmark.return_5d is not None else 0.0

    relative: list[tuple[str, float]] = []
    for symbol in sector_symbols:
        signal = signals.get(symbol)
        if signal is None or signal.return_5d is None:
            continue
        relative.append((symbol, signal.return_5d - benchmark_return))

    relative.sort(key=lambda item: item[1], reverse=True)
    strong = [symbol for symbol, value in relative if value > 0.02][:3]
    weak = [symbol for symbol, value in sorted(relative, key=lambda item: item[1]) if value < -0.02][:3]
    risk_on_score = _risk_on_score(relative)

    return SectorRotation(
        strong_sectors=strong,
        weak_sectors=weak,
        risk_on_score=risk_on_score,
        growth_vs_value=_growth_vs_value(signals),
        cyclical_vs_defensive=_cyclical_vs_defensive(signals),
        notes=[],
    )


def _risk_on_score(relative: list[tuple[str, float]]) -> float:
    if not relative:
        return 0.0
    average = sum(value for _, value in relative) / len(relative)
    return max(-1.0, min(1.0, average * 10))


def _growth_vs_value(signals: dict[str, PriceSignal]) -> str:
    qqq = signals.get("QQQ")
    spy = signals.get("SPY")
    if not qqq or not spy or qqq.return_5d is None or spy.return_5d is None:
        return "unknown"
    if qqq.return_5d - spy.return_5d > 0.01:
        return "growth_leading"
    if spy.return_5d - qqq.return_5d > 0.01:
        return "broad_market_leading"
    return "mixed"


def _cyclical_vs_defensive(signals: dict[str, PriceSignal]) -> str:
    cyclicals = _average_return(signals, ["XLI", "XLF", "XLE", "XLY"])
    defensives = _average_return(signals, ["XLU", "XLP", "XLV"])
    if cyclicals is None or defensives is None:
        return "unknown"
    if cyclicals - defensives > 0.01:
        return "cyclical_leading"
    if defensives - cyclicals > 0.01:
        return "defensive_leading"
    return "mixed"


def _average_return(signals: dict[str, PriceSignal], symbols: list[str]) -> float | None:
    values = [
        signals[symbol].return_5d
        for symbol in symbols
        if symbol in signals and signals[symbol].return_5d is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)

