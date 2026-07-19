from datetime import date, datetime, time
from decimal import Decimal


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def parse_datetime_date(value: str) -> tuple[date, time | None]:
    stripped = value.strip()
    if not stripped:
        raise ValueError("missing datetime")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(stripped, fmt)
            return parsed.date(), parsed.time()
        except ValueError:
            pass
    return parse_date(stripped[:10]), None


def parse_time(value: str) -> time:
    return datetime.strptime(value.strip(), "%H:%M:%S").time()


def parse_decimal(value: str) -> Decimal:
    cleaned = (
        value.strip()
        .replace(",", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("元", "")
    )
    return Decimal(cleaned)


def normalize_currency(value: str) -> str:
    stripped = value.strip().upper()
    mapping = {
        "人民币": "CNY",
        "RMB": "CNY",
    }
    return mapping.get(stripped, stripped)
