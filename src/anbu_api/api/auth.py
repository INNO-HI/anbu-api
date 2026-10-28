"""인증·3단계 권한(SFR-007): super_admin(발주기관 전용) / admin(운영) / viewer(조회).

- 비밀번호: PBKDF2-SHA256(표준 라이브러리) 해시.
- 토큰: JWT(HS256), 만료 jwt_expire_minutes.
- 매핑 테이블 재식별 등 발주기관 전용 기능은 super_admin만 접근(권한 정의서 참조).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta, timezone, datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.api import deps
from anbu_api.config import settings
from anbu_api.models.ops import User

ROLE_LEVEL = {"viewer": 1, "admin": 2, "super_admin": 3}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

_PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iters)
    ).hex()
    return secrets.compare_digest(candidate, digest)


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def authenticate(ops_session: Session, username: str, password: str) -> User | None:
    user = ops_session.scalars(select(User).where(User.username == username)).first()
    if user and user.active and verify_password(password, user.password_hash):
        return user
    return None


def get_current_user(
    token: str = Depends(oauth2_scheme),
    ops: Session = Depends(deps.ops_db),
) -> dict:
    """토큰 검증 + 계정 활성 여부 확인."""
    cred_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise cred_error
    username = payload.get("sub")
    user = ops.scalars(select(User).where(User.username == username)).first()
    if user is None or not user.active:
        raise cred_error
    return {"username": user.username, "role": user.role}


def require_role(min_role: str):
    """역할 수준 검사 의존성 — viewer < admin < super_admin."""

    def checker(current: dict = Depends(get_current_user)) -> dict:
        if ROLE_LEVEL.get(current["role"], 0) < ROLE_LEVEL[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"권한 부족: {min_role} 이상 필요",
            )
        return current

    return checker
