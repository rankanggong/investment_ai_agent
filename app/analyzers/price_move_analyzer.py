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
    volatility_zscore = _volatility_zscore(bars)
    is_unusual, reason = _unusual_move_reason(return_1d, return_5d, volume_ratio, bars)

    return PriceSignal(
        symbol=symbol.upper(),
        return_1d=return_1d,
        return_5d=return_5d,
        return_20d=return_20d,
        volume_ratio_20d=volume_ratio,
        volatility_zscore=volatility_zscore,
        is_unusual_move=is_unusual,
        reason=reason,
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


def _volatility_zscore(bars: list[PriceBar]) -> float | None:
    returns = _daily_returns(bars[-22:])
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
    return_1d: float | None,
    return_5d: float | None,
    volume_ratio: float | None,
    bars: list[PriceBar],
) -> tuple[bool, str]:
    reasons: list[str] = []
    recent_returns = _daily_returns(bars[-21:])
    avg_abs_return = mean(abs(value) for value in recent_returns[:-1]) if len(recent_returns) > 1 else 0

    if return_1d is not None and abs(return_1d) > max(0.03, 1.5 * avg_abs_return):
        reasons.append("1D return exceeds recent volatility threshold")
    if volume_ratio is not None and volume_ratio > 2:
        reasons.append("volume exceeds 2x recent average")
    if return_5d is not None and recent_returns:
        weekly_threshold = 2 * (pstdev(recent_returns) if len(recent_returns) > 1 else 0)
        if abs(return_5d) > weekly_threshold:
            reasons.append("5D return exceeds recent weekly volatility proxy")

    return bool(reasons), "; ".join(reasons)

