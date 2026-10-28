"""원 식별자 ↔ 가명 식별자 매핑 저장소(SFR-004).

요구사항 충족 방식:
  - "무작위 또는 비밀키 기반 가명 식별자 치환(단순 해시 미사용)"
    → 가명 ID는 secrets 기반 무작위 토큰. 전송본만으로는 역산 불가.
  - "매핑 테이블은 암호화해 원본과 분리 보관"
    → 원 식별자는 Fernet 암호문으로만 저장(운영 DB, 원본·전송용과 분리).
  - 재실행 안정성: HMAC-SHA256 lookup_hash(비밀키 기반)로 기존 매핑을 복호화 없이
    조회해, 같은 원 식별자는 항상 같은 가명 ID를 받는다(테이블 간 조인 유지).
  - 재식별(resolve)은 발주기관 전용(SFR-007: super_admin API에서만 호출).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.config import settings
from anbu_api.models.ops import PseudonymMapping

NAMESPACES = ("subject", "device", "meter")


def _derive_fernet_key(secret: str) -> bytes:
    """Fernet 키 미지정 시 비밀키에서 유도(urlsafe base64 32바이트)."""
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())


class MappingStore:
    """운영 DB 세션에 바인딩된 매핑 저장소. commit은 호출측(파이프라인) 책임."""

    def __init__(
        self,
        ops_session: Session,
        *,
        secret_key: str | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self.session = ops_session
        self._secret = (secret_key or settings.pseudonym_secret_key).encode("utf-8")
        key = encryption_key or settings.mapping_encryption_key
        self._fernet = Fernet(key.encode() if key else _derive_fernet_key(self._secret.decode()))
        self._cache: dict[tuple[str, str], str] = {}

    def _lookup_hash(self, namespace: str, original_id: str) -> str:
        msg = f"{namespace}:{original_id}".encode("utf-8")
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def get_or_create(self, namespace: str, original_id: str | int) -> str:
        """원 식별자의 가명 ID를 반환한다(없으면 무작위 토큰 발급·암호화 저장)."""
        original = str(original_id)
        cache_key = (namespace, original)
        if cache_key in self._cache:
            return self._cache[cache_key]

        lookup = self._lookup_hash(namespace, original)
        row = self.session.scalars(
            select(PseudonymMapping).where(
                PseudonymMapping.namespace == namespace,
                PseudonymMapping.lookup_hash == lookup,
            )
        ).first()
        if row is None:
            row = PseudonymMapping(
                namespace=namespace,
                lookup_hash=lookup,
                original_encrypted=self._fernet.encrypt(original.encode("utf-8")).decode("ascii"),
                pseudo_id=secrets.token_hex(16),
            )
            self.session.add(row)
            self.session.flush()
        self._cache[cache_key] = row.pseudo_id
        return row.pseudo_id

    def resolve(self, namespace: str, pseudo_id: str) -> str | None:
        """가명 ID → 원 식별자 복호화. 발주기관 전용 기능(감사 로그 필수)."""
        row = self.session.scalars(
            select(PseudonymMapping).where(
                PseudonymMapping.namespace == namespace,
                PseudonymMapping.pseudo_id == pseudo_id,
            )
        ).first()
        if row is None:
            return None
        return self._fernet.decrypt(row.original_encrypted.encode("ascii")).decode("utf-8")
