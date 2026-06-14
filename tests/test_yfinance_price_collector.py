from datetime import date, datetime
import sys
from types import SimpleNamespace

from app.collectors.yfinance_price_collector import _load_history, collect_yfinance_prices


class FakeHistory:
    def __init__(self, rows):
        self.rows = rows
        self.empty = not rows

    def iterrows(self):
        return iter(self.rows)


def test_collect_yfinance_prices_normalizes_history_rows():
    calls = []

    def load_history(symbol, period):
        calls.append((symbol, period))
        return FakeHistory(
            [
                (
                    datetime(2026, 6, 9),
                    {
                        "Open": 100.0,
                        "High": 102.0,
                        "Low": 99.0,
                        "Close": 101.0,
                        "Adj Close": 0.0,
                        "Volume": 1200,
                    },
                )
            ]
        )

    result = collect_yfinance_prices(["spy"], history_loader=load_history)

    assert calls == [("SPY", "6mo")]
    assert result.failed_symbols == []
    assert len(result.bars) == 1
    assert result.bars[0].symbol == "SPY"
    assert result.bars[0].date == date(2026, 6, 9)
    assert result.bars[0].adjusted_close == 0.0
    assert result.bars[0].source == "yfinance"


def test_collect_yfinance_prices_continues_after_empty_result_or_exception():
    def load_history(symbol, period):
        if symbol == "BAD":
            raise RuntimeError("download failed")
        if symbol == "EMPTY":
            return FakeHistory([])
        return FakeHistory(
            [
                (
                    date(2026, 6, 9),
                    {
                        "Open": 10.0,
                        "High": 12.0,
                        "Low": 9.0,
                        "Close": 11.0,
                        "Volume": 100,
                    },
                )
            ]
        )

    result = collect_yfinance_prices(
        ["GOOD", "BAD", "EMPTY"], history_loader=load_history
    )

    assert [bar.symbol for bar in result.bars] == ["GOOD"]
    assert result.failed_symbols == ["BAD", "EMPTY"]
    assert result.failure_reasons == {
        "BAD": "RuntimeError: download failed",
        "EMPTY": "No price data returned",
    }


def test_load_history_enables_retries_and_uses_longer_history_timeout(monkeypatch):
    history_calls = []
    fake_yfinance = SimpleNamespace(
        config=SimpleNamespace(network=SimpleNamespace(retries=0)),
        Ticker=lambda symbol: SimpleNamespace(
            history=lambda **kwargs: history_calls.append((symbol, kwargs))
        ),
    )
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    _load_history("SPY", "6mo")

    assert fake_yfinance.config.network.retries == 2
    assert history_calls == [
        (
            "SPY",
            {
                "period": "6mo",
                "interval": "1d",
                "auto_adjust": False,
                "timeout": 30,
            },
        )
    ]


def test_collect_yfinance_prices_stops_after_rate_limit():
    calls = []

    class YFRateLimitError(Exception):
        pass

    def load_history(symbol, period):
        calls.append(symbol)
        raise YFRateLimitError("Too Many Requests")

    result = collect_yfinance_prices(["SPY", "QQQ", "GLD"], history_loader=load_history)

    assert calls == ["SPY"]
    assert result.failed_symbols == ["SPY", "QQQ", "GLD"]
    assert result.failure_reasons == {
        "SPY": "YFRateLimitError: Too Many Requests",
        "QQQ": "Skipped because Yahoo rate limit was reached",
        "GLD": "Skipped because Yahoo rate limit was reached",
    }
