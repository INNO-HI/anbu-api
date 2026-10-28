"""개발·테스트용 합성 데이터 생성기(결정적, rng_seed 고정 시 항상 동일).

여기서 생성되는 이름·연락처·주소·메모는 모두 **가상의 값**이다. 가명처리(SFR-004)·
화면 마스킹(SFR-007)·자유기술 정밀 가명처리(SFR-010)를 검증하기 위해 직접식별자와
식별 가능 패턴(전화번호, 생년, 가족 관계, 희귀 병명 등)을 의도적으로 포함한다.
운영 서버에서는 절대 실행하지 않는다.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from anbu_api.models.accum import (
    Alert,
    AmiUsageA,
    AmiUsageB,
    CareRecord,
    Device,
    LedRawLog,
    Subject,
)

_NAMES = ["김영희", "박철수", "이순자", "최갑돌", "정말순", "강복례",
          "윤덕수", "한금자", "오병철", "서점례", "임만수", "조옥분"]
_GUARDIANS = [("박미숙", "딸"), ("김대성", "아들"), ("이은주", "며느리"), ("최민규", "손자")]
_EMD = ["애월읍", "한림읍", "조천읍", "구좌읍", "남원읍",
        "표선면", "성산읍", "대정읍", "일도이동", "이도일동"]
_ROOMS = ["안방", "거실", "주방", "화장실"]
_LEVELS = ["L1", "L2", "L3", "L4", "L5"]
_BENEFIT = ["기초수급", "차상위", "일반"]


def _gen_raw_logs(session: Session, device_id: int, day0: datetime, days: int,
                  rng: random.Random) -> int:
    """점등 중 12초 간격 1행(소등 중 무기록) 패턴의 원시 로그 생성."""
    rows = 0
    for d in range(days):
        base = day0 + timedelta(days=d)
        for _ in range(rng.randint(2, 4)):  # 하루 점등 세션 수
            start_min = rng.randint(6 * 60, 22 * 60)
            dur_min = rng.randint(5, 40)
            t = base + timedelta(minutes=start_min)
            end = t + timedelta(minutes=dur_min)
            while t < end:
                session.add(LedRawLog(device_id=device_id, logged_at=t))
                rows += 1
                t += timedelta(seconds=12)
    return rows


def seed_accum(session: Session, *, subjects: int = 6, days: int = 1,
               start: datetime | None = None, rng_seed: int = 42,
               with_ami: bool = True) -> dict:
    """누적 DB에 합성 데이터를 적재하고 건수 dict를 반환한다(commit 포함)."""
    rng = random.Random(rng_seed)
    day0 = start or datetime(2026, 10, 1, 0, 0, 0)
    counts = {"subjects": 0, "devices": 0, "raw_logs": 0,
              "care_records": 0, "alerts": 0, "ami_a": 0, "ami_b": 0}

    all_devices: list[Device] = []
    for i in range(subjects):
        name = _NAMES[i % len(_NAMES)]
        g_name, g_rel = _GUARDIANS[i % len(_GUARDIANS)]
        birth = date(1935 + (i * 3) % 26, (i % 12) + 1, (i % 27) + 1)
        emd = _EMD[i % len(_EMD)]
        g_phone = f"010-{2000 + i:04d}-{7700 + i:04d}"
        subj = Subject(
            name=name,
            phone=f"010-{1000 + i:04d}-{5600 + i:04d}",
            address_full=f"제주특별자치도 제주시 {emd} 중앙로{10 + i}길 {i + 1}",
            region_emd=emd,
            birth_date=birth,
            gender="F" if i % 2 == 0 else "M",
            guardian_name=g_name,
            guardian_phone=g_phone,
            care_worker_name="홍길동" if i % 2 else "성춘향",
            care_worker_phone="010-9999-0001",
            service_start_date=date(2025, (i % 12) + 1, 15),
            service_end_date=date(2026, 9, 30) if i == subjects - 1 else None,
            meal_level=_LEVELS[i % 5],
            cognition_level=_LEVELS[(i + 1) % 5],
            communication_level=_LEVELS[(i + 2) % 5],
            benefit_type=_BENEFIT[i % 3],
            high_risk_yn=(i % 4 == 0),
            high_risk_reason="독거·최근 낙상 이력" if i % 4 == 0 else None,
            notes=(
                f"{name} 어르신은 {birth.year}년생으로 {emd} 거주. "
                f"{g_rel} {g_name}(연락처 {g_phone})이 주 1회 방문. "
                + ("과거 희귀질환(길랑-바레 증후군) 병력 있음. " if i == 1 else "")
                + "식사는 혼자 가능하나 거동이 불편함."
            ),
        )
        session.add(subj)
        session.flush()
        counts["subjects"] += 1

        n_dev = 1 + (i % 3)
        for r in range(n_dev):
            dev = Device(
                subject_id=subj.subject_id,
                room=_ROOMS[r % len(_ROOMS)],
                device_type="LED",
                serial_no=f"LED-{subj.subject_id:03d}-{r}",
                install_date=date(2025, 3, 10),
                # i==2 첫 장비는 장애, i==3 첫 장비는 무신호(로그 없음) 시나리오
                current_status="fault" if (i == 2 and r == 0) else "normal",
            )
            session.add(dev)
            session.flush()
            all_devices.append(dev)
            counts["devices"] += 1
            if not (i == 3 and r == 0):  # 무신호 장비는 로그를 만들지 않음
                counts["raw_logs"] += _gen_raw_logs(session, dev.device_id, day0, days, rng)

        for v in range(2):
            session.add(CareRecord(
                subject_id=subj.subject_id,
                care_worker_name=subj.care_worker_name,
                visit_at=day0 + timedelta(days=v, hours=10 + i % 5),
                care_type="방문" if v == 0 else "전화",
                memo=(
                    f"{name} 어르신 댁 방문. 혈압 양호. {g_rel} {g_name}과 통화함({g_phone}). "
                    f"다음 방문은 2026년 10월 20일 예정. 어르신은 {2026 - birth.year}세."
                ),
            ))
            counts["care_records"] += 1

        if i == 0:
            session.add(Alert(
                subject_id=subj.subject_id, device_id=all_devices[0].device_id,
                alert_type="NO_LIGHT_24H",
                triggered_at=day0 + timedelta(hours=30),
                resolved_at=day0 + timedelta(hours=33),
                note="보호자 통화로 안전 확인",
            ))
            counts["alerts"] += 1
        if i == 2:
            session.add(Alert(
                subject_id=subj.subject_id,
                device_id=all_devices[-n_dev].device_id,
                alert_type="DEVICE_FAULT",
                triggered_at=day0 + timedelta(hours=5),
                resolved_at=None,
                note="센서 응답 없음",
            ))
            counts["alerts"] += 1

    if with_ami and subjects >= 2:
        subj_rows = session.query(Subject).order_by(Subject.subject_id).limit(2).all()
        for k, subj in enumerate(subj_rows):
            meter = f"JEJU-{9000 + k}"
            for h in range(days * 24):
                t = day0 + timedelta(hours=h)
                kwh = round(0.2 + rng.random() * 0.8, 3)
                session.add(AmiUsageA(meter_id=meter, subject_id=subj.subject_id,
                                      measured_at=t, kwh=kwh))
                counts["ami_a"] += 1
                # B 원천: 뒤 절반 시간대 중복 + 마지막 2시간은 B에만 존재
                if h >= days * 12:
                    session.add(AmiUsageB(meter_no=meter, subject_id=subj.subject_id,
                                          read_time=t, usage_kwh=kwh))
                    counts["ami_b"] += 1
            for h in range(2):
                t = day0 + timedelta(hours=days * 24 + h)
                session.add(AmiUsageB(meter_no=meter, subject_id=subj.subject_id,
                                      read_time=t, usage_kwh=0.5))
                counts["ami_b"] += 1

    session.commit()
    return counts
