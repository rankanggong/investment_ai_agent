from app.models.analysis import DataCoverage, DataCoverageRow
from app.models.price import PriceBar

MACRO_MIN_ROWS = 6
COMPANY_BOUNDS_MIN_ROWS = 20


def analyze_data_coverage(
    price_history: dict[str, list[PriceBar]],
    price_symbols: list[str],
    macro_symbols: list[str],
    popular_company_symbols: list[str],
    news_item_count: int,
) -> DataCoverage:
    rows: list[DataCoverageRow] = []
    rows.extend(
        _price_row("Prices", symbol, price_history, min_rows=1)
        for symbol in price_symbols
    )
    rows.extend(
        _price_row(
            "Macro",
            symbol,
            price_history,
            min_rows=MACRO_MIN_ROWS,
            detail=f"Needs at least {MACRO_MIN_ROWS} price rows for 5D macro context.",
        )
        for symbol in macro_symbols
    )
    rows.extend(
        _price_row(
            "Section 9",
            symbol,
            price_history,
            min_rows=COMPANY_BOUNDS_MIN_ROWS,
            detail=(
                f"Needs at least {COMPANY_BOUNDS_MIN_ROWS} price rows for popular "
                "company price bounds."
            ),
        )
        for symbol in popular_company_symbols
    )
    rows.append(_news_row(news_item_count))

    impacts = _impacts(rows)
    return DataCoverage(rows=rows, impacts=impacts)


def _price_row(
    category: str,
    symbol: str,
    price_history: dict[str, list[PriceBar]],
    min_rows: int,
    detail: str | None = None,
) -> DataCoverageRow:
    normalized_symbol = symbol.upper()
    bars = sorted(
        price_history.get(normalized_symbol, []),
        key=lambda bar: bar.date,
    )
    row_count = len(bars)
    status = _status(row_count, min_rows)
    latest = bars[-1].date.isoformat() if bars else "N/A"
    if detail is None:
        detail = "Price history available." if row_count else "No price history available."

    return DataCoverageRow(
        category=category,
        item=normalized_symbol,
        status=status,
        rows=row_count,
        latest=latest,
        detail=detail,
    )


def _news_row(news_item_count: int) -> DataCoverageRow:
    return DataCoverageRow(
        category="News",
        item="stored news",
        status="available" if news_item_count > 0 else "missing",
        rows=news_item_count,
        latest="N/A",
        detail=(
            "Stored news rows available for clustering and event detection."
            if news_item_count > 0
            else "No stored news rows available for clustering or event detection."
        ),
    )


def _status(row_count: int, min_rows: int) -> str:
    if row_count == 0:
        return "missing"
    if row_count < min_rows:
        return "insufficient"
    return "available"


def _impacts(rows: list[DataCoverageRow]) -> list[str]:
    impacts: list[str] = []

    macro_gaps = [
        row.item
        for row in rows
        if row.category == "Macro" and row.status != "available"
    ]
    if macro_gaps:
        impacts.append(
            "Section 4 may be unknown because "
            f"{_join_items(macro_gaps)} need at least {MACRO_MIN_ROWS} price rows."
        )

    news_row = next(row for row in rows if row.category == "News")
    if news_row.status != "available":
        impacts.append("Sections 5-6 may be empty because no stored news items were found.")

    company_gaps = [
        row.item
        for row in rows
        if row.category == "Section 9" and row.status != "available"
    ]
    if company_gaps:
        impacts.append(
            "Section 9 may omit "
            f"{_join_items(company_gaps)} because fewer than "
            f"{COMPANY_BOUNDS_MIN_ROWS} price rows are available."
        )

    if not impacts:
        impacts.append("No data coverage gaps detected for configured diagnostics.")

    return impacts


def _join_items(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"
