"""추가 검수(SFR-010): 자동 처리 뒤 사람이 메모를 읽고 남은 식별 위험을 점검한다.

- build_review_sheet: 검수 대상 시트(CSV) 생성. 위험 신호가 있는 메모를 플래그해
  특이 메모를 따로 재검수할 수 있게 한다.
- write_review_record: 검수 방식·과정·결과를 추가검수 기록으로 남긴다
  (발주기관 비정형데이터 추가검수 결과서 작성 지원).
"""
from __future__ import annotations

import csv
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.models.transfer import TCareRecord
from anbu_api.timeutil import iso_kst, now_kst

# 잔존 위험 신호: 남은 숫자열(연락처 파편), 호칭 없는 한글 성명 의심 패턴, 직업/병명 단서
_RISK_CHECKS: list[tuple[str, re.Pattern]] = [
    ("잔존 숫자열", re.compile(r"\d{4,}")),
    ("성명 의심", re.compile(r"[김이박최정강조윤장임한오서신권황안송류전홍][가-힣]{2}(?![가-힣])")),
    ("병명·직업 단서", re.compile(r"(병력|진단|직업|교사|어부|해녀)")),
]


def flag_risks(memo: str) -> list[str]:
    """메모 1건의 잔존 식별 위험 신호 목록을 반환한다."""
    return [name for name, pattern in _RISK_CHECKS if pattern.search(memo)]


def build_review_sheet(
    transfer_session: Session, out_path: str, *, sample_every: int = 1
) -> dict:
    """검수 시트(CSV)를 생성한다. sample_every=1이면 전수, n이면 n건당 1건 표본.

    위험 플래그가 있는 메모는 표본 여부와 무관하게 항상 포함한다(특이 메모 재검수).
    """
    rows = transfer_session.scalars(
        select(TCareRecord).where(TCareRecord.memo_pseudo.is_not(None))
    ).all()

    total = len(rows)
    included = 0
    flagged = 0
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["전송키", "방문시각", "가명처리 메모", "위험 신호", "검수 결과", "검수자"])
        for idx, rec in enumerate(rows):
            risks = flag_risks(rec.memo_pseudo or "")
            if risks:
                flagged += 1
            if risks or idx % sample_every == 0:
                included += 1
                writer.writerow([
                    rec.id, rec.visit_at, rec.memo_pseudo,
                    "; ".join(risks), "", "",
                ])
    return {"total": total, "included": included, "flagged": flagged, "path": out_path}


def write_review_record(
    sheet_stats: dict,
    out_path: str,
    *,
    method: str = "전수",
    reviewed: int | None = None,
    resolved: int | None = None,
) -> str:
    """추가검수 기록을 생성한다(검수 방식·과정·결과)."""
    lines = [
        "# 비정형데이터 추가검수 기록 (SFR-010)",
        "",
        f"- 작성 일시: {iso_kst(now_kst())} (KST)",
        f"- 검수 방식: {method}",
        "- 과정: 자동(규칙 기반) 가명처리 → 검수 시트 생성 → 사람 검수 →",
        "  위험 신호 플래그 메모는 별도 재검수 → 조치(일반화 강화·문장 삭제) 후 재생성",
        "",
        "## 결과",
        "",
        "| 항목 | 건수 |",
        "|---|---|",
        f"| 전체 가명처리 메모 | {sheet_stats['total']} |",
        f"| 검수 대상(시트 포함) | {sheet_stats['included']} |",
        f"| 위험 신호 플래그 | {sheet_stats['flagged']} |",
        f"| 사람 검수 완료 | {reviewed if reviewed is not None else '(검수 후 기입)'} |",
        f"| 조치 완료 | {resolved if resolved is not None else '(검수 후 기입)'} |",
        "",
        f"- 검수 시트: {sheet_stats['path']}",
        "- 처리 기준: 「가명정보 처리 가이드라인」(개인정보보호위원회, 2026.3) 비정형데이터 기준",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
