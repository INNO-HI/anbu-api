"""관리 API(SFR-005~007) — ETL·가명처리·발행 실행, 구독·계정 관리, 매핑 재식별.

모든 실행형 엔드포인트는 감사 로그(AuditLog)를 남긴다(공통사항 라).
매핑 재식별은 발주기관 전용(super_admin)이다.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.api import deps
from anbu_api.api.auth import hash_password, require_role, verify_password
from anbu_api.models.ops import AuditLog, Subscription, User
from anbu_api.opslog import audit
from anbu_api.timeutil import iso_kst

router = APIRouter(prefix="/api/admin", tags=["admin"])

_ETL_JOBS = ("intervals", "status", "inactivity", "retention", "ami")


class PseudonymizeIn(BaseModel):
    include_memo: bool = False  # SFR-010 채택 시에만 True


class PublishIn(BaseModel):
    table: str | None = None  # None이면 전체
    dry_run: bool = True


class SubscriptionIn(BaseModel):
    university: str
    client_id: str
    topic_pattern: str = "anbu/#"


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "viewer"


@router.post("/etl/{job}", dependencies=[Depends(require_role("admin"))])
def run_etl(
    job: str,
    current: dict = Depends(require_role("admin")),
    accum: Session = Depends(deps.accum_db),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """ETL 작업 실행: intervals / status / inactivity / retention / ami."""
    if job not in _ETL_JOBS:
        raise HTTPException(status_code=400, detail=f"알 수 없는 작업: {job}")

    if job == "intervals":
        from anbu_api.etl.lighting_intervals import build_intervals
        result: dict = {"created": build_intervals(accum)}
    elif job == "status":
        from anbu_api.etl.device_status_history import sync_status
        result = {"appended": sync_status(accum)}
    elif job == "inactivity":
        from anbu_api.etl.device_status_history import infer_inactivity
        result = {"changed": infer_inactivity(accum)}
    elif job == "retention":
        from anbu_api.etl.retention import apply_retention
        result = apply_retention(accum)
    else:  # ami (SFR-009 — 발주기관이 데이터 제공을 확보한 경우에 한함)
        from anbu_api.ami.loader import integrate_ami
        from anbu_api.pseudonym.mapping_store import MappingStore
        result = {"added": integrate_ami(accum, MappingStore(ops))}

    audit(ops, current["username"], f"etl:{job}", str(result))
    ops.commit()
    return {"job": job, **result}


@router.post("/pseudonymize")
def run_pseudonymize(
    body: PseudonymizeIn,
    current: dict = Depends(require_role("admin")),
    accum: Session = Depends(deps.accum_db),
    transfer: Session = Depends(deps.transfer_db),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """가명처리 파이프라인 실행(SFR-004). include_memo는 SFR-010 채택 시에만."""
    from anbu_api.pseudonym.pipeline import run_full

    memo_fn = None
    if body.include_memo:
        from anbu_api.freetext.pseudonymizer import FreeTextPseudonymizer, build_known_names

        p = FreeTextPseudonymizer(build_known_names(accum))
        memo_fn = lambda text: p.pseudonymize(text).text  # noqa: E731

    counts = run_full(accum, transfer, ops, memo_pseudonymizer=memo_fn)
    audit(ops, current["username"], "pseudonymize", str(counts))
    ops.commit()
    return counts


@router.post("/publish")
def run_publish(
    body: PublishIn,
    current: dict = Depends(require_role("admin")),
    transfer: Session = Depends(deps.transfer_db),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """전송용 DB 발행(SFR-006). 기본 dry_run — 실발행은 dry_run=false."""
    from anbu_api.transport.mqtt_publisher import publish_all, publish_table

    if body.table:
        result = {body.table: publish_table(
            transfer, ops, body.table, dry_run=body.dry_run, publisher=current["username"],
        )}
    else:
        result = publish_all(transfer, ops, dry_run=body.dry_run, publisher=current["username"])
    audit(ops, current["username"], "publish", f"dry_run={body.dry_run} {result}")
    ops.commit()
    return result


@router.get("/subscriptions", dependencies=[Depends(require_role("admin"))])
def list_subscriptions(ops: Session = Depends(deps.ops_db)) -> list[dict]:
    subs = ops.scalars(select(Subscription).order_by(Subscription.id)).all()
    return [
        {
            "id": s.id,
            "university": s.university,
            "client_id": s.client_id,
            "topic_pattern": s.topic_pattern,
            "active": s.active,
        }
        for s in subs
    ]


@router.post("/subscriptions")
def create_subscription(
    body: SubscriptionIn,
    current: dict = Depends(require_role("admin")),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """구독 등록(SFR-006). client_key는 이 응답에서 1회만 노출된다."""
    if ops.scalars(
        select(Subscription).where(Subscription.client_id == body.client_id)
    ).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 client_id")
    client_key = secrets.token_urlsafe(24)
    ops.add(Subscription(
        university=body.university,
        client_id=body.client_id,
        client_key_hash=hash_password(client_key),
        topic_pattern=body.topic_pattern,
    ))
    audit(ops, current["username"], "subscription:create", body.client_id)
    ops.commit()
    return {"client_id": body.client_id, "client_key": client_key,
            "notice": "client_key는 다시 조회할 수 없습니다. 참여 대학에 안전한 경로로 전달하세요."}


@router.get("/users", dependencies=[Depends(require_role("super_admin"))])
def list_users(ops: Session = Depends(deps.ops_db)) -> list[dict]:
    users = ops.scalars(select(User).order_by(User.id)).all()
    return [{"username": u.username, "role": u.role, "active": u.active} for u in users]


@router.post("/users")
def create_user(
    body: UserIn,
    current: dict = Depends(require_role("super_admin")),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    if body.role not in ("viewer", "admin", "super_admin"):
        raise HTTPException(status_code=400, detail="역할은 viewer/admin/super_admin")
    if ops.scalars(select(User).where(User.username == body.username)).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 계정")
    ops.add(User(username=body.username, password_hash=hash_password(body.password),
                 role=body.role))
    audit(ops, current["username"], "user:create", f"{body.username}({body.role})")
    ops.commit()
    return {"username": body.username, "role": body.role}


@router.get("/mappings/resolve")
def resolve_mapping(
    namespace: str,
    pseudo_id: str,
    current: dict = Depends(require_role("super_admin")),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """가명 ID → 원 식별자 재식별 — 발주기관 전용(SFR-004/007). 감사 로그 필수."""
    from anbu_api.pseudonym.mapping_store import MappingStore

    original = MappingStore(ops).resolve(namespace, pseudo_id)
    audit(ops, current["username"], "mapping:resolve",
          f"{namespace}:{pseudo_id} -> {'hit' if original else 'miss'}")
    ops.commit()
    if original is None:
        raise HTTPException(status_code=404, detail="매핑을 찾을 수 없습니다")
    return {"namespace": namespace, "pseudo_id": pseudo_id, "original_id": original}


@router.get("/audit", dependencies=[Depends(require_role("super_admin"))])
def list_audit(ops: Session = Depends(deps.ops_db)) -> list[dict]:
    logs = ops.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(50)
    ).all()
    return [
        {"username": a.username, "action": a.action, "detail": a.detail,
         "at": iso_kst(a.created_at)}
        for a in logs
    ]
