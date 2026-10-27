"""가명 식별자 생성 (SFR-004).

과업지시서 요구사항:
  - 대상자/장비/계량기 식별자를 "무작위 또는 비밀키 기반 가명 식별자"로 치환
  - "단순 해시 방식은 사용하지 않는다"
  - 원 식별자 ↔ 가명 식별자 매핑 테이블은 암호화하여 원본과 분리 보관

이 모듈은 두 가지 방식을 제공한다.
  1) random_token(): 무작위 토큰 발급(권장) — 대응은 암호화 매핑 테이블에만 보관
  2) keyed_token(): 비밀키 기반(HMAC) 결정적 치환 — 키는 발주기관 전용 보관

둘 다 키 없는 단순 해시(sha256(id) 등)와 달리 비밀키/무작위성을 전제로 하여
전송본만으로는 원 식별자를 역추적할 수 없게 한다.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

__all__ = ["random_token", "keyed_token"]


def random_token(nbytes: int = 16) -> str:
    """무작위 가명 식별자. 원본과의 대응은 호출측이 암호화 매핑 테이블에 저장한다."""
    return secrets.token_hex(nbytes)


def keyed_token(original_id: str, secret_key: str, namespace: str = "") -> str:
    """비밀키 기반 결정적 가명 식별자(HMAC-SHA256).

    같은 (original_id, namespace)는 항상 같은 토큰으로 매핑되어 테이블 간 조인을
    유지하면서도, secret_key 없이는 역산이 불가능하다. namespace로 대상자/장비/
    계량기 등 식별자 종류를 분리한다.
    """
    if not secret_key:
        raise ValueError("secret_key가 필요합니다 (발주기관 전용 보관).")
    msg = f"{namespace}:{original_id}".encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return digest[:32]
