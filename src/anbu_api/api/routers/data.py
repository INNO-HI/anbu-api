"""대상자 조회 API — 화면 마스킹 적용(SFR-007). 자유기술은 응답에 포함하지 않는다."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anbu_api.api import deps
from anbu_api.api.auth import require_role
from anbu_api.api.masking import mask_subject
from anbu_api.models.accum import Alert, CareRecord, Device, Subject
from anbu_api.timeutil import iso_kst

router = APIRouter(
    prefix="/api/data",
    tags=["data"],
    dependencies=[Depends(require_role("viewer"))],
)


@router.get("/subjects")
def list_subjects(accum: Session = Depends(deps.accum_db)) -> list[dict]:
    subjects = accum.scalars(select(Subject).order_by(Subject.subject_id)).all()
    device_counts = dict(
        accum.execute(select(Device.subject_id, func.count()).group_by(Device.subject_id)).all()
    )
    return [
        {**mask_subject(s), "device_count": int(device_counts.get(s.subject_id, 0))}
        for s in subjects
    ]


@router.get("/subjects/{subject_id}")
def subject_detail(subject_id: int, accum: Session = Depends(deps.accum_db)) -> dict:
    subj = accum.get(Subject, subject_id)
    if subj is None:
        raise HTTPException(status_code=404, detail="대상자를 찾을 수 없습니다")
    devices = accum.scalars(select(Device).where(Device.subject_id == subject_id)).all()
    alerts = accum.scalars(
        select(Alert)
        .where(Alert.subject_id == subject_id)
        .order_by(Alert.triggered_at.desc())
        .limit(5)
    ).all()
    care_count = accum.scalar(
        select(func.count()).select_from(CareRecord).where(CareRecord.subject_id == subject_id)
    )
    return {
        **mask_subject(subj),
        "devices": [
            {"device_id": d.device_id, "room": d.room, "status": d.current_status}
            for d in devices
        ],
        "recent_alerts": [
            {
                "alert_type": a.alert_type,
                "triggered_at": iso_kst(a.triggered_at),
                "resolved_at": iso_kst(a.resolved_at),
            }
            for a in alerts
        ],
        "care_record_count": int(care_count or 0),
    }
