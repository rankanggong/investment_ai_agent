import re

from app.steward.models import CashTransaction, ParseResult
from app.steward.parsers.common import normalize_currency, parse_date, parse_decimal


_ACCOUNT_RE = re.compile(r"账号[:：]\s*(\S+)")
_ROW_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<currency>[A-Za-z]{3})\s+"
    r"(?P<amount>[+-]?[\d,]+\.\d{2})\s+"
    r"(?P<balance>[+-]?[\d,]+\.\d{2})\s+"
    r"(?P<summary>.+)$"
)


def parse_cmb_statement_text(text: str) -> ParseResult:
    account_label = _extract_account_label(text)
    transactions: list[CashTransaction] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = _ROW_RE.match(line)
        if not match:
            continue
        transactions.append(
            CashTransaction(
                institution="cmb",
                account_label=account_label,
                transaction_date=parse_date(match.group("date")),
                currency=normalize_currency(match.group("currency")),
                amount=parse_decimal(match.group("amount")),
                balance=parse_decimal(match.group("balance")),
                summary=match.group("summary").strip(),
                raw_text=line,
            )
        )

    warnings = [] if transactions else ["No CMB transaction rows parsed."]
    return ParseResult(
        institution="cmb",
        source_type="pdf_text",
        transactions=transactions,
        warnings=warnings,
    )


def _extract_account_label(text: str) -> str:
    match = _ACCOUNT_RE.search(text)
    if match:
        return match.group(1)
    return "cmb_unknown_account"
