"""서버 진단(SFR-001).

다향관 서버의 하드웨어(GPU 포함)·OS·DB·저장 용량·네트워크·보안 설정 현황을
수집하고, 데이터 누적 증가량 기준으로 저장 용량 여유와 증설 필요 시점을 산정한다.
산출물: 서버 진단 보고서(write_report).
"""
from __future__ import annotations

import platform
import shutil
import socket
import subprocess
from datetime import timedelta

import psutil
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from anbu_api.timeutil import iso_kst, now_kst

# 원시 로그 1행의 추정 저장 비용(행 + 인덱스), 보수적으로 산정
RAW_LOG_ROW_BYTES = 80


def _detect_gpu() -> str:
    """GPU 존재 여부 탐지(nvidia-smi → macOS system_profiler 순). 실패 시 '미탐지'."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().splitlines()[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(
                ["system_profiler", "SPDisplaysDataType", "-detailLevel", "mini"],
                capture_output=True, text=True, timeout=15,
            )
            for line in out.stdout.splitlines():
                if "Chipset Model" in line:
                    return line.split(":", 1)[1].strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return "미탐지"


def _listening_ports() -> list[int]:
    """LISTEN 중인 포트 목록(보안 설정 현황). 권한 부족 시 빈 목록."""
    try:
        conns = psutil.net_connections(kind="inet")
        return sorted({c.laddr.port for c in conns if c.status == psutil.CONN_LISTEN})
    except (psutil.AccessDenied, PermissionError):
        return []


def estimate_growth(accum_session: Session, free_bytes: int) -> dict:
    """원시 로그 누적 추이로 일일 증가량과 증설 필요 시점을 산정한다."""
    from anbu_api.models.accum import LedRawLog

    total_rows = accum_session.scalar(select(func.count()).select_from(LedRawLog)) or 0
    first = accum_session.scalar(select(func.min(LedRawLog.logged_at)))
    last = accum_session.scalar(select(func.max(LedRawLog.logged_at)))

    if total_rows and first and last and last > first:
        span_days = max((last - first).total_seconds() / 86400, 1.0)
        daily_rows = total_rows / span_days
    else:
        daily_rows = 40_000  # 과업지시서 기준치(2026.6, 센서 58개): 일평균 약 4만 행

    daily_bytes = daily_rows * RAW_LOG_ROW_BYTES
    days_until_full = int(free_bytes / daily_bytes) if daily_bytes else None
    projected = (
        iso_kst(now_kst() + timedelta(days=days_until_full)) if days_until_full else None
    )
    return {
        "total_raw_rows": int(total_rows),
        "daily_rows_estimate": int(daily_rows),
        "daily_mb_estimate": round(daily_bytes / 1_048_576, 2),
        "days_until_full": days_until_full,
        "projected_full_date": projected,
    }


def run_diagnostics(accum_session: Session | None = None, *, data_dir: str = ".") -> dict:
    """서버 진단을 수행하고 결과 dict를 반환한다."""
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(data_dir)

    diag: dict = {
        "collected_at": iso_kst(now_kst()),
        "hardware": {
            "cpu_model": platform.processor() or platform.machine(),
            "cpu_cores_physical": psutil.cpu_count(logical=False),
            "cpu_cores_logical": psutil.cpu_count(logical=True),
            "memory_total_gb": round(vm.total / 1_073_741_824, 1),
            "memory_available_gb": round(vm.available / 1_073_741_824, 1),
            "gpu": _detect_gpu(),
        },
        "os": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "hostname": socket.gethostname(),
        },
        "storage": {
            "data_dir": data_dir,
            "total_gb": round(disk.total / 1_073_741_824, 1),
            "used_gb": round(disk.used / 1_073_741_824, 1),
            "free_gb": round(disk.free / 1_073_741_824, 1),
            "used_pct": round(disk.used / disk.total * 100, 1),
        },
        "network": {
            "interfaces": sorted(psutil.net_if_addrs().keys()),
        },
        "security": {
            "listening_ports": _listening_ports(),
        },
    }

    if accum_session is not None:
        from anbu_api.db import BASES

        counts = {}
        for table in BASES["accum"].metadata.sorted_tables:
            n = accum_session.execute(
                select(func.count()).select_from(table)
            ).scalar()
            counts[table.name] = int(n or 0)
        diag["db"] = {"tables": counts}
        diag["growth"] = estimate_growth(accum_session, disk.free)
    else:
        diag["growth"] = {
            "daily_rows_estimate": 40_000,
            "daily_mb_estimate": round(40_000 * RAW_LOG_ROW_BYTES / 1_048_576, 2),
            "note": "DB 미연결 — 과업지시서 기준치 사용",
        }
    return diag


def write_report(diag: dict, out_path: str) -> str:
    """서버 진단 보고서(SFR-001 산출물)를 markdown으로 생성한다."""
    hw, os_, st = diag["hardware"], diag["os"], diag["storage"]
    lines = [
        "# 서버 진단 보고서 (SFR-001)",
        "",
        f"- 진단 일시: {diag['collected_at']} (KST)",
        f"- 호스트: {os_['hostname']}",
        "",
        "## 1. 하드웨어",
        f"- CPU: {hw['cpu_model']} (물리 {hw['cpu_cores_physical']}코어 / 논리 {hw['cpu_cores_logical']}코어)",
        f"- 메모리: 총 {hw['memory_total_gb']} GB / 가용 {hw['memory_available_gb']} GB",
        f"- GPU: {hw['gpu']}",
        "",
        "## 2. 운영체제",
        f"- 플랫폼: {os_['platform']}",
        f"- Python: {os_['python']}",
        "",
        "## 3. 저장 용량",
        f"- 데이터 경로: {st['data_dir']}",
        f"- 총 {st['total_gb']} GB / 사용 {st['used_gb']} GB ({st['used_pct']}%) / 여유 {st['free_gb']} GB",
        "",
    ]
    if "db" in diag:
        lines += ["## 4. DB 테이블 현황", "", "| 테이블 | 행 수 |", "|---|---|"]
        lines += [f"| {t} | {n:,} |" for t, n in diag["db"]["tables"].items()]
        lines.append("")
    g = diag["growth"]
    lines += [
        "## 5. 누적 증가량·증설 시점 산정",
        f"- 일일 증가량 추정: 약 {g['daily_rows_estimate']:,} 행/일 ({g['daily_mb_estimate']} MB/일)",
    ]
    if g.get("days_until_full"):
        lines += [
            f"- 현재 여유 공간 기준 소진까지: 약 {g['days_until_full']:,}일",
            f"- 증설 필요 예상 시점: {g['projected_full_date']}",
            "- 권고: 소진 예상 시점 6개월 전까지 저장 장치 증설 또는 보존 정책 단축 검토",
        ]
    lines += [
        "",
        "## 6. 네트워크·보안 설정",
        f"- 네트워크 인터페이스: {', '.join(diag['network']['interfaces']) or '수집 불가'}",
        f"- LISTEN 포트: {', '.join(map(str, diag['security']['listening_ports'])) or '수집 불가(권한 제한)'}",
        "- 권고: 전송용 포트(8883/TLS)·API 포트 외 외부 노출 차단, 서버 접근 계정은 과업 수행 인력으로 한정",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return out_path
