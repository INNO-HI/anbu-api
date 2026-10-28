"""전력(AMI) 데이터 적재·통합(SFR-009, 조건부).

발주기관이 원시스템 운영사로부터 데이터 제공을 확보한 경우에만 수행한다.
AMI 2종(ami_usage_a, ami_usage_b)을 정본(power_usage) 하나로 통합한다.
  - 통합 규칙: 동일 (계량기, 측정시각)은 A 원천 우선, B는 A에 없는 시각만 보충.
  - 계량기 식별자는 적재 시점에 가명처리한다(매핑 저장소 namespace='meter').
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.models.accum import AmiUsageA, AmiUsageB, PowerUsage
from anbu_api.pseudonym.mapping_store import MappingStore


def integrate_ami(session: Session, store: MappingStore) -> int:
    """AMI 2종을 정본으로 통합 적재하고 신규 적재 건수를 반환한다(commit 포함).

    store는 운영 DB 세션에 바인딩된 매핑 저장소다(계량기 가명처리용).
    재실행 안전: 이미 정본에 있는 (가명 계량기, 시각)은 건너뛴다.
    """
    existing = {
        (m, t)
        for m, t in session.execute(
            select(PowerUsage.meter_pseudo_id, PowerUsage.measured_at)
        ).all()
    }
    added = 0

    for row in session.scalars(select(AmiUsageA)).all():
        pseudo = store.get_or_create("meter", row.meter_id)
        key = (pseudo, row.measured_at)
        if key in existing:
            continue
        session.add(PowerUsage(
            meter_pseudo_id=pseudo,
            subject_id=row.subject_id,
            measured_at=row.measured_at,
            kwh=row.kwh,
            source="A",
        ))
        existing.add(key)
        added += 1

    for row in session.scalars(select(AmiUsageB)).all():
        pseudo = store.get_or_create("meter", row.meter_no)
        key = (pseudo, row.read_time)
        if key in existing:
            continue
        session.add(PowerUsage(
            meter_pseudo_id=pseudo,
            subject_id=row.subject_id,
            measured_at=row.read_time,
            kwh=row.usage_kwh,
            source="B",
        ))
        existing.add(key)
        added += 1

    session.commit()
    # 매핑 저장소(운영 DB) 쪽도 확정
    store.session.commit()
    return added
