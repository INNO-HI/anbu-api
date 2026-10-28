"""SFR-001 서버 진단 · SFR-003 데이터 사전 테스트."""
import os

from anbu_api.diagnostics.server_diag import run_diagnostics, write_report
from anbu_api.dictionary.generate import generate_dictionary


def test_run_diagnostics_keys(seeded_accum):
    diag = run_diagnostics(seeded_accum, data_dir=".")
    assert {"hardware", "os", "storage", "network", "security", "db", "growth"} <= set(diag)
    assert diag["hardware"]["cpu_cores_logical"] >= 1
    assert diag["storage"]["free_gb"] > 0
    assert diag["db"]["tables"]["subjects"] == 4
    g = diag["growth"]
    assert g["total_raw_rows"] > 0
    assert g["daily_rows_estimate"] > 0
    assert g["days_until_full"] is None or g["days_until_full"] > 0


def test_spec_check_against_rfp(seeded_accum):
    """측정치가 과업지시서 명시 사양(HPE DL360 Gen11 등)과 대조된다."""
    diag = run_diagnostics(seeded_accum, data_dir=".")
    checks = diag["spec_check"]
    items = {c["항목"] for c in checks}
    assert {"CPU 논리 코어", "메모리(GB)", "GPU"} <= items
    assert all(isinstance(c["적합"], bool) for c in checks)


def test_write_diag_report(seeded_accum, tmp_path):
    diag = run_diagnostics(seeded_accum, data_dir=".")
    path = write_report(diag, str(tmp_path / "서버진단보고서.md"))
    content = open(path, encoding="utf-8").read()
    assert "서버 진단 보고서" in content
    assert "증설" in content
    assert "과업지시서 기준 사양 대조" in content


def test_generate_dictionary(seeded_accum, tmp_path):
    paths = generate_dictionary(str(tmp_path), accum_session=seeded_accum)
    assert len(paths) == 4  # CSV 3개 + 데이터사전.md
    md = open(os.path.join(str(tmp_path), "데이터사전.md"), encoding="utf-8").read()
    # 세 DB의 핵심 테이블이 모두 수록된다
    for table in ("subjects", "t_subjects", "pseudonym_mappings", "lighting_intervals"):
        assert f"`{table}`" in md
    # 코드·결측 표준과 이상 알림 기준, 설치 현황 반영
    assert "결측은 NULL" in md
    assert "NO_LIGHT_24H" in md
    assert "방별 센서 설치 현황" in md
    # CSV 생성 확인
    csv_content = open(os.path.join(str(tmp_path), "dictionary_accum.csv"),
                       encoding="utf-8-sig").read()
    assert "subjects" in csv_content and "birth_date" in csv_content
