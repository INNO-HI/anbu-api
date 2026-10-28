"""애플리케이션 설정. 비밀값은 환경변수(.env)로만 주입하며 커밋하지 않는다.

DB는 과업지시서(SFR-004)에 따라 3개로 물리 분리한다.
  - accum    : 누적 DB(원본, 직접식별자 포함 — 본교 서버 밖 반출 금지)
  - transfer : 전송용 DB(가명처리본만 적재, 참여 대학 제공 대상)
  - ops      : 운영 DB(가명 매핑·전송 이력·계정·감사 로그)
개발·테스트는 sqlite 기본값으로 바로 구동되고, 운영(다향관 서버)은 MariaDB URL로 교체한다.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- 데이터베이스 (3개 분리) ---
    accum_db_url: str = "sqlite:///data/accum.db"
    transfer_db_url: str = "sqlite:///data/transfer.db"
    ops_db_url: str = "sqlite:///data/ops.db"

    # --- 가명처리 (SFR-004) — 발주기관 전용 보관, 커밋 금지 ---
    pseudonym_secret_key: str = "dev-only-secret-change-in-production"
    mapping_encryption_key: str = ""  # Fernet 키. 비우면 secret_key에서 유도

    # --- MQTT 구독형 전송 (SFR-006) ---
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_tls_ca: str | None = None
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "anbu"

    # --- API 인증 (SFR-007) ---
    jwt_secret_key: str = "dev-only-jwt-secret-change-in-production-32b+"
    jwt_expire_minutes: int = 60

    # --- ETL (SFR-002) ---
    lighting_gap_threshold_sec: int = 60  # 로그 공백이 이 값 이상이면 소등으로 판정
    retention_raw_log_days: int = 365     # LED 원시 로그 보관 일수(경과분 파기)
    inactive_after_hours: int = 48        # 무신호 지속 시 장비 '비활성' 판정 기준

    # --- 시각 기준 (KST 통일, SFR-002) ---
    tz: str = "Asia/Seoul"


settings = Settings()
