from statistics import pstdev

from app.models.analysis import CompanyPriceBound, CompanyPriceBounds
from app.models.price import PriceBar

MIN_HISTORY_ROWS = 20
MAX_LOOKBACK_ROWS = 60


def analyze_company_price_bounds(
    price_history: dict[str, list[PriceBar]],
    symbols: list[str],
) -> CompanyPriceBounds:
    bounds: list[CompanyPriceBound] = []
    notes: list[str] = []

    for symbol in symbols:
        normalized_symbol = symbol.upper()
        bars = sorted(
            price_history.get(normalized_symbol, []),
            key=lambda bar: bar.date,
        )
        if not bars:
            notes.append(f"{normalized_symbol} skipped: no price history available.")
            continue
        if len(bars) < MIN_HISTORY_ROWS:
            notes.append(
                f"{normalized_symbol} skipped: needs at least {MIN_HISTORY_ROWS} "
                f"price rows, found {len(bars)}."
            )
            continue

        bounds.append(_bound_for_symbol(normalized_symbol, bars[-MAX_LOOKBACK_ROWS:]))

    return CompanyPriceBounds(bounds=bounds, notes=notes)


def _bound_for_symbol(symbol: str, bars: list[PriceBar]) -> CompanyPriceBound:
    closes = [bar.close for bar in bars]
    latest = closes[-1]
    recent_low = min(closes)
    recent_high = max(closes)
    volatility = pstdev(closes) if len(closes) > 1 else 0.0
    volatility_lower = latest - volatility
    volatility_upper = latest + volatility
    lower_bound = min(recent_low, volatility_lower)
    upper_bound = max(recent_high, volatility_upper)
    basis = f"{len(closes)}D range + volatility band"

    return CompanyPriceBound(
        symbol=symbol,
        latest=latest,
        lower_review_bound=lower_bound,
        upper_review_bound=upper_bound,
        basis=basis,
        calculation_completeness=round(
            min(1.0, len(closes) / MAX_LOOKBACK_ROWS), 2
        ),
        notes=[
            (
                f"Recent range {recent_low:.2f}-{recent_high:.2f}; "
                f"volatility band {volatility_lower:.2f}-{volatility_upper:.2f}."
            )
        ],
    )
