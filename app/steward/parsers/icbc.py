import re

from app.steward.models import CashTransaction, ParseResult
from app.steward.parsers.common import (
    normalize_currency,
    parse_date,
    parse_decimal,
    parse_time,
)


_CARD_RE = re.compile(r"卡号\s+(\S+)")
_DETAIL_RE = re.compile(
    r"^(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<account>\S+)\s+"
    r"(?P<storage>\S+)\s+"
    r"(?P<serial>\S+)\s+"
    r"(?P<currency>\S+)\s+"
    r"(?P<cash_or_remit>\S+)\s+"
    r"(?P<summary>\S+)\s+"
    r"(?P<region>\S+)\s+"
    r"(?P<amount>[+-][\d,]+\.\d{2})\s+"
    r"(?P<balance>[+-]?[\d,]+\.\d{2})\s+"
    r"(?P<channel>.+)$"
)


def parse_icbc_statement_text(text: str) -> ParseResult:
    account_label = _extract_account_label(text)
    transactions: list[CashTransaction] = []
    current_date = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", line):
            current_date = parse_date(line)
            continue
        match = _DETAIL_RE.match(line)
        if not match or current_date is None:
            continue
        transactions.append(
            CashTransaction(
                institution="icbc",
                account_label=account_label,
                transaction_date=current_date,
                transaction_time=parse_time(match.group("time")),
                currency=normalize_currency(match.group("currency")),
                amount=parse_decimal(match.group("amount")),
                balance=parse_decimal(match.group("balance")),
                summary=match.group("summary").strip(),
                channel=match.group("channel").strip(),
                raw_text=f"{current_date.isoformat()} {line}",
            )
        )

    warnings = [] if transactions else ["No ICBC transaction rows parsed."]
    return ParseResult(
        institution="icbc",
        source_type="pdf_text",
        transactions=transactions,
        warnings=warnings,
    )


def _extract_account_label(text: str) -> str:
    match = _CARD_RE.search(text)
    if match:
        return match.group(1)
    return "icbc_unknown_account"
