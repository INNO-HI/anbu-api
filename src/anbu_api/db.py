"""DB 엔진·세션 관리 — 누적(accum)/전송용(transfer)/운영(ops) 3개 DB 물리 분리(SFR-004)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Literal

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from anbu_api.config import settings

DbName = Literal["accum", "transfer", "ops"]


class AccumBase(DeclarativeBase):
    """누적 DB(원본) 베이스."""


class TransferBase(DeclarativeBase):
    """전송용 DB(가명처리본) 베이스."""


class OpsBase(DeclarativeBase):
    """운영 DB(매핑·이력·계정) 베이스."""


BASES: dict[str, type[DeclarativeBase]] = {
    "accum": AccumBase,
    "transfer": TransferBase,
    "ops": OpsBase,
}

_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker] = {}


def _url_for(name: DbName) -> str:
    return getattr(settings, f"{name}_db_url")


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)


def get_engine(name: DbName) -> Engine:
    if name not in _engines:
        url = _url_for(name)
        _ensure_sqlite_dir(url)
        _engines[name] = create_engine(url, pool_pre_ping=True, future=True)
    return _engines[name]


def get_session(name: DbName) -> Session:
    if name not in _sessionmakers:
        _sessionmakers[name] = sessionmaker(bind=get_engine(name), future=True)
    return _sessionmakers[name]()


@contextmanager
def session_scope(name: DbName) -> Iterator[Session]:
    """commit/rollback을 보장하는 세션 컨텍스트."""
    session = get_session(name)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(names: tuple[DbName, ...] = ("accum", "transfer", "ops")) -> None:
    """모델 메타데이터 기준으로 테이블을 생성한다(개발·초기 구축용)."""
    import anbu_api.models  # noqa: F401  # 모델 등록

    for name in names:
        BASES[name].metadata.create_all(get_engine(name))


def make_session(engine: Engine) -> Session:
    """임의 엔진에 바인딩된 세션(테스트용)."""
    return Session(engine, future=True)
