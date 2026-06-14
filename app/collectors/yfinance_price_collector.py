from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
import math
from typing import Any

from app.models.price import PriceBar


HistoryLoader = Callable[[str, str], Any]


@dataclass(frozen=True)
class YFinanceCollectionResult:
    bars: list[PriceBar]
    failed_symbols: list[str]
    failure_reasons: dict[str, str] = field(default_factory=dict)


def collect_yfinance_prices(
    symbols: Iterable[str],
    period: str = "6mo",
    history_loader: HistoryLoader | None = None,
) -> YFinanceCollectionResult:
    loader = history_loader or _load_history
    normalized_symbols = [symbol.upper() for symbol in symbols]
    bars: list[PriceBar] = []
    failed_symbols: list[str] = []
    failure_reasons: dict[str, str] = {}

    for index, symbol in enumerate(normalized_symbols):
        try:
            history = loader(symbol, period)
            if history.empty:
                failed_symbols.append(symbol)
                failure_reasons[symbol] = "No price data returned"
                continue
            symbol_bars = [
                _row_to_bar(symbol, index, row) for index, row in history.iterrows()
            ]
        except Exception as error:
            failed_symbols.append(symbol)
            failure_reasons[symbol] = _describe_error(error)
            if _is_rate_limit_error(error):
                for skipped_symbol in normalized_symbols[index + 1 :]:
                    failed_symbols.append(skipped_symbol)
                    failure_reasons[skipped_symbol] = (
                        "Skipped because Yahoo rate limit was reached"
                    )
                break
            continue
        bars.extend(symbol_bars)

    return YFinanceCollectionResult(
        bars=bars,
        failed_symbols=failed_symbols,
        failure_reasons=failure_reasons,
    )


def _load_history(symbol: str, period: str):
    import yfinance as yf

    yf.config.network.retries = 2
    return yf.Ticker(symbol).history(
        period=period,
        interval="1d",
        auto_adjust=False,
        timeout=30,
    )


def _row_to_bar(symbol: str, index: Any, row: Any) -> PriceBar:
    close = _required_float(row.get("Close"))
    adjusted_close = _optional_float(row.get("Adj Close"))
    return PriceBar(
        symbol=symbol,
        date=_as_date(index),
        open=_optional_float(row.get("Open")),
        high=_optional_float(row.get("High")),
        low=_optional_float(row.get("Low")),
        close=close,
        adjusted_close=close if adjusted_close is None else adjusted_close,
        volume=_optional_float(row.get("Volume")),
        source="yfinance",
    )


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    converted = value.date()
    if not isinstance(converted, date):
        raise ValueError(f"Unsupported history date: {value!r}")
    return converted


def _required_float(value: Any) -> float:
    converted = _optional_float(value)
    if converted is None:
        raise ValueError("History row has no close price")
    return converted


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    converted = float(value)
    if math.isnan(converted):
        return None
    return converted


def _describe_error(error: Exception) -> str:
    detail = str(error).strip()
    error_type = type(error).__name__
    return f"{error_type}: {detail}" if detail else error_type


def _is_rate_limit_error(error: Exception) -> bool:
    return type(error).__name__ == "YFRateLimitError"
