"""자유기술 텍스트 정밀 가명처리(SFR-010) — 규칙 기반 1차 처리.

처리 대상(과업지시서):
  - 식별정보: 이름·연락처(주민번호·전화번호) 등
  - 식별가능정보: 나이·연도, 직업, 사는 곳 묘사, 가족 관계
  - 특이정보: 희귀 직업·병명, 특이한 사건
처리 방법: 삭제, 상위 범주 일반화(나이→연령대, 날짜→월), 문장 삭제.
대상자 본인뿐 아니라 메모에 나오는 가족·동거인·보호자 이름도 같은 기준으로 처리한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class MaskResult:
    """가명처리 결과: 처리된 텍스트와 치환 내역(유형·건수 집계용)."""

    text: str
    replacements: list[dict] = field(default_factory=list)


# 특이정보(희귀 병명 등) — 그것만으로 특정인이 떠오를 수 있는 키워드
RARE_KEYWORDS = [
    "길랑-바레", "길랑바레", "루게릭", "크론병", "헌팅턴", "희귀질환", "희귀병",
]

_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("주민등록번호", re.compile(r"\d{6}\s*-\s*[1-4]\d{6}"), "[주민번호 삭제]"),
    ("전화번호", re.compile(r"01[016789]\s*-?\s*\d{3,4}\s*-?\s*\d{4}"), "[연락처 삭제]"),
    ("생년", re.compile(r"(19|20)(\d)\d년생"), r"\1\g<2>0년대생"),
    # '2026년 10월 20일' → '2026년 10월' (날짜는 월 단위로 일반화)
    ("일자", re.compile(r"((?:19|20)\d{2}년\s*\d{1,2}월)\s*\d{1,2}일"), r"\1"),
    # '87세' → 연령대 (아래 _age_repl에서 처리)
    # 상세 주소: '중앙로10길 1', 'OO로 12-3' 등 도로명+번지
    ("상세주소", re.compile(r"[가-힣A-Za-z0-9]+(?:로|길)\s?\d+(?:-\d+)?(?:번지|호)?"), "[상세주소 삭제]"),
]

_AGE_RE = re.compile(r"(\d{1,3})세")


def _age_repl(m: re.Match) -> str:
    age = int(m.group(1))
    if age >= 85:
        return "85세 이상"
    if age < 65:
        return "65세 미만"
    return f"{(age // 10) * 10}대"


class FreeTextPseudonymizer:
    """규칙 기반 자유기술 가명처리기.

    known_names: 운영 테이블에서 수집한 실명 목록(대상자·보호자·담당자).
    이름은 사전 기반으로 정확히 치환하고, 호칭이 붙은 미등록 이름 패턴도 보조 처리한다.
    """

    # 호칭이 붙은 한글 이름(2~4자) — 사전에 없는 이름의 안전망
    _NAME_SUFFIX_RE = re.compile(r"[가-힣]{2,4}(?=\s*(?:어르신|님|씨|할머니|할아버지))")

    def __init__(self, known_names: list[str] | None = None) -> None:
        # 긴 이름 먼저 치환(부분 문자열 중복 방지)
        self._names = sorted({n for n in (known_names or []) if n and len(n) >= 2},
                             key=len, reverse=True)

    def pseudonymize(self, text: str) -> MaskResult:
        result = MaskResult(text=text)

        def note(kind: str, n: int) -> None:
            if n:
                result.replacements.append({"type": kind, "count": n})

        t = result.text
        for kind, pattern, repl in _PATTERNS:
            t, n = pattern.subn(repl, t)
            note(kind, n)

        t, n = _AGE_RE.subn(_age_repl, t)
        note("나이", n)

        n_names = 0
        for name in self._names:
            if name in t:
                n_names += t.count(name)
                t = t.replace(name, "[이름 삭제]")
        t, n2 = self._NAME_SUFFIX_RE.subn("[이름 삭제]", t)
        note("이름", n_names + n2)

        # 특이정보: 해당 키워드가 포함된 문장 전체 삭제(문장 삭제 처리)
        n_rare = 0
        sentences = re.split(r"(?<=[.!?다])\s+", t)
        kept = []
        for s in sentences:
            if any(k in s for k in RARE_KEYWORDS):
                n_rare += 1
                kept.append("[특이정보 문장 삭제]")
            else:
                kept.append(s)
        note("특이정보", n_rare)

        result.text = " ".join(kept)
        return result


def build_known_names(accum_session) -> list[str]:
    """운영 테이블에서 실명 목록(대상자·보호자·생활지원사)을 수집한다."""
    from sqlalchemy import select

    from anbu_api.models.accum import Subject

    names: set[str] = set()
    for row in accum_session.execute(
        select(Subject.name, Subject.guardian_name, Subject.care_worker_name)
    ).all():
        names.update(v for v in row if v)
    return sorted(names)
