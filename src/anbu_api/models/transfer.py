"""전송용 DB 모델 — 가명처리본 7개 테이블(SFR-004).

- 원본과 물리 분리. 참여 대학은 이 DB의 전송본만 구독 수신한다(원본 직접 접근 불허).
- 모든 PK는 원본 내부 일련번호와 무관한 새 키(autoincrement)다(기준: 내부 일련번호 → 새 키 대체).
- 직접식별자 컬럼은 아예 존재하지 않는다(스키마 수준 차단).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from anbu_api.db import TransferBase

BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class TSubject(TransferBase):
    """① 대상자(가명). 연령대·읍면동·월 단위 일자·상위 범주 기능 수준만 보유."""

    __tablename__ = "t_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pseudo_subject_id: Mapped[str] = mapped_column(String(64), unique=True)
    age_band: Mapped[str | None] = mapped_column(String(10), comment="예: 65-69 … 80-84, 85+")
    gender: Mapped[str | None] = mapped_column(String(1))
    region_emd: Mapped[str | None] = mapped_column(String(50), comment="읍·면·동까지만")
    service_start_ym: Mapped[str | None] = mapped_column(String(7), comment="YYYY-MM")
    service_end_ym: Mapped[str | None] = mapped_column(String(7), comment="YYYY-MM")
    meal_cat: Mapped[str | None] = mapped_column(String(10), comment="자립/부분도움/전적도움")
    cognition_cat: Mapped[str | None] = mapped_column(String(10))
    communication_cat: Mapped[str | None] = mapped_column(String(10))
    high_risk_yn: Mapped[bool | None] = mapped_column(Boolean, comment="예/아니오만, 사유 없음")
    benefit_yn: Mapped[bool | None] = mapped_column(
        Boolean, comment="기본 None(삭제). 발주기관 협의 시에만 예/아니오 채움"
    )


class TDevice(TransferBase):
    """② 장비(가명)."""

    __tablename__ = "t_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pseudo_device_id: Mapped[str] = mapped_column(String(64), unique=True)
    pseudo_subject_id: Mapped[str] = mapped_column(String(64), index=True)
    room: Mapped[str | None] = mapped_column(String(20))
    device_type: Mapped[str | None] = mapped_column(String(20))


class TLightingInterval(TransferBase):
    """③ 점등 구간."""

    __tablename__ = "t_lighting_intervals"
    __table_args__ = (Index("ix_t_interval_device_time", "pseudo_device_id", "started_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    pseudo_device_id: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)
    duration_sec: Mapped[int] = mapped_column(Integer)


class TDeviceStatusHistory(TransferBase):
    """④ 장비 상태 이력."""

    __tablename__ = "t_device_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pseudo_device_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(10))
    changed_at: Mapped[datetime] = mapped_column(DateTime)


class TCareRecord(TransferBase):
    """⑤ 돌봄 기록. memo_pseudo는 SFR-010 채택·추가검수 통과 시에만 채워진다(기본 NULL)."""

    __tablename__ = "t_care_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pseudo_subject_id: Mapped[str] = mapped_column(String(64), index=True)
    visit_at: Mapped[datetime] = mapped_column(DateTime)
    care_type: Mapped[str | None] = mapped_column(String(30))
    memo_pseudo: Mapped[str | None] = mapped_column(Text, comment="SFR-010 정밀 가명처리 결과")


class TAlert(TransferBase):
    """⑥ 이상 알림."""

    __tablename__ = "t_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pseudo_subject_id: Mapped[str] = mapped_column(String(64), index=True)
    pseudo_device_id: Mapped[str | None] = mapped_column(String(64))
    alert_type: Mapped[str] = mapped_column(String(30))
    triggered_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class TPowerUsage(TransferBase):
    """⑦ 전력 사용량 — SFR-009 수행 시에만 적재."""

    __tablename__ = "t_power_usage"
    __table_args__ = (Index("ix_t_power_meter_time", "pseudo_meter_id", "measured_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    pseudo_meter_id: Mapped[str] = mapped_column(String(64))
    pseudo_subject_id: Mapped[str | None] = mapped_column(String(64))
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    kwh: Mapped[Decimal] = mapped_column(Numeric(10, 3))


# 전송 대상 테이블명(토픽·발행 단위) — SFR-006에서 사용
TRANSFER_TABLES: dict[str, type[TransferBase]] = {
    "subjects": TSubject,
    "devices": TDevice,
    "lighting_intervals": TLightingInterval,
    "device_status_history": TDeviceStatusHistory,
    "care_records": TCareRecord,
    "alerts": TAlert,
    "power_usage": TPowerUsage,
}
