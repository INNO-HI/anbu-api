"""애플리케이션 설정. 비밀값은 환경변수(.env)로만 주입하며 커밋하지 않는다."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 누적 DB (원본) — 읽기 전용 계정 권장
    source_db_host: str = "127.0.0.1"
    source_db_port: int = 3306
    source_db_name: str = "anbu_accum"
    source_db_user: str = "anbu_ro"
    source_db_password: str = ""

    # 전송용 DB (원본과 분리)
    transfer_db_host: str = "127.0.0.1"
    transfer_db_port: int = 3306
    transfer_db_name: str = "anbu_transfer"
    transfer_db_user: str = "anbu_transfer"
    transfer_db_password: str = ""

    # 가명처리 비밀키 (발주기관 전용 보관)
    pseudonym_secret_key: str = ""
    mapping_encryption_key: str = ""

    # MQTT (구독형 전송)
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 8883
    mqtt_tls_ca: str | None = None
    mqtt_username: str = ""
    mqtt_password: str = ""

    tz: str = "Asia/Seoul"


settings = Settings()
