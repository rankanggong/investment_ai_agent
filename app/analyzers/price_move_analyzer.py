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
    absolute_move_z_score = _absolute_move_z_score_60d(bars)
    atr_20 = _atr_20(bars)
    atr_multiple = _atr_multiple(bars, atr_20)
    absolute_move_percentile = _absolute_move_percentile_252d(bars)
    is_unusual, reason = _unusual_move_reason(
        volume_ratio,
        absolute_move_z_score,
        atr_multiple,
        absolute_move_percentile,
    )
    sma_50 = _moving_average(bars, 50)
    sma_200 = _moving_average(bars, 200)

    return PriceSignal(
        symbol=symbol.upper(),
        return_1d=return_1d,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=volume_ratio,
        volatility_zscore=absolute_move_z_score,
        is_unusual_move=is_unusual,
        reason=reason,
        latest=latest.close,
        latest_date=latest.date,
        sma_50=sma_50,
        sma_200=sma_200,
        distance_to_50d=_distance(latest.close, sma_50),
        distance_to_200d=_distance(latest.close, sma_200),
        drawdown_from_high=_drawdown_from_252d_high(bars),
        atr_20=atr_20,
        atr_multiple=atr_multiple,
        return_zscore_60d=absolute_move_z_score,
        historical_percentile=absolute_move_percentile,
        sma_50_slope_20d=_moving_average_slope(bars, 50, 20),
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


def _absolute_move_z_score_60d(bars: list[PriceBar]) -> float | None:
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
    absolute_move_z_score: float | None,
    atr_multiple: float | None,
    absolute_move_percentile: float | None,
) -> tuple[bool, str]:
    reasons: list[str] = []
    if absolute_move_z_score is not None and absolute_move_z_score >= 2.0:
        reasons.append("absolute-move z-score ≥ 2.0")
    if atr_multiple is not None and atr_multiple >= 1.5:
        reasons.append("1D move ≥ 1.5 ATR")
    if absolute_move_percentile is not None and absolute_move_percentile >= 0.95:
        reasons.append("absolute move ≥ 95th 252D percentile")
    if volume_ratio is not None and volume_ratio > 2:
        reasons.append("volume exceeds 2x recent average")
    metrics = (
        f"absolute_move_z_score_60d={_metric(absolute_move_z_score)}; "
        f"ATR={_multiple(atr_multiple)}; "
        f"absolute_move_percentile_252d={_percentile(absolute_move_percentile)}"
    )
    prefix = "; ".join(reasons) if reasons else "No standardized threshold crossed"
    return bool(reasons), f"{prefix} ({metrics})"


def _moving_average(bars: list[PriceBar], window: int) -> float | None:
    if len(bars) < window:
        return None
    return mean(bar.close for bar in bars[-window:])


def _moving_average_slope(
    bars: list[PriceBar],
    window: int,
    change_window: int,
) -> float | None:
    if len(bars) < window + change_window:
        return None
    current = mean(bar.close for bar in bars[-window:])
    previous = mean(
        bar.close for bar in bars[-window - change_window:-change_window]
    )
    if previous == 0:
        return None
    return current / previous - 1


def _distance(latest: float, average: float | None) -> float | None:
    if average in {None, 0}:
        return None
    return latest / average - 1


def _drawdown_from_252d_high(bars: list[PriceBar]) -> float | None:
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


def _absolute_move_percentile_252d(bars: list[PriceBar]) -> float | None:
    returns = _daily_returns(bars[-254:])
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
