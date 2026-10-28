"""시각 유틸 — 모든 저장 시각은 한국 표준시(KST) naive datetime으로 통일한다(SFR-002)."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """현재 시각을 KST naive datetime으로 반환한다(DB 저장용)."""
    return datetime.now(KST).replace(tzinfo=None)


def to_kst_naive(dt: datetime) -> datetime:
    """aware datetime을 KST naive로 변환한다. naive 입력은 KST로 간주해 그대로 반환."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(KST).replace(tzinfo=None)


def to_ym(d: date | datetime | None) -> str | None:
    """날짜를 월 단위(YYYY-MM)로 일반화한다 — 서비스 시작·종료일 가명처리 기준(SFR-004)."""
    if d is None:
        return None
    return f"{d:%Y-%m}"


def iso_kst(dt: datetime | None) -> str | None:
    """전송본 직렬화용 ISO 문자열(KST naive 전제)."""
    if dt is None:
        return None
    return dt.isoformat(sep=" ", timespec="seconds")
