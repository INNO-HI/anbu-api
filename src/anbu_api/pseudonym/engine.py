"""행 단위 가명처리 변환(SFR-004) — 누적 DB 원본 행 → 전송용 DB 행.

각 함수는 rules.py의 기준을 적용해 전송용 모델 인스턴스를 만든다.
직접식별자(이름·연락처·주소·보호자·담당자)는 전송 모델에 컬럼이 없어
구조적으로 전달이 불가능하다.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from anbu_api.models.accum import (
    Alert,
    CareRecord,
    Device,
    DeviceStatusHistory,
    LightingInterval,
    PowerUsage,
    Subject,
)
from anbu_api.models.transfer import (
    TAlert,
    TCareRecord,
    TDevice,
    TDeviceStatusHistory,
    TLightingInterval,
    TPowerUsage,
    TSubject,
)
from anbu_api.pseudonym.mapping_store import MappingStore
from anbu_api.pseudonym.rules import age_band, categorize_level
from anbu_api.timeutil import to_ym

MemoPseudonymizer = Callable[[str], str]


def subject_to_transfer(subj: Subject, store: MappingStore, *, as_of: date) -> TSubject:
    return TSubject(
        pseudo_subject_id=store.get_or_create("subject", subj.subject_id),
        age_band=age_band(subj.birth_date, as_of=as_of),
        gender=subj.gender,
        region_emd=subj.region_emd,                      # 읍·면·동까지만(세부 주소는 비전송)
        service_start_ym=to_ym(subj.service_start_date), # 월 단위 일반화
        service_end_ym=to_ym(subj.service_end_date),
        meal_cat=categorize_level(subj.meal_level),      # 상위 범주화
        cognition_cat=categorize_level(subj.cognition_level),
        communication_cat=categorize_level(subj.communication_level),
        high_risk_yn=subj.high_risk_yn,                  # 예/아니오만(사유 삭제)
        benefit_yn=None,                                 # 수급 구분 삭제(협의 시에만 제공)
    )


def device_to_transfer(dev: Device, store: MappingStore) -> TDevice:
    return TDevice(
        pseudo_device_id=store.get_or_create("device", dev.device_id),
        pseudo_subject_id=store.get_or_create("subject", dev.subject_id),
        room=dev.room,
        device_type=dev.device_type,
    )


def interval_to_transfer(iv: LightingInterval, store: MappingStore) -> TLightingInterval:
    return TLightingInterval(
        pseudo_device_id=store.get_or_create("device", iv.device_id),
        started_at=iv.started_at,
        ended_at=iv.ended_at,
        duration_sec=iv.duration_sec,
    )


def status_to_transfer(h: DeviceStatusHistory, store: MappingStore) -> TDeviceStatusHistory:
    return TDeviceStatusHistory(
        pseudo_device_id=store.get_or_create("device", h.device_id),
        status=h.status,
        changed_at=h.changed_at,
    )


def care_to_transfer(
    c: CareRecord,
    store: MappingStore,
    *,
    memo_pseudonymizer: MemoPseudonymizer | None = None,
) -> TCareRecord:
    """자유기술(memo)은 기본 전송 제외. SFR-010 채택 시에만 정밀 가명처리본을 싣는다."""
    return TCareRecord(
        pseudo_subject_id=store.get_or_create("subject", c.subject_id),
        visit_at=c.visit_at,
        care_type=c.care_type,
        memo_pseudo=(memo_pseudonymizer(c.memo) if memo_pseudonymizer and c.memo else None),
    )


def alert_to_transfer(a: Alert, store: MappingStore) -> TAlert:
    return TAlert(
        pseudo_subject_id=store.get_or_create("subject", a.subject_id),
        pseudo_device_id=(
            store.get_or_create("device", a.device_id) if a.device_id is not None else None
        ),
        alert_type=a.alert_type,
        triggered_at=a.triggered_at,
        resolved_at=a.resolved_at,
    )


def power_to_transfer(p: PowerUsage, store: MappingStore) -> TPowerUsage:
    """계량기 식별자는 SFR-009 적재 시 이미 가명 — 그대로 사용."""
    return TPowerUsage(
        pseudo_meter_id=p.meter_pseudo_id,
        pseudo_subject_id=(
            store.get_or_create("subject", p.subject_id) if p.subject_id is not None else None
        ),
        measured_at=p.measured_at,
        kwh=p.kwh,
    )
