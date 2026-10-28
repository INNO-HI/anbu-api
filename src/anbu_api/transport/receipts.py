"""참여 대학 수신 확인 수집(SFR-005 제공 실적의 원천).

참여 대학 구독 클라이언트는 수신 후 anbu/receipts/<client_id> 토픽으로 수신 확인
메시지(JSON: {"topic": ..., "record_count": ...})를 발행한다. 이 모듈은 해당 토픽을
구독해 SubscriptionReceipt로 적재한다. REST 경로(POST /api/receipts)도 병행 제공된다.
"""
from __future__ import annotations

import json
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.ops import Subscription
from anbu_api.transport.history import record_receipt


def handle_receipt_message(
    ops_session: Session, topic: str, payload: bytes | str
) -> bool:
    """수신 확인 메시지 1건을 검증·적재한다. 등록된 활성 구독이 아니면 무시(False)."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[-2] != "receipts":
        return False
    client_id = parts[-1]
    sub = ops_session.scalars(
        select(Subscription).where(
            Subscription.client_id == client_id,
            Subscription.active == True,  # noqa: E712
        )
    ).first()
    if sub is None:
        return False
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return False
    record_receipt(
        ops_session,
        university=sub.university,
        client_id=client_id,
        topic=str(data.get("topic", "")),
        record_count=int(data.get("record_count", 0)),
    )
    ops_session.commit()
    return True


def attach_receipt_listener(client, ops_session_factory: Callable[[], Session]) -> None:
    """MQTT 클라이언트에 수신 확인 구독·처리 콜백을 연결한다(브로커 연결은 호출측)."""
    prefix = settings.mqtt_topic_prefix

    def on_message(cli, userdata, msg):
        session = ops_session_factory()
        try:
            handle_receipt_message(session, msg.topic, msg.payload)
        finally:
            session.close()

    client.subscribe(f"{prefix}/receipts/+", qos=1)
    client.on_message = on_message
