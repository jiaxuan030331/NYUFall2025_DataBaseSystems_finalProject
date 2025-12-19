-- ============================================================
-- FULL (REFERENCE) ENTERPRISE SCHEMA  — derived from the “full ERD”
-- ============================================================
--
-- Purpose
-- - This file is a *reference/superset* schema aligned with the larger ERD from earlier parts.
-- - Part IV focuses on an end-to-end workflow slice (unstructured ingestion → ML → write-back).
-- - The *workflow slice* used for the runnable Part IV demo is intentionally simplified and is
--   implemented in: db/schema.sql  (plus db/seed_data.sql).
--
-- How to read this file
-- - Tables below represent a broader enterprise/EDA-style model (accounts, geo, document index,
--   external indicators, etc.) that can exist in a real insurance ODS.
-- - The Part IV workflow slice is a *vertical slice* extracted from this broader model and is
--   documented/run against db/schema.sql.
--
-- Important
-- - This script is written in MySQL 8.x syntax (to avoid confusion with the Part IV MySQL stack).
-- - It creates a separate database (insurance_ods_full) so it does not conflict with insurance_ods.
-- - You do NOT need to run this to run Part IV. It exists to show lineage from “full ERD → slice”.
--
-- Part IV workflow slice tables (implemented in db/schema.sql):
-- - customer, policy, unstructured_text, ml_model_metadata,
--   customer_risk_score, policy_premium_adjustment, pipeline_event
--
-- ============================================================

CREATE DATABASE IF NOT EXISTS insurance_ods_full
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE insurance_ods_full;

-- =========================
-- Core (Enterprise) Entities
-- =========================

