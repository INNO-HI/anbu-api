"""SFR-006 전송 테스트 — 발행(가짜 클라이언트), 전송 이력, ACL, 수신 확인."""
import json
from types import SimpleNamespace

from sqlalchemy import select

from anbu_api.models.ops import Subscription, SubscriptionReceipt, TransferHistory
from anbu_api.pseudonym.pipeline import run_full
from anbu_api.transport.acl import generate_mosquitto_acl
from anbu_api.transport.mqtt_publisher import publish_all, publish_table, serialize_row
from anbu_api.transport.receipts import handle_receipt_message


class FakeClient:
    """브로커 연결 없이 발행 내용을 기록하는 가짜 MQTT 클라이언트."""

    def __init__(self):
        self.published: list[tuple[str, str, int]] = []

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


def _prepare_transfer(seeded_accum, transfer_session, ops_session):
    run_full(seeded_accum, transfer_session, ops_session)


def test_publish_table_with_fake_client(seeded_accum, transfer_session, ops_session):
    _prepare_transfer(seeded_accum, transfer_session, ops_session)
    client = FakeClient()
    n = publish_table(transfer_session, ops_session, "subjects", client=client)
    assert n == 4
    assert len(client.published) == 4
    topic, payload, qos = client.published[0]
    assert topic == "anbu/subjects"
    assert qos == 1
    data = json.loads(payload)
    assert "pseudo_subject_id" in data
    assert "name" not in data and "phone" not in data  # 직접식별자 없음

    hist = ops_session.scalars(select(TransferHistory)).all()
    assert len(hist) == 1
    assert hist[0].record_count == 4 and hist[0].status == "ok"


def test_publish_dry_run_records_history_only(seeded_accum, transfer_session, ops_session):
    _prepare_transfer(seeded_accum, transfer_session, ops_session)
    n = publish_table(transfer_session, ops_session, "alerts", dry_run=True)
    assert n >= 1
    hist = ops_session.scalars(select(TransferHistory)).first()
    assert hist.status == "dry_run"


def test_publish_all_covers_all_tables(seeded_accum, transfer_session, ops_session):
    _prepare_transfer(seeded_accum, transfer_session, ops_session)
    client = FakeClient()
    results = publish_all(transfer_session, ops_session, client=client)
    assert set(results) == {
        "subjects", "devices", "lighting_intervals", "device_status_history",
        "care_records", "alerts", "power_usage",
    }
    assert results["power_usage"] == 0  # SFR-009 미수행


def test_unknown_table_rejected(transfer_session, ops_session):
    import pytest

    with pytest.raises(ValueError):
        publish_table(transfer_session, ops_session, "원본테이블")


def test_serialize_row_types(seeded_accum, transfer_session, ops_session):
    _prepare_transfer(seeded_accum, transfer_session, ops_session)
    from anbu_api.models.transfer import TCareRecord

    row = transfer_session.scalars(select(TCareRecord)).first()
    data = serialize_row(row)
    assert isinstance(data["visit_at"], str)  # datetime → KST ISO 문자열


def test_generate_acl(ops_session, tmp_path):
    ops_session.add(Subscription(university="A대학교", client_id="univ_a",
                                 topic_pattern="anbu/#"))
    ops_session.add(Subscription(university="B대학교", client_id="univ_b",
                                 topic_pattern="anbu/alerts", active=False))
    ops_session.commit()

    path = generate_mosquitto_acl(ops_session, str(tmp_path / "acl"))
    content = open(path, encoding="utf-8").read()
    assert "user univ_a" in content
    assert "topic read anbu/#" in content
    assert "topic write anbu/receipts/univ_a" in content
    assert "univ_b" not in content  # 비활성 구독 제외


def test_handle_receipt_message(ops_session):
    ops_session.add(Subscription(university="A대학교", client_id="univ_a",
                                 topic_pattern="anbu/#"))
    ops_session.commit()

    ok = handle_receipt_message(
        ops_session, "anbu/receipts/univ_a",
        json.dumps({"topic": "anbu/subjects", "record_count": 42}),
    )
    assert ok
    receipt = ops_session.scalars(select(SubscriptionReceipt)).first()
    assert receipt.university == "A대학교" and receipt.record_count == 42

    # 미등록 클라이언트는 무시
    assert not handle_receipt_message(ops_session, "anbu/receipts/unknown", "{}")
    # 형식 오류 무시
    assert not handle_receipt_message(ops_session, "anbu/receipts/univ_a", "not-json")
