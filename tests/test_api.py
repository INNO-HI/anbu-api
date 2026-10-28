"""SFR-005/007 API 테스트 — 로그인, 3단계 권한, 화면 마스킹, 대시보드, 수신 확인."""
import pytest
from fastapi.testclient import TestClient

from anbu_api.api import deps
from anbu_api.api.auth import hash_password
from anbu_api.api.main import create_app
from anbu_api.models.ops import User
from anbu_api.pseudonym.pipeline import run_full


@pytest.fixture
def client(seeded_accum, transfer_session, ops_session):
    """3개 DB를 테스트 세션으로 바꾼 TestClient. 역할별 계정 포함."""
    for username, role in (("su", "super_admin"), ("op", "admin"), ("ro", "viewer")):
        ops_session.add(User(username=username, password_hash=hash_password("pw-" + username),
                             role=role))
    ops_session.commit()

    app = create_app()
    app.dependency_overrides[deps.accum_db] = lambda: seeded_accum
    app.dependency_overrides[deps.transfer_db] = lambda: transfer_session
    app.dependency_overrides[deps.ops_db] = lambda: ops_session
    return TestClient(app)


def _login(client, username):
    res = client.post("/api/token", data={"username": username, "password": "pw-" + username})
    assert res.status_code == 200
    return {"Authorization": "Bearer " + res.json()["access_token"]}


def test_login_and_bad_password(client):
    assert client.post("/api/token", data={"username": "ro", "password": "틀림"}).status_code == 401
    headers = _login(client, "ro")
    assert client.get("/api/dashboard/ingest", headers=headers).status_code == 200


def test_unauthenticated_rejected(client):
    assert client.get("/api/dashboard/ingest").status_code == 401
    assert client.get("/api/data/subjects").status_code == 401


def test_role_gates(client):
    """viewer는 조회만, admin은 실행, super_admin은 매핑 재식별까지."""
    ro, op, su = _login(client, "ro"), _login(client, "op"), _login(client, "su")

    # viewer: 실행형 엔드포인트 금지
    assert client.post("/api/admin/etl/intervals", headers=ro).status_code == 403
    assert client.post("/api/admin/pseudonymize", json={}, headers=ro).status_code == 403

    # admin: ETL 실행 가능
    res = client.post("/api/admin/etl/intervals", headers=op)
    assert res.status_code == 200
    assert res.json()["created"] > 0

    # admin: 매핑 재식별 금지(발주기관 전용), super_admin만 가능
    client.post("/api/admin/pseudonymize", json={}, headers=op)
    from anbu_api.models.transfer import TSubject
    # 전송용에서 가명 ID 하나 조회
    sub_rows = client.get("/api/data/subjects", headers=ro).json()
    assert sub_rows
    # 가명 ID 획득을 위해 매핑 없는 임의값 시험
    denied = client.get("/api/admin/mappings/resolve",
                        params={"namespace": "subject", "pseudo_id": "x"}, headers=op)
    assert denied.status_code == 403
    miss = client.get("/api/admin/mappings/resolve",
                      params={"namespace": "subject", "pseudo_id": "x"}, headers=su)
    assert miss.status_code == 404  # 권한은 통과, 매핑 없음


def test_masking_applied(client):
    """대상자 화면에서 이름·연락처는 마스킹되고 자유기술은 노출되지 않는다."""
    headers = _login(client, "ro")
    rows = client.get("/api/data/subjects", headers=headers).json()
    assert len(rows) == 4
    for row in rows:
        assert "*" in row["name"]                       # 김*희 형태
        assert row["phone"] is None or "****" in row["phone"]
        assert "notes" not in row and "memo" not in row  # 자유기술 비노출
        assert "birth_date" not in row                  # 생년월일 대신 연령대
        assert row["age_band"]

    detail = client.get(f"/api/data/subjects/{rows[0]['subject_id']}", headers=headers).json()
    assert "*" in detail["guardian_name"]
    assert "상세 비공개" in detail["region"]
    assert client.get("/api/data/subjects/9999", headers=headers).status_code == 404


def test_dashboard_endpoints(client, seeded_accum, transfer_session, ops_session):
    headers = _login(client, "op")
    client.post("/api/admin/etl/intervals", headers=headers)
    client.post("/api/admin/pseudonymize", json={}, headers=headers)
    client.post("/api/admin/publish", json={"dry_run": True}, headers=headers)

    ingest = client.get("/api/dashboard/ingest", headers=headers).json()
    assert ingest["tables"]["subjects"] == 4
    assert ingest["tables"]["lighting_intervals"] > 0
    assert any(r["job"] == "pseudonymize" for r in ingest["recent_runs"])

    sensors = client.get("/api/dashboard/sensors", headers=headers).json()
    assert sum(sensors["device_status"].values()) == ingest["tables"]["devices"]

    transfers = client.get("/api/dashboard/transfers", headers=headers).json()
    assert len(transfers["recent"]) > 0
    assert transfers["recent"][0]["status"] == "dry_run"


def test_subscription_and_receipt_flow(client):
    """구독 등록 → client_key 1회 발급 → 수신 확인 → 제공 실적 집계."""
    op = _login(client, "op")
    created = client.post("/api/admin/subscriptions", json={
        "university": "A대학교", "client_id": "univ_a", "topic_pattern": "anbu/#",
    }, headers=op)
    assert created.status_code == 200
    key = created.json()["client_key"]

    # 수신 확인(REST) — 올바른 키
    ok = client.post("/api/receipts", json={"topic": "anbu/subjects", "record_count": 10},
                     headers={"X-Client-Id": "univ_a", "X-Client-Key": key})
    assert ok.status_code == 200
    # 잘못된 키 거부
    bad = client.post("/api/receipts", json={"topic": "anbu/subjects", "record_count": 1},
                      headers={"X-Client-Id": "univ_a", "X-Client-Key": "wrong"})
    assert bad.status_code == 401

    # 제공 실적 집계에 반영
    summary = client.get("/api/dashboard/receipts", headers=op).json()
    assert summary["universities"][0]["university"] == "A대학교"
    assert summary["universities"][0]["total_records"] == 10

    # 중복 client_id 거부
    dup = client.post("/api/admin/subscriptions", json={
        "university": "A대학교", "client_id": "univ_a",
    }, headers=op)
    assert dup.status_code == 409


def test_user_management_super_only(client):
    op, su = _login(client, "op"), _login(client, "su")
    assert client.get("/api/admin/users", headers=op).status_code == 403
    assert client.get("/api/admin/users", headers=su).status_code == 200

    created = client.post("/api/admin/users", json={
        "username": "new_viewer", "password": "pw", "role": "viewer",
    }, headers=su)
    assert created.status_code == 200
    # admin은 계정 생성 불가
    assert client.post("/api/admin/users", json={
        "username": "x", "password": "pw", "role": "viewer",
    }, headers=op).status_code == 403


def test_audit_log_recorded(client):
    su = _login(client, "su")
    client.post("/api/admin/etl/status", headers=su)
    logs = client.get("/api/admin/audit", headers=su).json()
    actions = {l["action"] for l in logs}
    assert "etl:status" in actions
    assert "login" in actions


def test_dashboard_page_served(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "운영 대시보드" in res.text