CREATE TABLE IF NOT EXISTS customer (
  customer_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  full_name     VARCHAR(200) NOT NULL,
  customer_type VARCHAR(50)  NOT NULL DEFAULT 'PERSON',
  email         VARCHAR(200),
  phone         VARCHAR(50),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS account (
  account_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id  BIGINT      NOT NULL,
  account_no   VARCHAR(64) NOT NULL,
  status       VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
  opened_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at    DATETIME    NULL,
  CONSTRAINT fk_account_customer
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
) ENGINE=InnoDB;

CREATE UNIQUE INDEX ux_account_account_no ON account(account_no);
CREATE INDEX ix_account_customer ON account(customer_id);

-- =========================
-- Geo / Location Domain
-- =========================

CREATE TABLE IF NOT EXISTS geo_map (
  geo_code         VARCHAR(32) PRIMARY KEY,
  country          VARCHAR(100) NOT NULL,
  state_code       VARCHAR(20),
  county_name      VARCHAR(120),
  effective_start  DATE NOT NULL,
  effective_end    DATE,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS customer_location (
  customer_location_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id          BIGINT      NOT NULL,
  geo_code             VARCHAR(32) NOT NULL,
  period_start         DATE        NOT NULL,
  period_end           DATE,
  address_line1        VARCHAR(255),
  address_line2        VARCHAR(255),
  city                 VARCHAR(120),
  postal_code          VARCHAR(40),
  created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_cl_customer
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  CONSTRAINT fk_cl_geo
    FOREIGN KEY (geo_code) REFERENCES geo_map(geo_code),
  CONSTRAINT chk_cl_period
    CHECK (period_end IS NULL OR period_end > period_start)
) ENGINE=InnoDB;

CREATE INDEX ix_cl_customer ON customer_location(customer_id);
CREATE INDEX ix_cl_geo ON customer_location(geo_code);
CREATE INDEX ix_cl_customer_period_start_desc ON customer_location(customer_id, period_start DESC);

-- Note:
-- The full ERD may enforce “no overlapping residence periods” via advanced constraints/triggers.
-- MySQL can implement this with triggers or in the application layer; for reference purposes,
-- we omit complex overlap-trigger logic here.

CREATE TABLE IF NOT EXISTS external_health_indicator (
  indicator_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  geo_code        VARCHAR(32) NOT NULL,
  indicator_code  VARCHAR(80) NOT NULL,
  period_start    DATE NOT NULL,
  period_end      DATE NOT NULL,
  value_num       DECIMAL(12,4) NOT NULL,
  source          VARCHAR(120) NOT NULL,
  ingested_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ehi_geo
    FOREIGN KEY (geo_code) REFERENCES geo_map(geo_code),
  CONSTRAINT chk_ehi_period
    CHECK (period_end >= period_start),
  CONSTRAINT uq_ehi_geo_indicator_period_end
    UNIQUE (geo_code, indicator_code, period_end)
) ENGINE=InnoDB;

CREATE INDEX ix_ehi_geo_period ON external_health_indicator(geo_code, period_start, period_end);
CREATE INDEX ix_ehi_indicator_code ON external_health_indicator(indicator_code);

-- =========================
-- Document / Unstructured Sources (Enterprise view)
-- =========================

CREATE TABLE IF NOT EXISTS unstructured_source (
  source_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
  account_id   BIGINT,
  file_path    VARCHAR(500) NOT NULL,
  file_type    VARCHAR(50)  NOT NULL,
  ingest_date  DATE         NOT NULL,
  description  VARCHAR(500),
  source_url   VARCHAR(500),
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_us_account
    FOREIGN KEY (account_id) REFERENCES account(account_id)
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX ix_us_account ON unstructured_source(account_id);
CREATE UNIQUE INDEX ux_us_file_path ON unstructured_source(file_path);

CREATE TABLE IF NOT EXISTS document_index (
  doc_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id    BIGINT       NOT NULL,
  doc_type       VARCHAR(80)  NOT NULL,
  uri            VARCHAR(500) NOT NULL,
  source_system  VARCHAR(80),
  metadata       JSON NOT NULL,
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_di_customer
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
) ENGINE=InnoDB;

CREATE INDEX ix_di_customer_doctype ON document_index(customer_id, doc_type);

-- =========================
-- Risk / Analytics (Enterprise view)
-- =========================

-- In the full ERD/enterprise view, we may keep *latest* risk per customer for fast operational access.
CREATE TABLE IF NOT EXISTS customer_risk_score_latest (
  customer_id    BIGINT       PRIMARY KEY,
  risk_score     DECIMAL(5,4) NOT NULL,
  risk_label     VARCHAR(20)  NOT NULL,
  model_id       VARCHAR(100) NOT NULL,
  model_version  VARCHAR(100) NOT NULL,
  scored_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_crsl_customer
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  CONSTRAINT chk_crsl_score_range
    CHECK (risk_score >= 0.0 AND risk_score <= 1.0)
) ENGINE=InnoDB;

CREATE INDEX ix_crsl_risk_label ON customer_risk_score_latest(risk_label);
CREATE INDEX ix_crsl_scored_at_desc ON customer_risk_score_latest(scored_at DESC);

CREATE TABLE IF NOT EXISTS customer_risk_feature_snapshot (
  snapshot_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  customer_id           BIGINT NOT NULL,
  risk_segment          VARCHAR(50),
  bmi_bucket            VARCHAR(50),
  activity_level        VARCHAR(50),
  geo_code              VARCHAR(32),
  data_cutoff_at        DATETIME NOT NULL,
  feature_view_version  VARCHAR(50) NOT NULL,
  created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_crfs_customer
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
  CONSTRAINT fk_crfs_geo
    FOREIGN KEY (geo_code) REFERENCES geo_map(geo_code)
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX ix_crfs_customer ON customer_risk_feature_snapshot(customer_id);
CREATE INDEX ix_crfs_geo ON customer_risk_feature_snapshot(geo_code);
CREATE INDEX ix_crfs_segment ON customer_risk_feature_snapshot(risk_segment);

CREATE TABLE IF NOT EXISTS customer_score_explain (
  customer_id    BIGINT PRIMARY KEY,
  top_factor1    VARCHAR(200),
  top_factor2    VARCHAR(200),
  top_factor3    VARCHAR(200),
  model_version  VARCHAR(100) NOT NULL,
  updated_at     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_cse_customer
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
) ENGINE=InnoDB;

CREATE INDEX ix_cse_model_version ON customer_score_explain(model_version);
