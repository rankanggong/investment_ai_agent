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

