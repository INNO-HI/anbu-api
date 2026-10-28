"""공통 픽스처 — in-memory sqlite 3개 DB(누적/전송용/운영) + 시드 데이터."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import anbu_api.models  # noqa: F401  # 메타데이터 등록
from anbu_api import seed
from anbu_api.db import AccumBase, OpsBase, TransferBase


def _memory_session(base) -> Session:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    base.metadata.create_all(engine)
    return Session(engine, future=True)


@pytest.fixture
def accum_session():
    s = _memory_session(AccumBase)
    yield s
    s.close()


@pytest.fixture
def transfer_session():
    s = _memory_session(TransferBase)
    yield s
    s.close()


@pytest.fixture
def ops_session():
    s = _memory_session(OpsBase)
    yield s
    s.close()


@pytest.fixture
def seeded_accum(accum_session):
    """대상자 4명·1일치 합성 데이터가 적재된 누적 DB 세션."""
    seed.seed_accum(accum_session, subjects=4, days=1)
    return accum_session
