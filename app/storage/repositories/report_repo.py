import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.storage.db import connect
from app.models.analysis import (
    DecisionContext,
    DecisionHistoryRecord,
    StrategyDecisionState,
)


class ReportRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def insert_report(self, report_type: str, report_date: date, title: str, content: str) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO reports (report_type, report_date, title, content_markdown)
                VALUES (?, ?, ?, ?)
                """,
                (report_type, report_date.isoformat(), title, content),
            )

    def get_latest_content(self, report_type: str) -> str | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT content_markdown
                FROM reports
                WHERE report_type = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (report_type,),
            ).fetchone()
        return None if row is None else str(row["content_markdown"])

    def get_previous_content(
        self,
        report_type: str,
        before_date: date,
    ) -> str | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT content_markdown
                FROM reports
                WHERE report_type = ? AND report_date < ?
                ORDER BY report_date DESC, id DESC
                LIMIT 1
                """,
                (report_type, before_date.isoformat()),
            ).fetchone()
        return None if row is None else str(row["content_markdown"])

    def upsert_decision_state(
        self,
        report_date: date,
        decision: StrategyDecisionState,
        context: DecisionContext | None = None,
    ) -> None:
        readiness = decision.action_readiness
        execution = decision.execution_readiness
        rule_states = {
            result.rule_id: result.status
            for result in decision.rules
            if result.rule_id
        }
        with connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decision_states
                  (
                    report_date, readiness_status, candidate_action, symbol,
                    rule_id, rule_states_json, reasons_json,
                    execution_status, permission_status, proposed_amount,
                    proposed_currency, execution_reasons_json,
                    evidence_refs_json, context_json
                  )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_date) DO UPDATE SET
                  readiness_status = excluded.readiness_status,
                  candidate_action = excluded.candidate_action,
                  symbol = excluded.symbol,
                  rule_id = excluded.rule_id,
                  rule_states_json = excluded.rule_states_json,
                  reasons_json = excluded.reasons_json,
                  execution_status = excluded.execution_status,
                  permission_status = excluded.permission_status,
                  proposed_amount = excluded.proposed_amount,
                  proposed_currency = excluded.proposed_currency,
                  execution_reasons_json = excluded.execution_reasons_json,
                  evidence_refs_json = excluded.evidence_refs_json,
                  context_json = excluded.context_json,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (
                    report_date.isoformat(),
                    readiness.status,
                    readiness.candidate_action,
                    readiness.symbol,
                    readiness.rule_id,
                    json.dumps(rule_states, sort_keys=True),
                    json.dumps(readiness.reasons, ensure_ascii=False),
                    execution.status,
                    execution.permission_status,
                    execution.proposed_amount,
                    execution.currency,
                    json.dumps(execution.reasons, ensure_ascii=False),
                    json.dumps(
                        context.evidence_refs if context else readiness.evidence_refs,
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        asdict(context) if context else {},
                        ensure_ascii=False,
                        sort_keys=True,
                        default=_json_default,
                    ),
                ),
            )

    def get_previous_decision_state(
        self,
        before_date: date,
    ) -> DecisionHistoryRecord | None:
        with connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM decision_states
                WHERE report_date < ?
                ORDER BY report_date DESC, id DESC
                LIMIT 1
                """,
                (before_date.isoformat(),),
            ).fetchone()
        return None if row is None else _decision_record(row)

    def list_decision_states(self) -> list[DecisionHistoryRecord]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM decision_states
                ORDER BY report_date, id
                """
            ).fetchall()
        return [_decision_record(row) for row in rows]


def _decision_record(row) -> DecisionHistoryRecord:
    return DecisionHistoryRecord(
        report_date=date.fromisoformat(row["report_date"]),
        readiness_status=row["readiness_status"],
        candidate_action=row["candidate_action"],
        symbol=row["symbol"],
        rule_id=row["rule_id"],
        rule_states=dict(json.loads(row["rule_states_json"])),
        reasons=tuple(json.loads(row["reasons_json"])),
        execution_status=row["execution_status"],
        permission_status=row["permission_status"],
        proposed_amount=row["proposed_amount"],
        proposed_currency=row["proposed_currency"],
        execution_reasons=tuple(json.loads(row["execution_reasons_json"])),
        evidence_refs=tuple(json.loads(row["evidence_refs_json"])),
        context=dict(json.loads(row["context_json"])),
    )


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported journal value: {type(value).__name__}")
