from datetime import date, timedelta

from app.analyzers.price_move_analyzer import analyze_price_moves
from app.models.price import PriceBar


def make_bar(day, close, volume=1000):
    return PriceBar(
        symbol="GLD",
        date=date(2026, 1, 1) + timedelta(days=day),
        open=close,
        high=close,
        low=close,
        close=close,
        adjusted_close=close,
        volume=volume,
        source="test",
    )


def test_analyze_price_moves_calculates_returns_and_flags_unusual_move():
    prices = [make_bar(i, 100 + i * 0.1) for i in range(21)]
    prices.append(make_bar(21, 108, volume=3000))

    signals = analyze_price_moves({"GLD": prices})
    signal = signals["GLD"]

    assert round(signal.return_1d, 4) == round((108 / 102 - 1), 4)
    assert signal.return_5d > 0.05
    assert signal.return_20d > 0.07
    assert signal.volume_ratio_20d == 3.0
    assert signal.is_unusual_move is True
    assert signal.latest == 108
    assert signal.latest_date == date(2026, 1, 22)


def test_analyze_price_moves_calculates_long_horizon_and_standardized_metrics():
    prices = [make_bar(i, 100 + i * 0.2) for i in range(219)]
    prices.append(make_bar(219, 160, volume=4000))

    signal = analyze_price_moves({"GLD": prices})["GLD"]

    assert signal.sma_50 is not None
    assert signal.sma_200 is not None
    assert signal.distance_to_50d is not None
    assert signal.distance_to_200d is not None
    assert signal.drawdown_from_high == 0
    assert signal.atr_20 is not None
    assert signal.atr_multiple is not None
    assert signal.return_zscore_60d is not None
    assert signal.historical_percentile is not None
    assert "z-score" in signal.reason
    assert "ATR" in signal.reason
    assert "percentile" in signal.reason
