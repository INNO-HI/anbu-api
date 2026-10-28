"""운영 DB 모델 — 가명 매핑(암호화)·전송 이력·구독·계정·감사 로그.

매핑 테이블은 원본·전송용과 분리 보관하며(SFR-004) 발주기관 전용 권한으로만
접근한다(SFR-007: API에서 super_admin 역할만 허용).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from anbu_api.db import OpsBase
from anbu_api.timeutil import now_kst


class PseudonymMapping(OpsBase):
    """원 식별자 ↔ 가명 식별자 매핑(SFR-004).

    - original_encrypted: 원 식별자의 Fernet 암호문(평문 저장 금지).
    - lookup_hash: HMAC-SHA256(secret, namespace:original) — 복호화 없이 기존 매핑 조회용.
    - pseudo_id: 무작위 토큰(단순 해시 아님).
    """

    __tablename__ = "pseudonym_mappings"
    __table_args__ = (
        UniqueConstraint("namespace", "lookup_hash", name="uq_mapping_lookup"),
        UniqueConstraint("namespace", "pseudo_id", name="uq_mapping_pseudo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    namespace: Mapped[str] = mapped_column(String(20), comment="subject/device/meter")
    lookup_hash: Mapped[str] = mapped_column(String(64))
    original_encrypted: Mapped[str] = mapped_column(Text)
    pseudo_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)


class TransferHistory(OpsBase):
    """전송 이력(SFR-006) — 발행 기준."""

    __tablename__ = "transfer_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(40))
    topic: Mapped[str] = mapped_column(String(100))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)
    publisher: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10), default="ok", comment="ok/error/dry_run")
    detail: Mapped[str | None] = mapped_column(String(200))


class SubscriptionReceipt(OpsBase):
    """참여 대학 구독 수신 기록 — 데이터 제공 실적 집계(SFR-005)의 원천."""

    __tablename__ = "subscription_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university: Mapped[str] = mapped_column(String(50))
    client_id: Mapped[str] = mapped_column(String(50))
    topic: Mapped[str] = mapped_column(String(100))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)


class Subscription(OpsBase):
    """참여 대학 구독 권한(SFR-006). client_key_hash로 수신 확인(REST) 인증."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    university: Mapped[str] = mapped_column(String(50))
    client_id: Mapped[str] = mapped_column(String(50), unique=True)
    client_key_hash: Mapped[str | None] = mapped_column(String(200))
    topic_pattern: Mapped[str] = mapped_column(String(100), comment="예: anbu/#, anbu/alerts")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)


class User(OpsBase):
    """관리자 계정 — 3단계 권한(SFR-007): super_admin / admin / viewer."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), comment="super_admin/admin/viewer")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)


class AuditLog(OpsBase):
    """작업 이력(공통사항 라: 서버 접근·작업 이력 기록)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(50))
    detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)


class EtlRun(OpsBase):
    """ETL·가명처리·전송 작업 실행 기록 — 대시보드 적재 현황(SFR-005)의 원천."""

    __tablename__ = "etl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job: Mapped[str] = mapped_column(String(40), comment="intervals/status/retention/pseudonymize/ami/publish")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now_kst)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default="ok", comment="ok/error")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text)
