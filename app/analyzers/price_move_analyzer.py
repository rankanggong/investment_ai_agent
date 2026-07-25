from statistics import mean, pstdev

from app.models.analysis import PriceSignal
from app.models.price import PriceBar


def analyze_price_moves(price_history: dict[str, list[PriceBar]]) -> dict[str, PriceSignal]:
    return {
        symbol: _analyze_symbol(symbol, sorted(bars, key=lambda bar: bar.date))
        for symbol, bars in price_history.items()
        if bars
    }


def _analyze_symbol(symbol: str, bars: list[PriceBar]) -> PriceSignal:
    latest = bars[-1]
    return_1d = _return_over(bars, 1)
    return_5d = _return_over(bars, 5)
    return_20d = _return_over(bars, 20)
    volume_ratio = _volume_ratio_20d(bars)
    return_zscore = _return_zscore_60d(bars)
    atr_20 = _atr_20(bars)
    atr_multiple = _atr_multiple(bars, atr_20)
    historical_percentile = _historical_percentile(bars)
    is_unusual, reason = _unusual_move_reason(
        volume_ratio,
        return_zscore,
        atr_multiple,
        historical_percentile,
    )
    sma_50 = _moving_average(bars, 50)
    sma_200 = _moving_average(bars, 200)

    return PriceSignal(
        symbol=symbol.upper(),
        return_1d=return_1d,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=volume_ratio,
        volatility_zscore=return_zscore,
        is_unusual_move=is_unusual,
        reason=reason,
        latest=latest.close,
        latest_date=latest.date,
        sma_50=sma_50,
        sma_200=sma_200,
        distance_to_50d=_distance(latest.close, sma_50),
        distance_to_200d=_distance(latest.close, sma_200),
        drawdown_from_high=_drawdown_from_high(bars),
        atr_20=atr_20,
        atr_multiple=atr_multiple,
        return_zscore_60d=return_zscore,
        historical_percentile=historical_percentile,
    )


def _return_over(bars: list[PriceBar], days: int) -> float | None:
    if len(bars) <= days:
        return None
    previous = bars[-days - 1].close
    if previous == 0:
        return None
    return bars[-1].close / previous - 1


def _daily_returns(bars: list[PriceBar]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(bars, bars[1:]):
        if previous.close != 0:
            returns.append(current.close / previous.close - 1)
    return returns


def _volume_ratio_20d(bars: list[PriceBar]) -> float | None:
    if len(bars) < 21 or bars[-1].volume is None:
        return None
    volumes = [bar.volume for bar in bars[-21:-1] if bar.volume is not None]
    if not volumes:
        return None
    average_volume = mean(volumes)
    if average_volume == 0:
        return None
    return bars[-1].volume / average_volume


def _return_zscore_60d(bars: list[PriceBar]) -> float | None:
    returns = _daily_returns(bars[-61:])
    if len(returns) < 2:
        return None
    baseline = returns[:-1]
    if not baseline:
        return None
    volatility = pstdev(baseline)
    if volatility == 0:
        return None
    return (abs(returns[-1]) - mean(abs(value) for value in baseline)) / volatility


def _unusual_move_reason(
    volume_ratio: float | None,
    return_zscore: float | None,
    atr_multiple: float | None,
    historical_percentile: float | None,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if return_zscore is not None and return_zscore >= 2.0:
        reasons.append("return z-score ≥ 2.0")
    if atr_multiple is not None and atr_multiple >= 1.5:
        reasons.append("1D move ≥ 1.5 ATR")
    if historical_percentile is not None and historical_percentile >= 0.95:
        reasons.append("absolute return ≥ 95th historical percentile")
    if volume_ratio is not None and volume_ratio > 2:
        reasons.append("volume exceeds 2x recent average")
    metrics = (
        f"z={_metric(return_zscore)}; ATR={_multiple(atr_multiple)}; "
        f"percentile={_percentile(historical_percentile)}"
    )
    prefix = "; ".join(reasons) if reasons else "No standardized threshold crossed"
    return bool(reasons), f"{prefix} ({metrics})"


def _moving_average(bars: list[PriceBar], window: int) -> float | None:
    if len(bars) < window:
        return None
    return mean(bar.close for bar in bars[-window:])


def _distance(latest: float, average: float | None) -> float | None:
    if average in {None, 0}:
        return None
    return latest / average - 1


def _drawdown_from_high(bars: list[PriceBar]) -> float | None:
    if not bars:
        return None
    high = max(bar.close for bar in bars[-252:])
    if high == 0:
        return None
    return bars[-1].close / high - 1


def _atr_20(bars: list[PriceBar]) -> float | None:
    if len(bars) < 21:
        return None
    true_ranges: list[float] = []
    for previous, current in zip(bars[-21:-1], bars[-20:]):
        high = current.high if current.high is not None else current.close
        low = current.low if current.low is not None else current.close
        true_ranges.append(
            max(
                high - low,
                abs(high - previous.close),
                abs(low - previous.close),
            )
        )
    return mean(true_ranges) if true_ranges else None


def _atr_multiple(bars: list[PriceBar], atr_20: float | None) -> float | None:
    if len(bars) < 2 or atr_20 in {None, 0}:
        return None
    return abs(bars[-1].close - bars[-2].close) / atr_20


def _historical_percentile(bars: list[PriceBar]) -> float | None:
    returns = _daily_returns(bars[-253:])
    if len(returns) < 20:
        return None
    latest = abs(returns[-1])
    baseline = [abs(value) for value in returns[:-1]]
    return sum(value <= latest for value in baseline) / len(baseline)


def _metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def _multiple(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}x"


def _percentile(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"
