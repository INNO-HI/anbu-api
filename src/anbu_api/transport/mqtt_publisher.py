"""구독형 데이터 전송 발행(SFR-006).

가명처리된 전송용 DB의 행을 MQTT 토픽(anbu/<table>)으로 발행하고 전송 이력을
기록한다. 전송 구간은 TLS로 암호화한다(SFR-004). 발행 대상은 전송용 DB만이며
누적 DB(원본)는 이 모듈에서 접근하지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import paho.mqtt.client as mqtt
from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.transfer import TRANSFER_TABLES
from anbu_api.timeutil import iso_kst
from anbu_api.transport.history import record_publish


def build_client(client_id: str = "anbu_publisher") -> mqtt.Client:
    """운영용 MQTT 클라이언트(TLS·인증 설정 포함)."""
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        protocol=mqtt.MQTTv5,
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    if settings.mqtt_tls_ca:
        client.tls_set(ca_certs=settings.mqtt_tls_ca)  # 전송 구간 TLS 암호화
    return client


def serialize_row(obj: Any) -> dict:
    """전송용 모델 행 → JSON 직렬화 가능한 dict (datetime→KST ISO, Decimal→float)."""
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = iso_kst(val)
        elif isinstance(val, Decimal):
            val = float(val)
        out[col.name] = val
    return out


def publish_table(
    transfer_session: Session,
    ops_session: Session,
    table_name: str,
    *,
    client: mqtt.Client | None = None,
    dry_run: bool = False,
    publisher: str = "system",
) -> int:
    """전송용 테이블 하나를 발행하고 건수를 반환한다(전송 이력 기록·commit 포함).

    client를 주입하면 연결 관리는 호출측 책임(테스트·일괄 발행용).
    dry_run=True면 실제 발행 없이 직렬화·이력 기록만 수행한다.
    """
    if table_name not in TRANSFER_TABLES:
        raise ValueError(f"알 수 없는 전송 테이블: {table_name}")
    model = TRANSFER_TABLES[table_name]
    topic = f"{settings.mqtt_topic_prefix}/{table_name}"
    rows = transfer_session.scalars(select(model)).all()

    own_client = False
    try:
        if not dry_run:
            if client is None:
                client = build_client()
                client.connect(settings.mqtt_host, settings.mqtt_port)
                client.loop_start()
                own_client = True
            for row in rows:
                payload = json.dumps(serialize_row(row), ensure_ascii=False)
                client.publish(topic, payload, qos=1)
        record_publish(
            ops_session, table_name, topic, len(rows),
            status="dry_run" if dry_run else "ok", publisher=publisher,
        )
        ops_session.commit()
    except Exception as e:
        record_publish(
            ops_session, table_name, topic, 0,
            status="error", publisher=publisher, detail=str(e)[:200],
        )
        ops_session.commit()
        raise
    finally:
        if own_client and client is not None:
            client.loop_stop()
            client.disconnect()
    return len(rows)


def publish_all(
    transfer_session: Session,
    ops_session: Session,
    *,
    client: mqtt.Client | None = None,
    dry_run: bool = False,
    publisher: str = "system",
) -> dict[str, int]:
    """전송용 7개 테이블 전체를 발행한다(빈 power_usage는 건너뜀)."""
    own_client = False
    if not dry_run and client is None:
        client = build_client()
        client.connect(settings.mqtt_host, settings.mqtt_port)
        client.loop_start()
        own_client = True
    try:
        results: dict[str, int] = {}
        for table_name in TRANSFER_TABLES:
            results[table_name] = publish_table(
                transfer_session, ops_session, table_name,
                client=client, dry_run=dry_run, publisher=publisher,
            )
        return results
    finally:
        if own_client and client is not None:
            client.loop_stop()
            client.disconnect()
