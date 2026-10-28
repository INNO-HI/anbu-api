"""운영 기록 헬퍼 — ETL 실행 기록(EtlRun)과 감사 로그(AuditLog)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from anbu_api.models.ops import AuditLog, EtlRun
from anbu_api.timeutil import now_kst


def record_run(
    ops_session: Session,
    job: str,
    *,
    status: str = "ok",
    row_count: int = 0,
    detail: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> EtlRun:
    """작업 실행 기록을 남긴다. commit은 호출측 책임."""
    run = EtlRun(
        job=job,
        status=status,
        row_count=row_count,
        detail=detail,
        started_at=started_at or now_kst(),
        finished_at=finished_at or now_kst(),
    )
    ops_session.add(run)
    return run


def audit(ops_session: Session, username: str | None, action: str, detail: str = "") -> AuditLog:
    """감사 로그(작업 이력)를 남긴다. commit은 호출측 책임."""
    log = AuditLog(username=username, action=action, detail=detail[:500])
    ops_session.add(log)
    return log
