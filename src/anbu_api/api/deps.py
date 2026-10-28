"""FastAPI 세션 의존성 — 테스트에서 dependency_overrides로 교체한다."""
from __future__ import annotations

from typing import Iterator

from sqlalchemy.orm import Session

from anbu_api.db import get_session


def accum_db() -> Iterator[Session]:
    session = get_session("accum")
    try:
        yield session
    finally:
        session.close()


def transfer_db() -> Iterator[Session]:
    session = get_session("transfer")
    try:
        yield session
    finally:
        session.close()


def ops_db() -> Iterator[Session]:
    session = get_session("ops")
    try:
        yield session
    finally:
        session.close()
