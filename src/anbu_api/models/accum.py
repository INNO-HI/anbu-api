"""누적 DB(원본) 모델 — 원시스템 적재분 + SFR-002 파생 테이블.

- 직접식별자를 포함하므로 본교 서버 밖 반출 금지(공통사항 가·나).
- 모든 시각 컬럼은 KST naive datetime으로 저장한다(SFR-002).
- 결측 표준: 값이 없으면 NULL. 빈 문자열·'-'·'미상' 표기 금지(SFR-003).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anbu_api.db import AccumBase
from anbu_api.timeutil import now_kst

# sqlite autoincrement 호환 BigInt PK
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Subject(AccumBase):
    """대상자(원본). 직접식별자 포함 — 전송 금지, 화면 마스킹 대상(SFR-007)."""

    __tablename__ = "subjects"

    subject_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), comment="직접식별자: 전송 시 삭제")
    phone: Mapped[str | None] = mapped_column(String(20), comment="직접식별자: 전송 시 삭제")
    address_full: Mapped[str | None] = mapped_column(String(200), comment="직접식별자: 전송 시 삭제")
    region_emd: Mapped[str | None] = mapped_column(String(50), comment="읍·면·동 (전송 시 이 수준까지만 유지)")
    birth_date: Mapped[date | None] = mapped_column(Date, comment="전송 시 연령대로 일반화(85세 이상 통합)")
    gender: Mapped[str | None] = mapped_column(String(1), comment="M/F")
    guardian_name: Mapped[str | None] = mapped_column(String(50), comment="직접식별자: 전송 시 삭제")
    guardian_phone: Mapped[str | None] = mapped_column(String(20), comment="직접식별자: 전송 시 삭제")
    care_worker_name: Mapped[str | None] = mapped_column(String(50), comment="직접식별자: 전송 시 삭제")
    care_worker_phone: Mapped[str | None] = mapped_column(String(20), comment="직접식별자: 전송 시 삭제")
    service_start_date: Mapped[date | None] = mapped_column(Date, comment="전송 시 월 단위(YYYY-MM)로 변환")
    service_end_date: Mapped[date | None] = mapped_column(Date, comment="전송 시 월 단위(YYYY-MM)로 변환")
    meal_level: Mapped[str | None] = mapped_column(String(20), comment="식사 기능 코드 L1~L5 → 전송 시 상위 범주화")
    cognition_level: Mapped[str | None] = mapped_column(String(20), comment="인지 기능 코드 L1~L5 → 전송 시 상위 범주화")
    communication_level: Mapped[str | None] = mapped_column(String(20), comment="의사소통 기능 코드 L1~L5 → 전송 시 상위 범주화")
    benefit_type: Mapped[str | None] = mapped_column(String(20), comment="수급 구분: 전송 시 삭제(협의 시 예/아니오만)")
    high_risk_yn: Mapped[bool] = mapped_column(Boolean, default=False, comment="고위험군 여부: 전송 시 예/아니오만")
    high_risk_reason: Mapped[str | None] = mapped_column(String(200), comment="판정 사유: 전송 시 삭제")
    notes: Mapped[str | None] = mapped_column(Text, comment="자유기술: 전송 제외(SFR-010 채택 시 정밀 가명처리)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst, onupdate=now_kst)

    devices: Mapped[list["Device"]] = relationship(back_populates="subject")


class Device(AccumBase):
    """장비(IoT-LED 센서). current_status는 현재값만 — 이력은 DeviceStatusHistory(SFR-002)."""

    __tablename__ = "devices"

    device_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"), index=True)
    room: Mapped[str | None] = mapped_column(String(20), comment="설치 위치: 안방/거실/주방/화장실 등")
    device_type: Mapped[str] = mapped_column(String(20), default="LED")
    serial_no: Mapped[str | None] = mapped_column(String(50))
    install_date: Mapped[date | None] = mapped_column(Date)
    current_status: Mapped[str] = mapped_column(
        String(10), default="normal", comment="코드: normal/inactive/fault"
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst, onupdate=now_kst)

    subject: Mapped[Subject] = relationship(back_populates="devices")


class LedRawLog(AccumBase):
    """LED 원시 로그 — 점등 중 약 12초 간격 1행, 소등 중 무기록(과업지시서 현행 환경)."""

    __tablename__ = "led_raw_logs"
    __table_args__ = (Index("ix_led_raw_device_time", "device_id", "logged_at"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id"))
    logged_at: Mapped[datetime] = mapped_column(DateTime)


class LightingInterval(AccumBase):
    """점등 구간 파생 테이블(SFR-002): 원시 로그 → 시작·종료·지속시간."""

    __tablename__ = "lighting_intervals"
    __table_args__ = (
        UniqueConstraint("device_id", "started_at", name="uq_interval_device_start"),
        Index("ix_interval_device_time", "device_id", "started_at"),
    )

    interval_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id"))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)
    duration_sec: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)


class DeviceStatusHistory(AccumBase):
    """장비 상태 변경 이력(SFR-002): 무활동 구간과 장비 중단 구간을 사후 구분 가능하게 누적."""

    __tablename__ = "device_status_history"
    __table_args__ = (Index("ix_status_hist_device_time", "device_id", "changed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id"))
    status: Mapped[str] = mapped_column(String(10), comment="normal/inactive/fault")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)
    source: Mapped[str] = mapped_column(String(10), default="auto", comment="auto(추론)/sync(원시스템)/manual")
    note: Mapped[str | None] = mapped_column(String(200))


class CareRecord(AccumBase):
    """돌봄 기록. memo는 자유기술 — 전송 제외 원칙, SFR-010 채택 시 정밀 가명처리 후 전송."""

    __tablename__ = "care_records"

    record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"), index=True)
    care_worker_name: Mapped[str | None] = mapped_column(String(50))
    visit_at: Mapped[datetime] = mapped_column(DateTime)
    care_type: Mapped[str | None] = mapped_column(String(30), comment="코드: 방문/전화/기타")
    memo: Mapped[str | None] = mapped_column(Text)


class Alert(AccumBase):
    """이상 알림."""

    __tablename__ = "alerts"

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.device_id"))
    alert_type: Mapped[str] = mapped_column(
        String(30), comment="코드: NO_LIGHT_24H/LONG_INACTIVITY/DEVICE_FAULT"
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(String(200))


class AmiUsageA(AccumBase):
    """전력(AMI) 원천 1종 — 미적재 스테이징. SFR-009 수행 시 정본으로 통합."""

    __tablename__ = "ami_usage_a"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.subject_id"))
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    kwh: Mapped[Decimal] = mapped_column(Numeric(10, 3))


class AmiUsageB(AccumBase):
    """전력(AMI) 원천 2종 — 필드명이 다른 중복 원천(통합 대상)."""

    __tablename__ = "ami_usage_b"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    meter_no: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.subject_id"))
    read_time: Mapped[datetime] = mapped_column(DateTime)
    usage_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 3))


class PowerUsage(AccumBase):
    """전력(AMI) 정본(SFR-009): 2종 통합·중복 제거, 계량기 식별자는 적재 시점에 가명처리."""

    __tablename__ = "power_usage"
    __table_args__ = (
        UniqueConstraint("meter_pseudo_id", "measured_at", name="uq_power_meter_time"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    meter_pseudo_id: Mapped[str] = mapped_column(String(64), comment="가명 계량기 식별자(SFR-009)")
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.subject_id"))
    measured_at: Mapped[datetime] = mapped_column(DateTime)
    kwh: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    source: Mapped[str] = mapped_column(String(1), comment="정본 출처: A(우선)/B(보충)")
