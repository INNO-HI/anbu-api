"""가명처리 파이프라인(SFR-004): 누적 DB → 전송용 DB 전량 재구축.

- 전송용 테이블을 비우고 가명처리본을 재적재한다(스냅샷 방식).
  가명 ID는 매핑 저장소가 안정적으로 유지하므로 재실행해도 ID가 바뀌지 않는다.
- 전력(power) 테이블은 SFR-009 수행(정본 존재) 시에만 적재한다.
- 처리 결과는 EtlRun(job='pseudonymize')으로 기록하고, 발주기관 적정성 검토용
  처리 기록 문서를 write_processing_record()로 출력할 수 있다.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from anbu_api.models.accum import (
    Alert,
    CareRecord,
    Device,
    DeviceStatusHistory,
    LightingInterval,
    PowerUsage,
    Subject,
)
from anbu_api.models.transfer import TRANSFER_TABLES
from anbu_api.opslog import record_run
from anbu_api.pseudonym import engine as eng
from anbu_api.pseudonym.mapping_store import MappingStore
from anbu_api.timeutil import iso_kst, now_kst


def run_full(
    accum_session: Session,
    transfer_session: Session,
    ops_session: Session,
    *,
    include_power: bool | None = None,
    memo_pseudonymizer: eng.MemoPseudonymizer | None = None,
    as_of: date | None = None,
    store: MappingStore | None = None,
) -> dict:
    """전송용 DB를 가명처리본으로 재구축하고 테이블별 적재 건수를 반환한다."""
    started = now_kst()
    as_of = as_of or started.date()
    store = store or MappingStore(ops_session)

    # 전송용 테이블 초기화(새 키 부여를 위해 전량 재적재)
    for model in TRANSFER_TABLES.values():
        transfer_session.execute(delete(model))

    counts: dict[str, int] = {}

    rows = accum_session.scalars(select(Subject)).all()
    for s in rows:
        transfer_session.add(eng.subject_to_transfer(s, store, as_of=as_of))
    counts["subjects"] = len(rows)

    rows = accum_session.scalars(select(Device)).all()
    for d in rows:
        transfer_session.add(eng.device_to_transfer(d, store))
    counts["devices"] = len(rows)

    rows = accum_session.scalars(select(LightingInterval)).all()
    for iv in rows:
        transfer_session.add(eng.interval_to_transfer(iv, store))
    counts["lighting_intervals"] = len(rows)

    rows = accum_session.scalars(select(DeviceStatusHistory)).all()
    for h in rows:
        transfer_session.add(eng.status_to_transfer(h, store))
    counts["device_status_history"] = len(rows)

    rows = accum_session.scalars(select(CareRecord)).all()
    for c in rows:
        transfer_session.add(
            eng.care_to_transfer(c, store, memo_pseudonymizer=memo_pseudonymizer)
        )
    counts["care_records"] = len(rows)

    rows = accum_session.scalars(select(Alert)).all()
    for a in rows:
        transfer_session.add(eng.alert_to_transfer(a, store))
    counts["alerts"] = len(rows)

    power_rows = accum_session.scalars(select(PowerUsage)).all()
    if include_power is None:
        include_power = bool(power_rows)  # SFR-009 수행 여부 자동 감지
    if include_power:
        for p in power_rows:
            transfer_session.add(eng.power_to_transfer(p, store))
        counts["power_usage"] = len(power_rows)
    else:
        counts["power_usage"] = 0

    transfer_session.commit()
    record_run(
        ops_session,
        "pseudonymize",
        row_count=sum(counts.values()),
        detail=json.dumps(counts, ensure_ascii=False),
        started_at=started,
    )
    ops_session.commit()
    return counts


def write_processing_record(counts: dict, out_path: str) -> str:
    """가명처리 결과·처리 기록(발주기관 적정성 검토 자료) 문서를 생성한다."""
    lines = [
        "# 가명처리 결과 및 처리 기록",
        "",
        f"- 처리 일시: {iso_kst(now_kst())} (KST)",
        "- 처리 기준: docs/가명처리기준서.md (발주기관 서면 합의본)",
        "- 처리 방식: 무작위 토큰 치환 + 암호화 매핑 분리 보관(단순 해시 미사용)",
        "",
        "## 테이블별 적재 건수",
        "",
        "| 전송용 테이블 | 건수 |",
        "|---|---|",
    ]
    for table, n in counts.items():
        lines.append(f"| {table} | {n} |")
    lines += [
        "",
        "## 안전조치",
        "- 직접식별자(이름·연락처·주소·보호자·담당자): 전송 스키마에 미포함(구조적 차단)",
        "- 매핑 테이블: Fernet 암호화, 운영 DB 분리 보관, 발주기관 전용 권한(super_admin)",
        "- 자유기술 항목: 기본 전송 제외(SFR-010 채택 시 정밀 가명처리·추가검수 후 전송)",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
