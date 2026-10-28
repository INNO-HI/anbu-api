"""코드값·결측 표준 정의(SFR-003) — 데이터 사전에 수록되는 표준의 단일 원천."""
from __future__ import annotations

# 결측 표준: 값이 없으면 NULL. 빈 문자열, '-', '미상', 0 대체 표기를 금지한다.
MISSING_VALUE_STANDARD = "결측은 NULL로만 표기한다(빈 문자열·'-'·'미상'·0 대체 금지)."

CODE_DEFINITIONS: dict[str, dict[str, str]] = {
    "devices.current_status / device_status_history.status": {
        "normal": "정상(신호 수신 중)",
        "inactive": "비활성(무신호 — 장비 중단 또는 수거)",
        "fault": "장애(오작동·응답 없음)",
    },
    "alerts.alert_type": {
        "NO_LIGHT_24H": "24시간 무점등(생활 신호 없음)",
        "LONG_INACTIVITY": "장기 무활동(점등 패턴 급감)",
        "DEVICE_FAULT": "장비 장애",
    },
    "care_records.care_type": {
        "방문": "현장 방문 돌봄",
        "전화": "전화 안부 확인",
        "기타": "그 외 활동",
    },
    "subjects.meal_level / cognition_level / communication_level": {
        "L1": "완전 자립",
        "L2": "대체로 자립",
        "L3": "부분 도움 필요",
        "L4": "상당한 도움 필요",
        "L5": "전적 도움 필요",
    },
    "subjects.benefit_type": {
        "기초수급": "국민기초생활보장 수급",
        "차상위": "차상위 계층",
        "일반": "비수급 일반",
    },
    "subjects.gender": {"M": "남성", "F": "여성"},
    "power_usage.source": {"A": "AMI 원천 1종(정본 우선)", "B": "AMI 원천 2종(보충)"},
}

# 이상 알림 판정 기준(데이터 사전 수록용)
ALERT_RULES = {
    "NO_LIGHT_24H": "전체 설치 센서에서 24시간 이상 점등 기록이 없을 때",
    "LONG_INACTIVITY": "최근 7일 일평균 점등 구간 수가 직전 4주 평균의 30% 미만일 때",
    "DEVICE_FAULT": "장비 헬스체크 무응답 또는 원시스템 장애 보고 시",
}
