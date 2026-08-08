from datetime import date, timedelta
from pytest import approx

from app.analyzers.company_price_bounds_analyzer import analyze_company_price_bounds
from app.models.price import PriceBar


def bar(day: int, symbol: str, close: float) -> PriceBar:
    return PriceBar(
        symbol=symbol,
        date=date(2026, 1, 1) + timedelta(days=day),
        open=close,
        high=close,
        low=close,
        close=close,
        adjusted_close=close,
        volume=1000,
        source="test",
    )


def test_company_price_bounds_uses_recent_range_and_volatility_band():
    history = {
        "AAPL": [bar(day, "AAPL", 100 + day) for day in range(60)],
    }

    result = analyze_company_price_bounds(history, ["AAPL"])

    assert len(result.bounds) == 1
    bound = result.bounds[0]
    assert bound.symbol == "AAPL"
    assert bound.latest == 159
    assert bound.lower_review_bound == approx(100.0)
    assert bound.upper_review_bound == approx(176.318102, rel=1e-6)
    assert bound.basis == "60D range + volatility band"
    assert bound.calculation_completeness == 1.0
    assert bound.notes == [
        "Recent range 100.00-159.00; volatility band 141.68-176.32."
    ]
    assert result.notes == []


def test_company_price_bounds_records_note_for_insufficient_history():
    history = {
        "NVDA": [bar(day, "NVDA", 100 + day) for day in range(10)],
    }

    result = analyze_company_price_bounds(history, ["NVDA", "MSFT"])

    assert result.bounds == []
    assert result.notes == [
        "NVDA skipped: needs at least 20 price rows, found 10.",
        "MSFT skipped: no price history available.",
    ]
