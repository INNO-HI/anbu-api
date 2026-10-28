"""가명처리 기준(SFR-004) — 가명처리 기준서(docs/가명처리기준서.md)와 일치해야 한다.

| 구분            | 기준 |
|-----------------|------|
| 직접식별자      | 이름·연락처·주소·보호자·담당자 정보 삭제(전송 스키마에 컬럼 자체가 없음) |
| 가명 식별자     | 무작위 토큰 + 암호화 매핑(단순 해시 미사용) — mapping_store 참조 |
| 준식별자        | 생년월일 → 연령대(85세 이상 통합), 지역 → 읍·면·동까지만 |
| 서비스 시작·종료 | 월 단위(YYYY-MM) |
| 내부 일련번호   | 전송본에서 새 키로 대체(전송 테이블 PK는 별도 autoincrement) |
| 자유기술        | 전송 제외(SFR-010 채택 시에만 정밀 가명처리 후 전송) |
| 건강·경제 상태  | 기능 단계 → 상위 범주(자립/부분도움/전적도움), 수급 구분 삭제, 고위험군 예/아니오만 |
"""
from __future__ import annotations

from datetime import date

# 연령대 구간: 5세 단위, 85세 이상은 하나의 범주로 통합
AGE_BAND_START = 65
AGE_BAND_MERGE = 85


def age_band(birth: date | None, *, as_of: date) -> str | None:
    """생년월일을 연령대로 일반화한다. 85세 이상은 '85+' 단일 범주."""
    if birth is None:
        return None
    age = as_of.year - birth.year - ((as_of.month, as_of.day) < (birth.month, birth.day))
    if age >= AGE_BAND_MERGE:
        return "85+"
    if age < AGE_BAND_START:
        return f"{AGE_BAND_START}세 미만"
    low = (age // 5) * 5
    return f"{low}-{low + 4}"


# 기능 단계 코드(L1~L5) → 상위 범주 (건강 관련 항목 범주화 기준)
LEVEL_CATEGORY = {
    "L1": "자립",
    "L2": "자립",
    "L3": "부분도움",
    "L4": "부분도움",
    "L5": "전적도움",
}


def categorize_level(code: str | None) -> str | None:
    """기능 단계 코드를 상위 범주로 변환한다. 미지 코드는 None(결측 표준)."""
    if code is None:
        return None
    return LEVEL_CATEGORY.get(code)
