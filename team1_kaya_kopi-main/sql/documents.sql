CREATE TABLE IF NOT EXISTS document_schema (
    version INT NOT NULL PRIMARY KEY
);
INSERT IGNORE INTO document_schema (version) VALUES (1);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id CHAR(36) NOT NULL PRIMARY KEY,
    source_scope VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL,
    processing_version VARCHAR(80) NOT NULL,
    started_at DATETIME(6) NOT NULL,
    finished_at DATETIME(6),
    files_seen INT NOT NULL DEFAULT 0,
    records_published INT NOT NULL DEFAULT 0,
    errors_json JSON NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
    id CHAR(36) NOT NULL PRIMARY KEY,
    source_path VARCHAR(512) NOT NULL UNIQUE,
    source_type VARCHAR(16) NOT NULL,
    content_hash CHAR(64),
    processing_version VARCHAR(80),
    revision CHAR(36),
    status VARCHAR(16) NOT NULL,
    last_run_id CHAR(36) NOT NULL,
    FOREIGN KEY (last_run_id) REFERENCES ingestion_runs(id)
);

CREATE TABLE IF NOT EXISTS document_records (
    id CHAR(36) NOT NULL PRIMARY KEY,
    file_id CHAR(36) NOT NULL,
    revision CHAR(36) NOT NULL,
    line_start INT NOT NULL,
    line_end INT NOT NULL,
    occurred_at DATETIME NOT NULL,
    utc_offset_minutes INT,
    subject TEXT NOT NULL,
    sender VARCHAR(255),
    body MEDIUMTEXT NOT NULL,
    FOREIGN KEY (file_id) REFERENCES source_files(id),
    INDEX record_date (occurred_at)
);

CREATE TABLE IF NOT EXISTS record_outlets (
    record_id CHAR(36) NOT NULL,
    original_code VARCHAR(16) NOT NULL,
    canonical_code VARCHAR(16) NOT NULL,
    PRIMARY KEY (record_id, original_code),
    FOREIGN KEY (record_id) REFERENCES document_records(id) ON DELETE CASCADE,
    INDEX canonical_outlet (canonical_code)
);
