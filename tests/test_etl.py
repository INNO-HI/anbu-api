"""SFR-002 ETL 테스트 — 점등 구간 파생, 상태 이력, 보존 정책."""
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from anbu_api.etl.device_status_history import infer_inactivity, sync_status
from anbu_api.etl.lighting_intervals import build_intervals
from anbu_api.etl.retention import apply_retention
from anbu_api.models.accum import (
    Device,
    DeviceStatusHistory,
    LedRawLog,
    LightingInterval,
    Subject,
)

AS_OF = datetime(2026, 10, 28, 12, 0, 0)


def _make_device(session) -> Device:
    subj = Subject(name="테스트", birth_date=date(1940, 1, 1))
    session.add(subj)
    session.flush()
    dev = Device(subject_id=subj.subject_id, room="안방")
    session.add(dev)
    session.flush()
    return dev


def test_build_intervals_splits_on_gap(accum_session):
    """12초 간격 로그 묶음 2개(10분 공백)는 구간 2개로 분리된다."""
    dev = _make_device(accum_session)
    t0 = datetime(2026, 10, 1, 9, 0, 0)
    # 세션 1: 3행(0, 12, 24초) / 세션 2: 10분 뒤 2행
    for sec in (0, 12, 24):
        accum_session.add(LedRawLog(device_id=dev.device_id, logged_at=t0 + timedelta(seconds=sec)))
    t1 = t0 + timedelta(minutes=10)
    for sec in (0, 12):
        accum_session.add(LedRawLog(device_id=dev.device_id, logged_at=t1 + timedelta(seconds=sec)))
    accum_session.commit()

    created = build_intervals(accum_session, gap_sec=60, as_of=AS_OF)
    assert created == 2

    intervals = accum_session.scalars(
        select(LightingInterval).order_by(LightingInterval.started_at)
    ).all()
    assert intervals[0].started_at == t0
    assert intervals[0].ended_at == t0 + timedelta(seconds=24)
    assert intervals[0].duration_sec == 24 + 12  # 행 주기 보정
    assert intervals[1].started_at == t1


def test_build_intervals_idempotent(accum_session):
    """재실행 시 새 로그가 없으면 구간이 추가되지 않는다."""
    dev = _make_device(accum_session)
    t0 = datetime(2026, 10, 1, 9, 0, 0)
    for sec in (0, 12, 24):
        accum_session.add(LedRawLog(device_id=dev.device_id, logged_at=t0 + timedelta(seconds=sec)))
    accum_session.commit()

    assert build_intervals(accum_session, gap_sec=60, as_of=AS_OF) == 1
    assert build_intervals(accum_session, gap_sec=60, as_of=AS_OF) == 0


def test_build_intervals_keeps_open_group(accum_session):
    """아직 점등 중일 수 있는(공백 미확정) 마지막 그룹은 확정하지 않는다."""
    dev = _make_device(accum_session)
    t0 = datetime(2026, 10, 1, 9, 0, 0)
    accum_session.add(LedRawLog(device_id=dev.device_id, logged_at=t0))
    accum_session.commit()
    # as_of가 마지막 로그에서 gap 미만 → 구간 미확정
    assert build_intervals(accum_session, gap_sec=60, as_of=t0 + timedelta(seconds=30)) == 0
    # 시간이 지나면 확정
    assert build_intervals(accum_session, gap_sec=60, as_of=t0 + timedelta(seconds=120)) == 1


def test_seeded_intervals(seeded_accum):
    """시드 데이터 전체에 대해 구간이 생성된다."""
    created = build_intervals(seeded_accum, as_of=AS_OF)
    assert created > 0
    bad = seeded_accum.scalar(
        select(func.count()).select_from(LightingInterval).where(
            LightingInterval.duration_sec <= 0
        )
    )
    assert bad == 0


def test_sync_status_appends_history(seeded_accum):
    """현재값과 이력이 다르면 이력 행이 추가되고, 재실행 시 중복되지 않는다."""
    n1 = sync_status(seeded_accum, as_of=AS_OF)
    device_count = seeded_accum.scalar(select(func.count()).select_from(Device))
    assert n1 == device_count  # 최초 실행: 전 장비 기록
    assert sync_status(seeded_accum, as_of=AS_OF) == 0  # 변경 없음


def test_infer_inactivity_marks_silent_device(seeded_accum):
    """로그가 없는 정상 장비는 '비활성'으로 전환되고 이력에 남는다."""
    changed = infer_inactivity(seeded_accum, inactive_after_hours=48, as_of=AS_OF)
    assert changed > 0
    hist = seeded_accum.scalars(
        select(DeviceStatusHistory).where(DeviceStatusHistory.source == "auto")
    ).all()
    assert all(h.status == "inactive" for h in hist)
    assert len(hist) == changed


def test_subject_overview_view(seeded_accum):
    """대상자 단위 통합 조회 뷰(SFR-002): 대상자 1행으로 장비·점등·알림·돌봄이 모인다."""
    from sqlalchemy import text

    from anbu_api.etl.views import VIEW_NAME, create_views

    build_intervals(seeded_accum, as_of=AS_OF)
    create_views(seeded_accum)

    rows = seeded_accum.execute(
        text(f"SELECT * FROM {VIEW_NAME} ORDER BY subject_id")
    ).mappings().all()
    assert len(rows) == 4
    first = rows[0]
    assert first["device_count"] >= 1
    assert first["last_lighting_at"] is not None   # 점등 이력 연계
    assert first["care_record_count"] == 2
    # 시드: subject 3(i=2)은 미해결 DEVICE_FAULT 알림 보유
    assert rows[2]["open_alert_count"] == 1


def test_retention_purges_old_raw_logs(seeded_accum):
    """보존 기간이 지난 원시 로그만 파기된다."""
    total_before = seeded_accum.scalar(select(func.count()).select_from(LedRawLog))
    # 시드 로그는 2026-10-01~02 — 27일 보존이면 전부 파기 대상(as_of=10-28 기준 cutoff=10-01 12:00)
    result = apply_retention(seeded_accum, raw_log_days=27, as_of=AS_OF)
    remaining = seeded_accum.scalar(select(func.count()).select_from(LedRawLog))
    assert result["purged_raw_logs"] + remaining == total_before
    assert result["purged_raw_logs"] > 0
    # 충분히 긴 보존 기간이면 파기 없음
    assert apply_retention(seeded_accum, raw_log_days=3650, as_of=AS_OF)["purged_raw_logs"] == 0
