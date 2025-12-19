CREATE DATABASE IF NOT EXISTS insurance_ods
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE insurance_ods;

-- =========================
-- Core Tables
-- =========================

CREATE TABLE customer (
  customer_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  full_name VARCHAR(200) NOT NULL,
  email VARCHAR(200),
  phone VARCHAR(50),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE policy (
  policy_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  product_type VARCHAR(100),
  base_premium DECIMAL(12,2),
  status ENUM('ACTIVE','PENDING','CANCELLED') DEFAULT 'PENDING',
  effective_date DATE,
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

-- =========================
-- Unstructured Data
-- =========================

CREATE TABLE unstructured_text (
  text_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  source_type ENUM('CLAIM_DESCRIPTION','CUSTOMER_REVIEW','SUPPORT_CHAT','OTHER'),
  raw_text TEXT,
  is_processed TINYINT DEFAULT 0,
  ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  processed_at DATETIME,
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
);

-- =========================
-- ML Governance
-- =========================

CREATE TABLE ml_model_metadata (
  model_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  model_name VARCHAR(200),
  model_version VARCHAR(100),
  algorithm VARCHAR(100),
  trained_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  eval_metric_name VARCHAR(50),
  eval_metric_value DECIMAL(10,6),
  is_active TINYINT DEFAULT 0,
  artifact_path VARCHAR(500)
);

-- =========================
-- ML Write-back
-- =========================

CREATE TABLE customer_risk_score (
  risk_score_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id BIGINT,
  text_id BIGINT,
  model_id BIGINT,
  risk_label ENUM('LOW','MEDIUM','HIGH'),
  risk_score DECIMAL(10,6),
  explanation VARCHAR(500),
  scored_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (text_id) REFERENCES unstructured_text(text_id),
  FOREIGN KEY (model_id) REFERENCES ml_model_metadata(model_id)
);

-- Latest risk per customer (optimization for dashboard/top queries)
CREATE TABLE customer_risk_score_latest (
  customer_id BIGINT PRIMARY KEY,
  risk_score_id BIGINT,
  text_id BIGINT,
  model_id BIGINT,
  risk_label ENUM('LOW','MEDIUM','HIGH'),
  risk_score DECIMAL(10,6),
  explanation VARCHAR(500),
  scored_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  FOREIGN KEY (text_id) REFERENCES unstructured_text(text_id),
  FOREIGN KEY (model_id) REFERENCES ml_model_metadata(model_id)
);

CREATE TABLE policy_premium_adjustment (
  adjustment_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  policy_id BIGINT,
  customer_id BIGINT,
  model_id BIGINT,
  risk_score_id BIGINT,
  adjustment_pct DECIMAL(6,2),
  suggested_premium DECIMAL(12,2),
  decision_status ENUM('SUGGESTED','APPROVED','REJECTED') DEFAULT 'SUGGESTED',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Pipeline Log
-- =========================

CREATE TABLE pipeline_event (
  event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  event_type VARCHAR(50),
  entity_type VARCHAR(50),
  entity_id BIGINT,
  message VARCHAR(2000),
  event_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Indexes (query optimization)
-- =========================

-- Inference: pull unprocessed texts in ingestion order
CREATE INDEX ix_unstructured_text_processed_ingested
  ON unstructured_text (is_processed, ingested_at);

-- Model lookup: find active model quickly
CREATE INDEX ix_mlm_name_active_trained
  ON ml_model_metadata (model_name, is_active, trained_at);

-- Risk history: support dashboard/latest lookups and premium suggestion join
CREATE INDEX ix_crs_customer_scored
  ON customer_risk_score (customer_id, scored_at);

CREATE INDEX ix_crs_customer_text_model_scored
  ON customer_risk_score (customer_id, text_id, model_id, scored_at);

CREATE INDEX ix_crs_label_scored
  ON customer_risk_score (risk_label, scored_at);

-- Latest risk table: top-N and filtering
CREATE INDEX ix_crsl_label_scored
  ON customer_risk_score_latest (risk_label, scored_at);

-- Policies: lookup active policy for a customer
CREATE INDEX ix_policy_customer_status
  ON policy (customer_id, status);

-- Premium adjustments: fetch latest adjustment for a customer
CREATE INDEX ix_ppa_customer_created
  ON policy_premium_adjustment (customer_id, created_at);

