"""SFR-004 가명처리 테스트 — 기준 적용, 암호화 매핑, 안정성."""
from datetime import date

from sqlalchemy import select

from anbu_api.models.ops import PseudonymMapping
from anbu_api.models.transfer import TSubject
from anbu_api.pseudonym.mapping_store import MappingStore
from anbu_api.pseudonym.pipeline import run_full
from anbu_api.pseudonym.rules import age_band, categorize_level

AS_OF = date(2026, 10, 28)


def test_age_band_rules():
    assert age_band(date(1940, 1, 1), as_of=AS_OF) == "85+"       # 86세
    assert age_band(date(1942, 12, 31), as_of=AS_OF) == "80-84"   # 83세
    assert age_band(date(1955, 1, 1), as_of=AS_OF) == "70-74"     # 71세
    assert age_band(date(1990, 1, 1), as_of=AS_OF) == "65세 미만"
    assert age_band(None, as_of=AS_OF) is None


def test_categorize_level():
    assert categorize_level("L1") == "자립"
    assert categorize_level("L3") == "부분도움"
    assert categorize_level("L5") == "전적도움"
    assert categorize_level(None) is None
    assert categorize_level("알수없음") is None  # 미지 코드는 결측 처리


def test_mapping_store_random_encrypted_stable(ops_session):
    store = MappingStore(ops_session)
    p1 = store.get_or_create("subject", 1)
    p2 = store.get_or_create("subject", 1)
    p3 = store.get_or_create("subject", 2)
    assert p1 == p2          # 같은 원 식별자 → 같은 가명 ID(조인 유지)
    assert p1 != p3
    assert len(p1) == 32     # 무작위 토큰(16바이트 hex)

    row = ops_session.scalars(select(PseudonymMapping)).first()
    assert "1" not in (row.pseudo_id,)              # 가명 ID는 원값과 무관
    assert row.original_encrypted != "1"            # 평문 저장 금지
    assert store.resolve("subject", p1) == "1"      # 발주기관 재식별 왕복
    assert store.resolve("subject", "없는값") is None

    # 새 저장소 인스턴스(재실행 가정)에서도 같은 가명 ID
    ops_session.commit()
    store2 = MappingStore(ops_session)
    assert store2.get_or_create("subject", 1) == p1


def test_run_full_applies_rules(seeded_accum, transfer_session, ops_session):
    counts = run_full(seeded_accum, transfer_session, ops_session, as_of=AS_OF)
    assert counts["subjects"] == 4
    assert counts["care_records"] == 8
    assert counts["power_usage"] == 0  # SFR-009 미수행 시 미적재

    subjects = transfer_session.scalars(select(TSubject)).all()
    for t in subjects:
        # 직접식별자 컬럼이 아예 없다(스키마 수준 차단)
        assert not hasattr(t, "name") and not hasattr(t, "phone")
        assert t.benefit_yn is None                    # 수급 구분 삭제
        assert t.service_start_ym and len(t.service_start_ym) == 7  # YYYY-MM
        assert t.meal_cat in ("자립", "부분도움", "전적도움", None)
        assert t.age_band is not None

    # 전송용 DB 어디에도 원본 이름이 없다
    from anbu_api.models.accum import Subject
    names = [s.name for s in seeded_accum.scalars(select(Subject)).all()]
    for t in subjects:
        row_text = str(vars(t))
        assert not any(name in row_text for name in names)


def test_run_full_stable_pseudo_ids(seeded_accum, transfer_session, ops_session):
    """재실행해도 가명 ID가 유지된다(매핑 저장소 안정성)."""
    run_full(seeded_accum, transfer_session, ops_session, as_of=AS_OF)
    first = {t.pseudo_subject_id for t in transfer_session.scalars(select(TSubject)).all()}
    run_full(seeded_accum, transfer_session, ops_session, as_of=AS_OF)
    second = {t.pseudo_subject_id for t in transfer_session.scalars(select(TSubject)).all()}
    assert first == second


def test_memo_excluded_by_default(seeded_accum, transfer_session, ops_session):
    """자유기술은 기본 전송 제외(SFR-010 채택 시에만 포함)."""
    run_full(seeded_accum, transfer_session, ops_session, as_of=AS_OF)
    from anbu_api.models.transfer import TCareRecord

    memos = transfer_session.scalars(select(TCareRecord.memo_pseudo)).all()
    assert all(m is None for m in memos)
