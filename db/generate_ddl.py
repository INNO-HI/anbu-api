"""운영(MariaDB)용 DDL 생성 — 모델 메타데이터에서 db/migrations/*.sql 산출.

실행: .venv/bin/python db/generate_ddl.py
sqlite 개발 환경과 운영 MariaDB 스키마의 단일 원천은 SQLAlchemy 모델이며,
이 스크립트는 그로부터 MariaDB 방언 DDL을 뽑아낸다.
"""
from __future__ import annotations

import os

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

import anbu_api.models  # noqa: F401  # 메타데이터 등록
from anbu_api.db import BASES

_FILES = {
    "accum": ("001_accum_schema.sql", "누적 DB (원본 — 반출 금지)"),
    "transfer": ("002_transfer_schema.sql", "전송용 DB (가명처리본 7개 테이블)"),
    "ops": ("003_ops_schema.sql", "운영 DB (매핑·이력·계정)"),
}


def main() -> None:
    out_dir = os.path.join(os.path.dirname(__file__), "migrations")
    os.makedirs(out_dir, exist_ok=True)
    dialect = mysql.dialect()

    for db_name, (filename, title) in _FILES.items():
        lines = [
            f"-- {title}",
            "-- anbu-api 모델에서 자동 생성 (db/generate_ddl.py) — 직접 수정하지 말 것",
            "SET NAMES utf8mb4;",
            "",
        ]
        for table in BASES[db_name].metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
            # MariaDB(10.11) 기본: InnoDB + utf8mb4
            lines.append(f"{ddl} ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;")
            for index in table.indexes:
                lines.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
            lines.append("")
        if db_name == "accum":
            from anbu_api.etl.views import VIEW_NAME, VIEW_SELECT

            lines += [
                "-- 대상자 단위 통합 조회 뷰 (SFR-002)",
                f"DROP VIEW IF EXISTS {VIEW_NAME};",
                f"CREATE VIEW {VIEW_NAME} AS {VIEW_SELECT};",
                "",
            ]
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"생성: {path}")


if __name__ == "__main__":
    main()
