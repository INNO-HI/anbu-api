"""화면 마스킹(SFR-007).

운영 화면(모든 역할)에서 직접식별자는 마스킹해 표시한다. 자유기술(notes/memo)은
API 응답에 포함하지 않는다. 원 식별자 확인이 필요한 발주기관 업무는 매핑 재식별
엔드포인트(super_admin 전용, 감사 로그 기록)로만 수행한다.
"""
from __future__ import annotations

import re

from anbu_api.models.accum import Subject
from anbu_api.pseudonym.rules import age_band
from anbu_api.timeutil import now_kst

_PHONE_RE = re.compile(r"^(0\d{1,2})-?(\d{3,4})-?(\d{4})$")


def mask_name(name: str | None) -> str | None:
    if not name:
        return None
    if len(name) == 1:
        return "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    m = _PHONE_RE.match(phone.strip())
    if not m:
        return "***"
    return f"{m.group(1)}-{'*' * len(m.group(2))}-{m.group(3)}"


def mask_address(region_emd: str | None) -> str | None:
    """주소는 읍·면·동까지만 표시한다(상세 주소 비노출)."""
    if not region_emd:
        return None
    return f"{region_emd} (상세 비공개)"


def mask_subject(subj: Subject) -> dict:
    """대상자 1명의 화면 표시용 dict(마스킹 적용, 자유기술 제외)."""
    return {
        "subject_id": subj.subject_id,
        "name": mask_name(subj.name),
        "gender": subj.gender,
        "age_band": age_band(subj.birth_date, as_of=now_kst().date()),
        "region": mask_address(subj.region_emd),
        "phone": mask_phone(subj.phone),
        "guardian_name": mask_name(subj.guardian_name),
        "guardian_phone": mask_phone(subj.guardian_phone),
        "service_start": f"{subj.service_start_date:%Y-%m}" if subj.service_start_date else None,
        "high_risk_yn": subj.high_risk_yn,
    }
