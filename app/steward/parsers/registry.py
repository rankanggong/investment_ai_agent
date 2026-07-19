from pathlib import Path

from app.steward.models import ParseResult
from app.steward.parsers.alipay import parse_alipay_csv_text
from app.steward.parsers.cmb import parse_cmb_statement_text
from app.steward.parsers.icbc import parse_icbc_statement_text


def parse_statement_file(path: Path) -> ParseResult:
    name = path.name.lower()
    if path.suffix.lower() == ".csv":
        text = _read_text_file(path)
        if "支付宝" in path.name or "alipay" in name or "收/支" in text:
            return parse_alipay_csv_text(text)
    if path.suffix.lower() == ".pdf":
        text = _extract_pdf_text(path)
        if "招商银行交易流水" in text or "China Merchants Bank" in text:
            return parse_cmb_statement_text(text)
        if "中国工商银行" in text or "ICBC" in text.upper():
            return parse_icbc_statement_text(text)

    return ParseResult(
        institution="unknown",
        source_type=path.suffix.lower().lstrip(".") or "file",
        transactions=[],
        warnings=[f"No steward parser matched {path.name}."],
    )


def _read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PDF import requires optional dependency 'pypdf'. "
            "Install project dependencies before importing PDF statements."
        ) from exc

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
