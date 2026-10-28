"""LED 원시 로그 → 점등 구간 파생 테이블(SFR-002).

원시 로그는 점등 중 약 12초 간격으로 1행씩 기록되고 소등 중에는 기록이 없다.
따라서 연속 로그 사이 공백이 gap_sec 이상이면 소등으로 판정해 구간을 닫는다.

- 증분 처리: 장비별로 기존 구간의 마지막 ended_at 이후 로그만 처리한다(재실행 안전).
- 미완 구간 보호: 장비가 아직 점등 중일 수 있는 마지막 그룹은 as_of 기준으로
  gap_sec 이상 지난 경우에만 확정한다(다음 실행에서 이어서 처리).
- duration_sec = (종료 - 시작) + 12초(행 하나가 약 12초의 점등을 대표).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.accum import LedRawLog, LightingInterval
from anbu_api.timeutil import now_kst

ROW_CADENCE_SEC = 12  # 원시 로그 기록 주기(현행 환경 명세)


def build_intervals(
    session: Session,
    *,
    gap_sec: int | None = None,
    as_of: datetime | None = None,
) -> int:
    """원시 로그를 점등 구간으로 변환해 적재하고 생성 건수를 반환한다(commit 포함)."""
    gap = gap_sec or settings.lighting_gap_threshold_sec
    as_of = as_of or now_kst()
    created = 0

    device_ids = session.scalars(select(LedRawLog.device_id).distinct()).all()
    for device_id in device_ids:
        watermark = session.scalar(
            select(func.max(LightingInterval.ended_at)).where(
                LightingInterval.device_id == device_id
            )
        )
        q = select(LedRawLog.logged_at).where(LedRawLog.device_id == device_id)
        if watermark is not None:
            q = q.where(LedRawLog.logged_at > watermark)
        times = session.scalars(q.order_by(LedRawLog.logged_at)).all()
        if not times:
            continue

        groups: list[tuple[datetime, datetime]] = []
        start = prev = times[0]
        for t in times[1:]:
            if (t - prev).total_seconds() >= gap:
                groups.append((start, prev))
                start = t
            prev = t
        # 마지막 그룹: 점등이 끝났다고 확신할 수 있을 때만 확정
        if (as_of - prev).total_seconds() >= gap:
            groups.append((start, prev))

        for started_at, ended_at in groups:
            session.add(LightingInterval(
                device_id=device_id,
                started_at=started_at,
                ended_at=ended_at,
                duration_sec=int((ended_at - started_at).total_seconds()) + ROW_CADENCE_SEC,
            ))
            created += 1

    session.commit()
    return created
