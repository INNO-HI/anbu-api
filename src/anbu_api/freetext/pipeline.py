"""자유기술 가명처리 적용 파이프라인(SFR-010).

전송용 돌봄 기록(t_care_records)의 memo_pseudo를 채운다. 발주기관이 자유기술
전송을 허용하고 SFR-010을 채택한 경우에만 실행하며, 추가 검수(review 모듈)를
거친 뒤에 전송한다.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from anbu_api.models.accum import CareRecord
from anbu_api.models.transfer import TCareRecord
from anbu_api.pseudonym.mapping_store import MappingStore
from anbu_api.freetext.pseudonymizer import FreeTextPseudonymizer, build_known_names


def apply_memo_pseudonymization(
    accum_session: Session,
    transfer_session: Session,
    ops_session: Session,
    *,
    pseudonymizer: FreeTextPseudonymizer | None = None,
) -> int:
    """원본 돌봄 기록의 memo를 정밀 가명처리해 전송용 행에 채운다(commit 포함).

    전송용 행과의 대응은 (가명 대상자 ID, 방문 시각)으로 찾는다 — 전송용 PK는
    원본과 무관한 새 키이므로 원본 일련번호로는 연결하지 않는다.
    """
    p = pseudonymizer or FreeTextPseudonymizer(build_known_names(accum_session))
    store = MappingStore(ops_session)
    updated = 0

    for rec in accum_session.scalars(
        select(CareRecord).where(CareRecord.memo.is_not(None))
    ).all():
        pseudo_subject = store.get_or_create("subject", rec.subject_id)
        target = transfer_session.scalars(
            select(TCareRecord).where(
                TCareRecord.pseudo_subject_id == pseudo_subject,
                TCareRecord.visit_at == rec.visit_at,
            )
        ).first()
        if target is None:
            continue
        target.memo_pseudo = p.pseudonymize(rec.memo).text
        updated += 1

    transfer_session.commit()
    ops_session.commit()
    return updated
