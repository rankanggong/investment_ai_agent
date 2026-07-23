from datetime import date, timedelta

from app.analyzers.data_coverage_analyzer import analyze_data_coverage
from app.models.price import PriceBar


def bar(day: int, symbol: str) -> PriceBar:
    return PriceBar(
        symbol=symbol,
        date=date(2026, 1, 1) + timedelta(days=day),
        open=100,
        high=100,
        low=100,
        close=100,
        adjusted_close=100,
        volume=1000,
        source="test",
    )


def history(symbol: str, rows: int) -> list[PriceBar]:
    return [bar(day, symbol) for day in range(rows)]


def test_data_coverage_classifies_prices_macro_and_company_bounds():
    result = analyze_data_coverage(
        price_history={
            "SPY": history("SPY", 8),
            "TLT": history("TLT", 5),
            "AAPL": history("AAPL", 12),
        },
        price_symbols=["SPY", "QQQ"],
        macro_symbols=["SPY", "TLT", "UUP"],
        popular_company_symbols=["AAPL", "MSFT"],
    )

    assert result.rows[0].category == "Prices"
    assert result.rows[0].item == "SPY"
    assert result.rows[0].status == "available"
    assert result.rows[0].rows == 8
    assert result.rows[0].latest == "2026-01-08"

    assert _row(result, "Prices", "QQQ").status == "missing"
    assert _row(result, "Macro", "TLT").status == "insufficient"
    assert _row(result, "Macro", "TLT").detail == (
        "Needs at least 6 price rows for 5D macro context."
    )
    assert _row(result, "Macro", "UUP").status == "missing"
    assert _row(result, "Company bounds", "AAPL").status == "insufficient"
    assert _row(result, "Company bounds", "MSFT").status == "missing"
    assert all(row.category != "News" for row in result.rows)

    assert "Section 4 may be unknown because TLT and UUP need at least 6 price rows." in result.impacts
    assert (
        "Company bounds may omit AAPL and MSFT because fewer than 20 price rows are available."
        in result.impacts
    )


def test_data_coverage_reports_no_impacts_when_inputs_are_sufficient():
    result = analyze_data_coverage(
        price_history={
            "SPY": history("SPY", 25),
            "TLT": history("TLT", 6),
            "AAPL": history("AAPL", 20),
        },
        price_symbols=["SPY"],
        macro_symbols=["SPY", "TLT"],
        popular_company_symbols=["AAPL"],
    )

    assert all(row.status == "available" for row in result.rows)
    assert result.impacts == ["No data coverage gaps detected for configured diagnostics."]


def test_missing_usd_cnh_is_degraded_and_is_reported_as_a_gap():
    result = analyze_data_coverage(
        price_history={"SPY": history("SPY", 25)},
        price_symbols=["SPY", "USD/CNH"],
        macro_symbols=["SPY"],
        popular_company_symbols=[],
    )

    assert _row(result, "Prices", "USD/CNH").status == "degraded"
    assert result.status == "degraded"
    assert any("USD/CNH" in impact for impact in result.impacts)
    assert all("No data coverage gaps" not in impact for impact in result.impacts)


def _row(result, category: str, item: str):
    return next(row for row in result.rows if row.category == category and row.item == item)
