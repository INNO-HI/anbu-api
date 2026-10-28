"""데이터 사전 생성(SFR-003).

세 DB(누적/전송용/운영)의 모델 메타데이터에서 테이블·필드 정의서를 생성하고,
코드값·결측 표준, 방별 센서 설치 현황, 이상 알림 기준을 데이터 사전에 반영한다.
산출물: 데이터사전.md + DB별 테이블·필드 정의 CSV.
"""
from __future__ import annotations

import csv
import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anbu_api.db import BASES
from anbu_api.dictionary.codes import ALERT_RULES, CODE_DEFINITIONS, MISSING_VALUE_STANDARD
from anbu_api.timeutil import iso_kst, now_kst

_DB_TITLES = {
    "accum": "누적 DB (원본 — 반출 금지)",
    "transfer": "전송용 DB (가명처리본 7개 테이블)",
    "ops": "운영 DB (매핑·이력·계정)",
}


def _iter_columns(db_name: str):
    for table in BASES[db_name].metadata.sorted_tables:
        for col in table.columns:
            yield {
                "db": db_name,
                "table": table.name,
                "column": col.name,
                "type": str(col.type),
                "nullable": "Y" if col.nullable else "N",
                "pk": "Y" if col.primary_key else "",
                "comment": col.comment or "",
            }


def _write_csv(db_name: str, out_dir: str) -> str:
    path = os.path.join(out_dir, f"dictionary_{db_name}.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["db", "table", "column", "type", "nullable", "pk", "comment"]
        )
        writer.writeheader()
        for row in _iter_columns(db_name):
            writer.writerow(row)
    return path


def _sensor_layout(accum_session: Session) -> list[tuple[str, int]]:
    """방별 센서 설치 현황(설치 위치별 대수)."""
    from anbu_api.models.accum import Device

    rows = accum_session.execute(
        select(Device.room, func.count()).group_by(Device.room).order_by(Device.room)
    ).all()
    return [(room or "(미지정)", int(n)) for room, n in rows]


def generate_dictionary(
    out_dir: str, *, accum_session: Session | None = None
) -> list[str]:
    """데이터 사전 일체를 out_dir에 생성하고 생성 파일 경로 목록을 반환한다."""
    os.makedirs(out_dir, exist_ok=True)
    import anbu_api.models  # noqa: F401  # 메타데이터 등록

    paths = [_write_csv(db, out_dir) for db in ("accum", "transfer", "ops")]

    lines = [
        "# 데이터 사전 (SFR-003)",
        "",
        f"- 생성 일시: {iso_kst(now_kst())} (KST)",
        f"- 결측 표준: {MISSING_VALUE_STANDARD}",
        "- 시각 표준: 모든 시각은 한국 표준시(KST) naive datetime",
        "",
    ]

    for db in ("accum", "transfer", "ops"):
        lines += [f"## {_DB_TITLES[db]}", ""]
        current_table = None
        for row in _iter_columns(db):
            if row["table"] != current_table:
                current_table = row["table"]
                lines += [
                    f"### `{current_table}`",
                    "",
                    "| 필드 | 타입 | NULL | PK | 설명 |",
                    "|---|---|---|---|---|",
                ]
            lines.append(
                f"| {row['column']} | {row['type']} | {row['nullable']} "
                f"| {row['pk']} | {row['comment']} |"
            )
        lines.append("")

    lines += ["## 코드 정의", ""]
    for field, codes in CODE_DEFINITIONS.items():
        lines += [f"### {field}", "", "| 코드 | 의미 |", "|---|---|"]
        lines += [f"| {code} | {meaning} |" for code, meaning in codes.items()]
        lines.append("")

    lines += ["## 이상 알림 판정 기준", "", "| 알림 | 기준 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in ALERT_RULES.items()]
    lines.append("")

    if accum_session is not None:
        lines += ["## 방별 센서 설치 현황", "", "| 설치 위치 | 센서 수 |", "|---|---|"]
        lines += [f"| {room} | {n} |" for room, n in _sensor_layout(accum_session)]
        lines.append("")

    md_path = os.path.join(out_dir, "데이터사전.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    paths.append(md_path)
    return paths
