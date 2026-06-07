from app.analyzers.sector_rotation_analyzer import analyze_sector_rotation
from app.models.analysis import PriceSignal


def signal(symbol, r5, r20):
    return PriceSignal(
        symbol=symbol,
        return_1d=0.0,
        return_5d=r5,
        return_20d=r20,
        volume_ratio_20d=None,
        volatility_zscore=None,
        is_unusual_move=False,
        reason="",
    )


def test_sector_rotation_ranks_sectors_against_spy():
    result = analyze_sector_rotation(
        {
            "SPY": signal("SPY", 0.02, 0.03),
            "XLK": signal("XLK", 0.08, 0.10),
            "XLU": signal("XLU", -0.01, -0.02),
        },
        sector_symbols=["XLK", "XLU"],
        benchmark_symbol="SPY",
    )

    assert result.strong_sectors == ["XLK"]
    assert result.weak_sectors == ["XLU"]
    assert result.risk_on_score > 0

