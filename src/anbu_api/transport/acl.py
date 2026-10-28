"""Mosquitto ACL 생성(SFR-006 구독 권한 관리).

운영 DB의 Subscription(참여 대학 구독 권한)으로부터 브로커 ACL 파일을 생성한다.
- 발행 계정(anbu_publisher): 데이터 토픽 전체 발행 가능
- 참여 대학 계정: 승인된 topic_pattern 구독(read)만 가능 + 자신의 수신 확인
  토픽(anbu/receipts/<client_id>) 발행(write) 가능
비밀번호 파일은 mosquitto_passwd로 별도 관리한다(운영 매뉴얼 참조).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.ops import Subscription


def generate_mosquitto_acl(ops_session: Session, out_path: str) -> str:
    """활성 구독 기준으로 Mosquitto ACL 파일을 생성하고 경로를 반환한다."""
    prefix = settings.mqtt_topic_prefix
    lines = [
        "# anbu-api가 생성한 Mosquitto ACL — 직접 수정하지 말 것",
        "# 재생성: anbu gen-acl",
        "",
        f"user {settings.mqtt_username or 'anbu_publisher'}",
        f"topic readwrite {prefix}/#",
        "",
    ]
    subs = ops_session.scalars(
        select(Subscription).where(Subscription.active == True)  # noqa: E712
    ).all()
    for sub in subs:
        lines += [
            f"# {sub.university}",
            f"user {sub.client_id}",
            f"topic read {sub.topic_pattern}",
            f"topic write {prefix}/receipts/{sub.client_id}",
            "",
        ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
