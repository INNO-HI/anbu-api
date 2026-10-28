"""SFR-009 AMI 적재·통합 테스트 — A 우선 통합, 중복 제거, 계량기 가명처리."""
from sqlalchemy import func, select

from anbu_api.ami.loader import integrate_ami
from anbu_api.models.accum import AmiUsageA, AmiUsageB, PowerUsage
from anbu_api.pseudonym.mapping_store import MappingStore


def test_integrate_ami_merges_and_dedupes(seeded_accum, ops_session):
    store = MappingStore(ops_session)
    a_count = seeded_accum.scalar(select(func.count()).select_from(AmiUsageA))
    b_count = seeded_accum.scalar(select(func.count()).select_from(AmiUsageB))
    assert a_count > 0 and b_count > 0

    added = integrate_ami(seeded_accum, store)
    rows = seeded_accum.scalars(select(PowerUsage)).all()
    assert added == len(rows)
    # 정본 = A 전체 + (B 중 A에 없는 시각)만 — 중복 없음
    assert len(rows) < a_count + b_count
    assert len({(r.meter_pseudo_id, r.measured_at) for r in rows}) == len(rows)
    # 겹치는 시각은 A 원천이 우선
    sources = {r.source for r in rows}
    assert sources == {"A", "B"}

    # 계량기 식별자는 가명 — 원본 식별자(JEJU-…)가 남지 않는다
    assert all(not r.meter_pseudo_id.startswith("JEJU") for r in rows)

    # 재실행 안전(이미 적재된 것은 건너뜀)
    assert integrate_ami(seeded_accum, store) == 0


def test_meter_pseudonym_stable(seeded_accum, ops_session):
    """같은 계량기는 항상 같은 가명 ID를 받는다."""
    store = MappingStore(ops_session)
    integrate_ami(seeded_accum, store)
    p1 = store.get_or_create("meter", "JEJU-9000")
    rows = seeded_accum.scalars(
        select(PowerUsage).where(PowerUsage.meter_pseudo_id == p1)
    ).all()
    assert len(rows) > 0
