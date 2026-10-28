-- 누적 DB (원본 — 반출 금지)
-- anbu-api 모델에서 자동 생성 (db/generate_ddl.py) — 직접 수정하지 말 것
SET NAMES utf8mb4;

CREATE TABLE subjects (
	subject_id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(50) NOT NULL COMMENT '직접식별자: 전송 시 삭제', 
	phone VARCHAR(20) COMMENT '직접식별자: 전송 시 삭제', 
	address_full VARCHAR(200) COMMENT '직접식별자: 전송 시 삭제', 
	region_emd VARCHAR(50) COMMENT '읍·면·동 (전송 시 이 수준까지만 유지)', 
	birth_date DATE COMMENT '전송 시 연령대로 일반화(85세 이상 통합)', 
	gender VARCHAR(1) COMMENT 'M/F', 
	guardian_name VARCHAR(50) COMMENT '직접식별자: 전송 시 삭제', 
	guardian_phone VARCHAR(20) COMMENT '직접식별자: 전송 시 삭제', 
	care_worker_name VARCHAR(50) COMMENT '직접식별자: 전송 시 삭제', 
	care_worker_phone VARCHAR(20) COMMENT '직접식별자: 전송 시 삭제', 
	service_start_date DATE COMMENT '전송 시 월 단위(YYYY-MM)로 변환', 
	service_end_date DATE COMMENT '전송 시 월 단위(YYYY-MM)로 변환', 
	meal_level VARCHAR(20) COMMENT '식사 기능 코드 L1~L5 → 전송 시 상위 범주화', 
	cognition_level VARCHAR(20) COMMENT '인지 기능 코드 L1~L5 → 전송 시 상위 범주화', 
	communication_level VARCHAR(20) COMMENT '의사소통 기능 코드 L1~L5 → 전송 시 상위 범주화', 
	benefit_type VARCHAR(20) COMMENT '수급 구분: 전송 시 삭제(협의 시 예/아니오만)', 
	high_risk_yn BOOL NOT NULL COMMENT '고위험군 여부: 전송 시 예/아니오만', 
	high_risk_reason VARCHAR(200) COMMENT '판정 사유: 전송 시 삭제', 
	notes TEXT COMMENT '자유기술: 전송 제외(SFR-010 채택 시 정밀 가명처리)', 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ami_usage_a (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	meter_id VARCHAR(30) NOT NULL, 
	subject_id INTEGER, 
	measured_at DATETIME NOT NULL, 
	kwh NUMERIC(10, 3) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ami_usage_b (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	meter_no VARCHAR(30) NOT NULL, 
	subject_id INTEGER, 
	read_time DATETIME NOT NULL, 
	usage_kwh NUMERIC(10, 3) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE care_records (
	record_id INTEGER NOT NULL AUTO_INCREMENT, 
	subject_id INTEGER NOT NULL, 
	care_worker_name VARCHAR(50), 
	visit_at DATETIME NOT NULL, 
	care_type VARCHAR(30) COMMENT '코드: 방문/전화/기타', 
	memo TEXT, 
	PRIMARY KEY (record_id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_care_records_subject_id ON care_records (subject_id);

CREATE TABLE devices (
	device_id INTEGER NOT NULL AUTO_INCREMENT, 
	subject_id INTEGER NOT NULL, 
	room VARCHAR(20) COMMENT '설치 위치: 안방/거실/주방/화장실 등', 
	device_type VARCHAR(20) NOT NULL, 
	serial_no VARCHAR(50), 
	install_date DATE, 
	current_status VARCHAR(10) NOT NULL COMMENT '코드: normal/inactive/fault', 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (device_id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_devices_subject_id ON devices (subject_id);

CREATE TABLE power_usage (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	meter_pseudo_id VARCHAR(64) NOT NULL COMMENT '가명 계량기 식별자(SFR-009)', 
	subject_id INTEGER, 
	measured_at DATETIME NOT NULL, 
	kwh NUMERIC(10, 3) NOT NULL, 
	source VARCHAR(1) NOT NULL COMMENT '정본 출처: A(우선)/B(보충)', 
	PRIMARY KEY (id), 
	CONSTRAINT uq_power_meter_time UNIQUE (meter_pseudo_id, measured_at), 
	FOREIGN KEY(subject_id) REFERENCES subjects (subject_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE alerts (
	alert_id INTEGER NOT NULL AUTO_INCREMENT, 
	subject_id INTEGER NOT NULL, 
	device_id INTEGER, 
	alert_type VARCHAR(30) NOT NULL COMMENT '코드: NO_LIGHT_24H/LONG_INACTIVITY/DEVICE_FAULT', 
	triggered_at DATETIME NOT NULL, 
	resolved_at DATETIME, 
	note VARCHAR(200), 
	PRIMARY KEY (alert_id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (subject_id), 
	FOREIGN KEY(device_id) REFERENCES devices (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_alerts_subject_id ON alerts (subject_id);

CREATE TABLE device_status_history (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	device_id INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL COMMENT 'normal/inactive/fault', 
	changed_at DATETIME NOT NULL, 
	source VARCHAR(10) NOT NULL COMMENT 'auto(추론)/sync(원시스템)/manual', 
	note VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(device_id) REFERENCES devices (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_status_hist_device_time ON device_status_history (device_id, changed_at);

CREATE TABLE led_raw_logs (
	id BIGINT NOT NULL AUTO_INCREMENT, 
	device_id INTEGER NOT NULL, 
	logged_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(device_id) REFERENCES devices (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_led_raw_device_time ON led_raw_logs (device_id, logged_at);

CREATE TABLE lighting_intervals (
	interval_id BIGINT NOT NULL AUTO_INCREMENT, 
	device_id INTEGER NOT NULL, 
	started_at DATETIME NOT NULL, 
	ended_at DATETIME NOT NULL, 
	duration_sec INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (interval_id), 
	CONSTRAINT uq_interval_device_start UNIQUE (device_id, started_at), 
	FOREIGN KEY(device_id) REFERENCES devices (device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE INDEX ix_interval_device_time ON lighting_intervals (device_id, started_at);

-- 대상자 단위 통합 조회 뷰 (SFR-002)
DROP VIEW IF EXISTS v_subject_overview;
CREATE VIEW v_subject_overview AS SELECT s.subject_id,
       s.region_emd,
       s.gender,
       s.high_risk_yn,
       (SELECT COUNT(*) FROM devices d
         WHERE d.subject_id = s.subject_id)                       AS device_count,
       (SELECT MAX(li.ended_at)
          FROM lighting_intervals li
          JOIN devices d2 ON li.device_id = d2.device_id
         WHERE d2.subject_id = s.subject_id)                      AS last_lighting_at,
       (SELECT COUNT(*) FROM alerts a
         WHERE a.subject_id = s.subject_id
           AND a.resolved_at IS NULL)                             AS open_alert_count,
       (SELECT COUNT(*) FROM care_records c
         WHERE c.subject_id = s.subject_id)                       AS care_record_count
  FROM subjects s;
