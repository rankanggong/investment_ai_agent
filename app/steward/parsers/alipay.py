import csv
from io import StringIO

from app.steward.models import CashTransaction, ParseResult
from app.steward.parsers.common import parse_datetime_date, parse_decimal


def parse_alipay_csv_text(text: str) -> ParseResult:
    header_index = _find_header_index(text)
    if header_index is None:
        return ParseResult(
            institution="alipay",
            source_type="csv",
            transactions=[],
            warnings=["No Alipay CSV header row parsed."],
        )

    csv_text = "\n".join(text.splitlines()[header_index:])
    reader = csv.DictReader(StringIO(csv_text))
    transactions: list[CashTransaction] = []
    warnings: list[str] = []

    for row_number, row in enumerate(reader, start=2):
        if not row or not any((value or "").strip() for value in row.values()):
            continue
        try:
            transaction_date, transaction_time = parse_datetime_date(
                _first_present(row, ["交易创建时间", "付款时间", "交易时间"])
            )
            amount = parse_decimal(_first_present(row, ["金额（元）", "金额", "交易金额"]))
            direction = _first_present(row, ["收/支", "收支"], default="")
            if direction == "支出" and amount > 0:
                amount = -amount
            counterparty = _first_present(row, ["交易对方", "对方"], default="")
            item = _first_present(row, ["商品名称", "商品", "备注"], default="")
            summary = " - ".join(part for part in [counterparty, item] if part)
            transactions.append(
                CashTransaction(
                    institution="alipay",
                    account_label="alipay",
                    transaction_date=transaction_date,
                    transaction_time=transaction_time,
                    currency="CNY",
                    amount=amount,
                    balance=None,
                    summary=summary or _first_present(row, ["类型"], default="支付宝交易"),
                    channel=_first_present(row, ["交易状态"], default=None),
                    raw_text=",".join(value or "" for value in row.values()),
                )
            )
        except (KeyError, ValueError) as exc:
            warnings.append(f"Skipped Alipay row {row_number}: {exc}")

    if not transactions and not warnings:
        warnings.append("No Alipay transaction rows parsed.")
    return ParseResult(
        institution="alipay",
        source_type="csv",
        transactions=transactions,
        warnings=warnings,
    )


def _find_header_index(text: str) -> int | None:
    for index, line in enumerate(text.splitlines()):
        if "金额" in line and ("收/支" in line or "收支" in line):
            return index
    return None


def _first_present(
    row: dict[str, str | None],
    names: list[str],
    default: str | None = None,
) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and value.strip():
            return value.strip()
    if default is not None:
        return default
    raise KeyError(f"missing columns: {', '.join(names)}")
