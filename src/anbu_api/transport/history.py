"""전송 이력(SFR-006)·구독 수신 기록(SFR-005 제공 실적) 기록 헬퍼."""
from __future__ import annotations

from sqlalchemy.orm import Session

from anbu_api.models.ops import SubscriptionReceipt, TransferHistory


def record_publish(
    ops_session: Session,
    table_name: str,
    topic: str,
    record_count: int,
    *,
    status: str = "ok",
    publisher: str | None = None,
    detail: str | None = None,
) -> TransferHistory:
    """발행 이력을 남긴다. commit은 호출측 책임."""
    row = TransferHistory(
        table_name=table_name,
        topic=topic,
        record_count=record_count,
        status=status,
        publisher=publisher,
        detail=detail,
    )
    ops_session.add(row)
    return row


def record_receipt(
    ops_session: Session,
    university: str,
    client_id: str,
    topic: str,
    record_count: int,
) -> SubscriptionReceipt:
    """참여 대학 수신 확인을 남긴다(제공 실적 집계 원천). commit은 호출측 책임."""
    row = SubscriptionReceipt(
        university=university,
        client_id=client_id,
        topic=topic,
        record_count=record_count,
    )
    ops_session.add(row)
    return row
