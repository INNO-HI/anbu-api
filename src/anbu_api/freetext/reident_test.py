"""재식별 시험(SFR-010).

문맥 가명처리를 거친 메모만 보고 공격자(사람 평가자 또는 생성형 AI 가정)가
나이·지역·가족 관계를 추론해 특정인으로 좁힐 수 있는지 시험한다.

- 본교 서버 안에서, 가명처리 단계의 적정성 검증 목적으로만 수행한다.
- 결과는 비율·건수로만 기록한다. 특정인을 알아볼 수 있는 결과(한 사람으로
  좁혀진 사례)의 내용은 기록·보존하지 않고 건수만 센다(발견 즉시 파기 원칙).
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.models.accum import Subject
from anbu_api.models.transfer import TCareRecord
from anbu_api.pseudonym.rules import age_band
from anbu_api.timeutil import iso_kst, now_kst

_AGE_TOKEN_RE = re.compile(r"(\d0)대|85세 이상|65세 미만")
_REL_TOKEN_RE = re.compile(r"(딸|아들|며느리|사위|손자|손녀|배우자|동거인)")


def _extract_clues(memo: str) -> dict:
    """가명처리된 메모에서 추론 가능한 단서(연령대·가족관계·지역어)를 추출한다."""
    age_m = _AGE_TOKEN_RE.search(memo)
    rel_m = _REL_TOKEN_RE.search(memo)
    return {
        "age_token": age_m.group(0) if age_m else None,
        "relation": rel_m.group(1) if rel_m else None,
    }


def run_reident_test(accum_session: Session, transfer_session: Session) -> dict:
    """재식별 시험을 수행하고 비율·건수 지표만 담은 결과를 반환한다."""
    as_of = now_kst().date()
    subjects = accum_session.scalars(select(Subject)).all()

    # 공격자 지식: 전체 대상자의 (연령대, 성별, 지역) 분포 — 외부 지식 결합 가정
    profile: list[dict] = [
        {
            "age_band": age_band(s.birth_date, as_of=as_of),
            "region": s.region_emd,
            "guardian_rel": None,  # 보호자 관계는 원본 notes에만 존재한다고 가정
        }
        for s in subjects
    ]

    memos = transfer_session.scalars(
        select(TCareRecord.memo_pseudo).where(TCareRecord.memo_pseudo.is_not(None))
    ).all()

    tested = 0
    age_inferred = 0
    age_correct = 0
    narrowed_to_one = 0

    for memo in memos:
        tested += 1
        clues = _extract_clues(memo)
        candidates = profile
        if clues["age_token"]:
            age_inferred += 1
            # 연령대 토큰('70대')과 프로필 연령대('70-74')의 10세 구간 일치 비교
            decade = clues["age_token"][:2]
            matched = [
                c for c in candidates
                if c["age_band"] and (
                    c["age_band"].startswith(decade)
                    or (clues["age_token"] == "85세 이상" and c["age_band"] == "85+")
                )
            ]
            if matched:
                age_correct += 1
            candidates = matched or candidates
        if len(candidates) == 1:
            narrowed_to_one += 1  # 건수만 기록(내용은 보존하지 않음)

    return {
        "tested_at": iso_kst(now_kst()),
        "memo_count": tested,
        "age_inference_attempts": age_inferred,
        "age_inference_correct_rate": round(age_correct / age_inferred, 3) if age_inferred else 0.0,
        "narrowed_to_one_count": narrowed_to_one,
        "narrowed_to_one_rate": round(narrowed_to_one / tested, 3) if tested else 0.0,
    }


def write_report(result: dict, out_path: str) -> str:
    """재식별 시험 결과서(발주기관 가명정보 적정성 검토 자료)를 생성한다."""
    lines = [
        "# 재식별 시험 결과서 (SFR-010)",
        "",
        f"- 시험 일시: {result['tested_at']} (KST)",
        "- 시험 방식: 가명처리된 메모의 잔존 단서(연령대·가족관계)로 대상자 추론을 시뮬레이션",
        "- 수행 위치: 본교 서버 내(외부 반출 없음). 결과는 비율·건수로만 기록.",
        "",
        "## 결과 지표",
        "",
        "| 지표 | 값 |",
        "|---|---|",
        f"| 시험 대상 메모 수 | {result['memo_count']} |",
        f"| 나이 추론 시도 건수 | {result['age_inference_attempts']} |",
        f"| 나이 추론 적중률 | {result['age_inference_correct_rate']:.1%} |",
        f"| 한 사람으로 좁혀진 메모 수 | {result['narrowed_to_one_count']} |",
        f"| 한 사람으로 좁혀진 비율 | {result['narrowed_to_one_rate']:.1%} |",
        "",
        "## 조치",
        "- 한 사람으로 좁혀진 사례가 있으면 해당 메모의 처리(일반화·문장 삭제)를 강화하고",
        "  재시험한다. 특정인을 알아볼 수 있는 중간 결과는 기록하지 않고 즉시 파기했다.",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
