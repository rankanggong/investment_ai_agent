from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256
from pathlib import Path

from app.steward.analyzer import analyze_cash_state
from app.steward.markdown_writer import render_steward_report
from app.steward.parsers.registry import parse_statement_file
from app.steward.reconciliation import reconcile_transfers
from app.steward.storage import StewardRepository, initialize_steward_database


@dataclass(frozen=True)
class StewardImportSummary:
    documents_seen: int
    parsed_documents: int
    imported_transactions: int
    warnings: list[str] = field(default_factory=list)


def import_steward_inbox(db_path: Path, inbox_path: Path) -> StewardImportSummary:
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)
    documents_seen = 0
    parsed_documents = 0
    imported_transactions = 0
    warnings: list[str] = []

    for path in _iter_statement_files(inbox_path):
        documents_seen += 1
        source_hash = _hash_file(path)
        try:
            result = parse_statement_file(path)
            parsed_documents += 1 if result.institution != "unknown" else 0
            document_warnings = result.warnings
            repo.record_source_document(
                path=str(path),
                source_hash=source_hash,
                institution=result.institution,
                source_type=result.source_type,
                status="imported" if result.transactions else "warning",
                warnings=document_warnings,
            )
            imported_transactions += repo.upsert_cash_transactions(
                source_hash,
                result.transactions,
            )
            warnings.extend(f"{path.name}: {warning}" for warning in document_warnings)
        except RuntimeError as exc:
            repo.record_source_document(
                path=str(path),
                source_hash=source_hash,
                institution="unknown",
                source_type=path.suffix.lower().lstrip(".") or "file",
                status="error",
                warnings=[str(exc)],
            )
            warnings.append(f"{path.name}: {exc}")

    return StewardImportSummary(
        documents_seen=documents_seen,
        parsed_documents=parsed_documents,
        imported_transactions=imported_transactions,
        warnings=warnings,
    )


def generate_steward_report(
    db_path: Path,
    report_dir: Path,
    report_date: date | None = None,
) -> Path:
    initialize_steward_database(db_path)
    repo = StewardRepository(db_path)
    effective_date = report_date or date.today()
    transactions = repo.list_cash_transactions()
    reconciliation = reconcile_transfers(
        transactions,
        repo.list_account_profiles(),
        repo.list_transfer_decisions(),
    )
    cash_state = analyze_cash_state(transactions, reconciliation)
    content = render_steward_report(
        report_date=effective_date,
        cash_state=cash_state,
        document_count=repo.count_source_documents(),
        holdings=repo.list_holdings(),
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"portfolio-steward-report-{effective_date.isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    repo.insert_report(
        report_date=effective_date,
        title=f"Portfolio Steward Report - {effective_date.isoformat()}",
        content=content,
    )
    return path


def _iter_statement_files(inbox_path: Path) -> list[Path]:
    if not inbox_path.exists():
        return []
    return sorted(
        path
        for path in inbox_path.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".pdf"}
    )


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
