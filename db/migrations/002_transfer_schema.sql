-- 전송용 DB (가명처리본 7개 테이블)
-- anbu-api 모델에서 자동 생성 (db/generate_ddl.py) — 직접 수정하지 말 것
SET NAMES utf8mb4;

CREATE TABLE t_alerts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	pseudo_subject_id VARCHAR(64) NOT NULL, 
	pseudo_device_id VARCHAR(64), 
	alert_type VARCHAR(30) NOT NULL, 
	triggered_at DATETIME NOT NULL, 
	resolved_at DATETIME, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_t_alerts_pseudo_subject_id ON t_alerts (pseudo_subject_id);

CREATE TABLE t_care_records (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	pseudo_subject_id VARCHAR(64) NOT NULL, 
	visit_at DATETIME NOT NULL, 
	care_type VARCHAR(30), 
	memo_pseudo TEXT COMMENT 'SFR-010 정밀 가명처리 결과', 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_t_care_records_pseudo_subject_id ON t_care_records (pseudo_subject_id);

CREATE TABLE t_device_status_history (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	pseudo_device_id VARCHAR(64) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	changed_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_t_device_status_history_pseudo_device_id ON t_device_status_history (pseudo_device_id);

CREATE TABLE t_devices (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	pseudo_device_id VARCHAR(64) NOT NULL, 
	pseudo_subject_id VARCHAR(64) NOT NULL, 
	room VARCHAR(20), 
	device_type VARCHAR(20), 
	PRIMARY KEY (id), 
	UNIQUE (pseudo_device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_t_devices_pseudo_subject_id ON t_devices (pseudo_subject_id);

CREATE TABLE t_lighting_intervals (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	pseudo_device_id VARCHAR(64) NOT NULL, 
	started_at DATETIME NOT NULL, 
	ended_at DATETIME NOT NULL, 
	duration_sec INTEGER NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_t_interval_device_time ON t_lighting_intervals (pseudo_device_id, started_at);

CREATE TABLE t_power_usage (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	pseudo_meter_id VARCHAR(64) NOT NULL, 
	pseudo_subject_id VARCHAR(64), 
	measured_at DATETIME NOT NULL, 
	kwh NUMERIC(10, 3) NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_t_power_meter_time ON t_power_usage (pseudo_meter_id, measured_at);

CREATE TABLE t_subjects (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	pseudo_subject_id VARCHAR(64) NOT NULL, 
	age_band VARCHAR(10) COMMENT '예: 65-69 … 80-84, 85+', 
	gender VARCHAR(1), 
	region_emd VARCHAR(50) COMMENT '읍·면·동까지만', 
	service_start_ym VARCHAR(7) COMMENT 'YYYY-MM', 
	service_end_ym VARCHAR(7) COMMENT 'YYYY-MM', 
	meal_cat VARCHAR(10) COMMENT '자립/부분도움/전적도움', 
	cognition_cat VARCHAR(10), 
	communication_cat VARCHAR(10), 
	high_risk_yn BOOL COMMENT '예/아니오만, 사유 없음', 
	benefit_yn BOOL COMMENT '기본 None(삭제). 발주기관 협의 시에만 예/아니오 채움', 
	PRIMARY KEY (id), 
	UNIQUE (pseudo_subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
