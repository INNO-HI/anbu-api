"""SFR-010 자유기술 가명처리·재식별 시험·추가검수 테스트."""
from sqlalchemy import select

from anbu_api.freetext.pipeline import apply_memo_pseudonymization
from anbu_api.freetext.pseudonymizer import FreeTextPseudonymizer, build_known_names
from anbu_api.freetext.reident_test import run_reident_test, write_report
from anbu_api.freetext.review import build_review_sheet, flag_risks, write_review_record
from anbu_api.models.transfer import TCareRecord
from anbu_api.pseudonym.pipeline import run_full


def test_pseudonymizer_masks_identifiers():
    p = FreeTextPseudonymizer(known_names=["김영희", "박미숙"])
    text = ("김영희 어르신은 1938년생으로 애월읍 중앙로10길 1 거주. "
            "딸 박미숙(010-2000-7700)이 주 1회 방문. 어르신은 88세. "
            "다음 방문은 2026년 10월 20일 예정.")
    result = p.pseudonymize(text)
    masked = result.text
    assert "김영희" not in masked and "박미숙" not in masked
    assert "010-2000-7700" not in masked
    assert "1938년생" not in masked and "1930년대생" in masked
    assert "88세" not in masked and "85세 이상" in masked
    assert "중앙로10길 1" not in masked
    assert "10월 20일" not in masked and "2026년 10월" in masked
    kinds = {r["type"] for r in result.replacements}
    assert {"이름", "전화번호", "생년", "나이"} <= kinds


def test_pseudonymizer_masks_rrn_and_rare_disease():
    p = FreeTextPseudonymizer()
    result = p.pseudonymize("주민번호 380115-2345678. 길랑-바레 증후군 병력 있음.")
    assert "380115-2345678" not in result.text
    assert "길랑-바레" not in result.text  # 특이정보 문장 삭제


def test_pseudonymizer_masks_unknown_name_with_suffix():
    p = FreeTextPseudonymizer()  # 사전에 없는 이름도 호칭 패턴으로 처리
    result = p.pseudonymize("조옥분 어르신 댁 방문함.")
    assert "조옥분" not in result.text


def test_apply_memo_pipeline(seeded_accum, transfer_session, ops_session):
    run_full(seeded_accum, transfer_session, ops_session)
    updated = apply_memo_pseudonymization(seeded_accum, transfer_session, ops_session)
    assert updated == 8  # 대상자 4명 × 돌봄 기록 2건

    memos = transfer_session.scalars(
        select(TCareRecord.memo_pseudo).where(TCareRecord.memo_pseudo.is_not(None))
    ).all()
    assert len(memos) == 8
    # 가명처리본에 원본 이름·전화번호가 없다
    names = build_known_names(seeded_accum)
    for memo in memos:
        assert not any(n in memo for n in names)
        assert "010-" not in memo


def test_reident_test_reports_counts_only(seeded_accum, transfer_session, ops_session, tmp_path):
    run_full(seeded_accum, transfer_session, ops_session)
    apply_memo_pseudonymization(seeded_accum, transfer_session, ops_session)

    result = run_reident_test(seeded_accum, transfer_session)
    assert result["memo_count"] == 8
    assert 0.0 <= result["narrowed_to_one_rate"] <= 1.0
    # 결과는 비율·건수만 — 개인 식별 내용 없음
    assert all(isinstance(v, (int, float, str)) for v in result.values())

    report = write_report(result, str(tmp_path / "재식별시험결과서.md"))
    content = open(report, encoding="utf-8").read()
    assert "재식별 시험 결과서" in content
    assert "비율·건수로만" in content


def test_review_sheet_and_record(seeded_accum, transfer_session, ops_session, tmp_path):
    run_full(seeded_accum, transfer_session, ops_session)
    apply_memo_pseudonymization(seeded_accum, transfer_session, ops_session)

    sheet = build_review_sheet(transfer_session, str(tmp_path / "검수시트.csv"))
    assert sheet["total"] == 8
    assert sheet["included"] == 8  # 전수 검수 기본

    record = write_review_record(sheet, str(tmp_path / "추가검수기록.md"), method="전수")
    content = open(record, encoding="utf-8").read()
    assert "추가검수 기록" in content


def test_flag_risks():
    assert "잔존 숫자열" in flag_risks("연락처 뒷자리 5678901")
    assert flag_risks("오늘 혈압 정상.") == []
    # 성명 의심 휴리스틱은 과탐 허용(검수 안전측) — '특이사항'도 플래그될 수 있다
    assert "성명 의심" in flag_risks("김영희 방문")
