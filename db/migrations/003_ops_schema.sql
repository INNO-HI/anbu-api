-- 운영 DB (매핑·이력·계정)
-- anbu-api 모델에서 자동 생성 (db/generate_ddl.py) — 직접 수정하지 말 것
SET NAMES utf8mb4;

CREATE TABLE audit_logs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(50), 
	action VARCHAR(50) NOT NULL, 
	detail VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE etl_runs (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	job VARCHAR(40) NOT NULL COMMENT 'intervals/status/retention/pseudonymize/ami/publish', 
	started_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	status VARCHAR(10) NOT NULL COMMENT 'ok/error', 
	row_count INTEGER NOT NULL, 
	detail TEXT, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE pseudonym_mappings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	namespace VARCHAR(20) NOT NULL COMMENT 'subject/device/meter', 
	lookup_hash VARCHAR(64) NOT NULL, 
	original_encrypted TEXT NOT NULL, 
	pseudo_id VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_mapping_lookup UNIQUE (namespace, lookup_hash), 
	CONSTRAINT uq_mapping_pseudo UNIQUE (namespace, pseudo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE subscription_receipts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	university VARCHAR(50) NOT NULL, 
	client_id VARCHAR(50) NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	record_count INTEGER NOT NULL, 
	received_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE subscriptions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	university VARCHAR(50) NOT NULL, 
	client_id VARCHAR(50) NOT NULL, 
	client_key_hash VARCHAR(200), 
	topic_pattern VARCHAR(100) NOT NULL COMMENT '예: anbu/#, anbu/alerts', 
	active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (client_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE transfer_history (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	table_name VARCHAR(40) NOT NULL, 
	topic VARCHAR(100) NOT NULL, 
	record_count INTEGER NOT NULL, 
	published_at DATETIME NOT NULL, 
	publisher VARCHAR(50), 
	status VARCHAR(10) NOT NULL COMMENT 'ok/error/dry_run', 
	detail VARCHAR(200), 
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(200) NOT NULL, 
	`role` VARCHAR(20) NOT NULL COMMENT 'super_admin/admin/viewer', 
	active BOOL NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
