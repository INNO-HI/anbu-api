"""참여 대학 수신 확인 REST 수집(SFR-005 제공 실적) — 구독 client_key로 인증."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.api import deps
from anbu_api.api.auth import verify_password
from anbu_api.models.ops import Subscription
from anbu_api.transport.history import record_receipt

router = APIRouter(tags=["receipts"])


class ReceiptIn(BaseModel):
    topic: str
    record_count: int


@router.post("/api/receipts")
def post_receipt(
    body: ReceiptIn,
    x_client_id: str = Header(...),
    x_client_key: str = Header(...),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    sub = ops.scalars(
        select(Subscription).where(
            Subscription.client_id == x_client_id,
            Subscription.active == True,  # noqa: E712
        )
    ).first()
    if sub is None or not sub.client_key_hash or not verify_password(
        x_client_key, sub.client_key_hash
    ):
        raise HTTPException(status_code=401, detail="구독 인증 실패")
    record_receipt(ops, sub.university, sub.client_id, body.topic, body.record_count)
    ops.commit()
    return {"ok": True}
