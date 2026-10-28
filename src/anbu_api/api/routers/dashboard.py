"""운영 대시보드 API(SFR-005) — 적재 현황·센서 동작·전송 현황·제공 실적 집계."""
from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anbu_api.api import deps
from anbu_api.api.auth import require_role
from anbu_api.db import BASES
from anbu_api.models.accum import Device, LightingInterval
from anbu_api.models.ops import EtlRun, SubscriptionReceipt, TransferHistory
from anbu_api.timeutil import iso_kst, now_kst

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_role("viewer"))],
)


@router.get("/ingest")
def ingest_status(
    accum: Session = Depends(deps.accum_db),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """적재 현황: 누적 DB 테이블별 행 수 + 최근 작업 실행 기록."""
    tables = {}
    for table in BASES["accum"].metadata.sorted_tables:
        n = accum.execute(select(func.count()).select_from(table)).scalar()
        tables[table.name] = int(n or 0)
    runs = ops.scalars(
        select(EtlRun).order_by(EtlRun.started_at.desc(), EtlRun.id.desc()).limit(10)
    ).all()
    return {
        "tables": tables,
        "recent_runs": [
            {
                "job": r.job,
                "status": r.status,
                "row_count": r.row_count,
                "started_at": iso_kst(r.started_at),
            }
            for r in runs
        ],
    }


@router.get("/sensors")
def sensor_status(accum: Session = Depends(deps.accum_db)) -> dict:
    """센서 동작: 장비 상태 분포, 오늘 점등 구간 수, 마지막 점등."""
    status_rows = accum.execute(
        select(Device.current_status, func.count()).group_by(Device.current_status)
    ).all()
    today_start = datetime.combine(now_kst().date(), time.min)
    intervals_today = accum.scalar(
        select(func.count())
        .select_from(LightingInterval)
        .where(LightingInterval.started_at >= today_start)
    )
    last_interval = accum.scalar(select(func.max(LightingInterval.ended_at)))
    return {
        "device_status": {status: int(n) for status, n in status_rows},
        "intervals_today": int(intervals_today or 0),
        "last_interval_at": iso_kst(last_interval),
    }


@router.get("/transfers")
def transfer_status(ops: Session = Depends(deps.ops_db)) -> dict:
    """전송 현황: 최근 발행 이력 + 테이블별 누적 발행 건수."""
    recent = ops.scalars(
        select(TransferHistory)
        .order_by(TransferHistory.published_at.desc(), TransferHistory.id.desc())
        .limit(10)
    ).all()
    totals = ops.execute(
        select(
            TransferHistory.table_name,
            func.sum(TransferHistory.record_count),
        )
        .where(TransferHistory.status == "ok")
        .group_by(TransferHistory.table_name)
    ).all()
    return {
        "recent": [
            {
                "table": t.table_name,
                "topic": t.topic,
                "record_count": t.record_count,
                "status": t.status,
                "published_at": iso_kst(t.published_at),
            }
            for t in recent
        ],
        "totals": {name: int(n or 0) for name, n in totals},
    }


@router.get("/receipts")
def receipt_summary(ops: Session = Depends(deps.ops_db)) -> dict:
    """데이터 제공 실적(SFR-005): 참여 대학별 구독 수신 집계."""
    rows = ops.execute(
        select(
            SubscriptionReceipt.university,
            func.sum(SubscriptionReceipt.record_count),
            func.count(),
            func.max(SubscriptionReceipt.received_at),
        ).group_by(SubscriptionReceipt.university)
    ).all()
    return {
        "universities": [
            {
                "university": univ,
                "total_records": int(total or 0),
                "receipt_count": int(cnt),
                "last_received_at": iso_kst(last),
            }
            for univ, total, cnt, last in rows
        ]
    }
