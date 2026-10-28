"""대상자 단위 통합 조회 뷰(SFR-002) — 테이블별로 흩어진 데이터를 대상자 1행으로.

sqlite(개발)·MariaDB 10.11(운영) 공통 문법만 사용한다.
init_db() 시 자동 생성되며, 운영 DDL(db/migrations/001)에도 포함된다.
"""
from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

VIEW_NAME = "v_subject_overview"

VIEW_SELECT = """
SELECT s.subject_id,
       s.region_emd,
       s.gender,
       s.high_risk_yn,
       (SELECT COUNT(*) FROM devices d
         WHERE d.subject_id = s.subject_id)                       AS device_count,
       (SELECT MAX(li.ended_at)
          FROM lighting_intervals li
          JOIN devices d2 ON li.device_id = d2.device_id
         WHERE d2.subject_id = s.subject_id)                      AS last_lighting_at,
       (SELECT COUNT(*) FROM alerts a
         WHERE a.subject_id = s.subject_id
           AND a.resolved_at IS NULL)                             AS open_alert_count,
       (SELECT COUNT(*) FROM care_records c
         WHERE c.subject_id = s.subject_id)                       AS care_record_count
  FROM subjects s
""".strip()


def create_views(bind: Engine | Session) -> None:
    """누적 DB에 통합 조회 뷰를 (재)생성한다."""
    ddl_drop = text(f"DROP VIEW IF EXISTS {VIEW_NAME}")
    ddl_create = text(f"CREATE VIEW {VIEW_NAME} AS {VIEW_SELECT}")
    if isinstance(bind, Session):
        bind.execute(ddl_drop)
        bind.execute(ddl_create)
        bind.commit()
    else:
        with bind.begin() as conn:
            conn.execute(ddl_drop)
            conn.execute(ddl_create)
