"""구독형 데이터 전송 발행 스켈레톤 (SFR-006).

가명처리된 전송본을 MQTT 토픽으로 발행하고, 참여 대학이 구독해 수신한다.
전송 구간은 TLS로 암호화한다(SFR-004). 전송 이력은 호출측에서 기록한다.

토픽 예시: anbu/{dataset}/{table}
"""
from __future__ import annotations

import json

import paho.mqtt.client as mqtt

from anbu_api.config import settings


def build_client() -> mqtt.Client:
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    if settings.mqtt_tls_ca:
        # 운영: 발주기관이 발급한 CA로 TLS 전송 구간 암호화
        client.tls_set(ca_certs=settings.mqtt_tls_ca)
    return client


def publish_records(table: str, records: list[dict], dataset: str = "anbu") -> int:
    """가명처리된 레코드를 토픽으로 발행하고 발행 건수를 반환한다.

    주의: records는 이미 가명처리된 전송본이어야 한다(원본/직접식별자 금지).
    """
    topic = f"{dataset}/{table}"
    client = build_client()
    client.connect(settings.mqtt_host, settings.mqtt_port)
    client.loop_start()
    try:
        for rec in records:
            client.publish(topic, json.dumps(rec, ensure_ascii=False), qos=1)
        return len(records)
    finally:
        client.loop_stop()
        client.disconnect()
