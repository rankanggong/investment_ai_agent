from pathlib import Path

from app.config import load_watchlist


def test_load_watchlist_expands_grouped_assets():
    watchlist = load_watchlist(Path("config/watchlist.yaml"))

    symbols = [asset.symbol for asset in watchlist.assets]

    assert "SPY" in symbols
    assert "QQQ" in symbols
    assert "XLK" in symbols
    assert watchlist.asset_by_symbol("SPY").role == "us_equity_core"
    assert watchlist.asset_by_symbol("XLK").role == "sector"

