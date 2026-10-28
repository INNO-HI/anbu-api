"""장비 상태 변경 이력 적재(SFR-002).

원시스템에는 장비 상태의 '현재값'만 남아 무활동과 장비 중단을 사후에 구분할 수
없다. 이 모듈은 ① 현재값 변경을 이력으로 누적(sync)하고 ② 장기 무신호 장비를
'비활성'으로 추론(infer)해 이력에 남긴다. 이력이 쌓이면 임의 시점에 대해
"로그 없음 = 대상자 무활동"인지 "장비 중단 구간"인지 구분할 수 있다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.accum import Device, DeviceStatusHistory, LedRawLog
from anbu_api.timeutil import now_kst


def _latest_status(session: Session, device_id: int) -> str | None:
    row = session.scalars(
        select(DeviceStatusHistory)
        .where(DeviceStatusHistory.device_id == device_id)
        .order_by(DeviceStatusHistory.changed_at.desc(), DeviceStatusHistory.id.desc())
        .limit(1)
    ).first()
    return row.status if row else None


def sync_status(session: Session, *, as_of: datetime | None = None) -> int:
    """devices.current_status와 최신 이력을 비교해 변경분을 이력으로 적재한다(commit 포함)."""
    as_of = as_of or now_kst()
    appended = 0
    for dev in session.scalars(select(Device)).all():
        latest = _latest_status(session, dev.device_id)
        if latest != dev.current_status:
            session.add(DeviceStatusHistory(
                device_id=dev.device_id,
                status=dev.current_status,
                changed_at=as_of,
                source="sync",
                note=f"원시스템 현재값 동기화(이전: {latest or '없음'})",
            ))
            appended += 1
    session.commit()
    return appended


def infer_inactivity(
    session: Session,
    *,
    inactive_after_hours: int | None = None,
    as_of: datetime | None = None,
) -> int:
    """무신호 장비 추론: 기준 시간 동안 원시 로그가 없는 정상 장비를 '비활성'으로 전환.

    current_status 갱신 + 이력(source='auto') 추가. commit 포함.
    """
    hours = inactive_after_hours or settings.inactive_after_hours
    as_of = as_of or now_kst()
    cutoff = as_of - timedelta(hours=hours)
    changed = 0
    for dev in session.scalars(select(Device).where(Device.current_status == "normal")).all():
        last_log = session.scalar(
            select(func.max(LedRawLog.logged_at)).where(LedRawLog.device_id == dev.device_id)
        )
        if last_log is None or last_log < cutoff:
            dev.current_status = "inactive"
            session.add(DeviceStatusHistory(
                device_id=dev.device_id,
                status="inactive",
                changed_at=as_of,
                source="auto",
                note=f"무신호 {hours}시간 이상(마지막 로그: {last_log or '없음'})",
            ))
            changed += 1
    session.commit()
    return changed
