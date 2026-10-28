"""보존 정책 적용(SFR-002): 보관 기간이 지난 데이터의 파기.

정책(보존정책서 docs/보존정책서.md와 일치해야 한다):
  - LED 원시 로그: retention_raw_log_days(기본 365일) 경과분 파기.
    점등 구간 파생 테이블이 요약을 보존하므로 원시 행은 파기해도 분석이 가능하다.
  - 점등 구간·상태 이력·돌봄 기록·이상 알림: 사업·연구 목적 범위 내 장기 보존.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.accum import LedRawLog
from anbu_api.timeutil import iso_kst, now_kst


def apply_retention(
    session: Session,
    *,
    raw_log_days: int | None = None,
    as_of: datetime | None = None,
) -> dict:
    """보존 기간 경과 원시 로그를 파기하고 결과를 반환한다(commit 포함)."""
    days = raw_log_days or settings.retention_raw_log_days
    as_of = as_of or now_kst()
    cutoff = as_of - timedelta(days=days)

    purge_count = session.scalar(
        select(func.count()).select_from(LedRawLog).where(LedRawLog.logged_at < cutoff)
    ) or 0
    if purge_count:
        session.execute(delete(LedRawLog).where(LedRawLog.logged_at < cutoff))
    session.commit()
    return {"purged_raw_logs": int(purge_count), "cutoff": iso_kst(cutoff), "days": days}
