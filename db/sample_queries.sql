USE insurance_ods;

-- Q1: Latest risk per customer
SELECT customer_id, risk_label, risk_score, scored_at
FROM customer_risk_score
ORDER BY scored_at DESC
LIMIT 5;

-- Q1b (Optimized): Latest risk per customer (materialized latest table)
SELECT customer_id, risk_label, risk_score, scored_at
FROM customer_risk_score_latest
ORDER BY scored_at DESC
LIMIT 5;

-- Q2: Top-N high risk customers (last 2 years)
SELECT c.full_name, crs.risk_label, crs.risk_score
FROM customer c
JOIN customer_risk_score crs ON c.customer_id = crs.customer_id
WHERE crs.scored_at >= DATE_SUB(CURDATE(), INTERVAL 2 YEAR)
ORDER BY crs.risk_score DESC
LIMIT 5;

-- Q2b (Optimized): Top-N high risk customers using latest table
SELECT c.full_name, crs.risk_label, crs.risk_score
FROM customer c
JOIN customer_risk_score_latest crs ON c.customer_id = crs.customer_id
WHERE crs.scored_at >= DATE_SUB(CURDATE(), INTERVAL 2 YEAR)
ORDER BY crs.risk_score DESC
LIMIT 5;

-- Q3: Risk distribution
SELECT risk_label, COUNT(*) AS cnt
FROM customer_risk_score
GROUP BY risk_label;

-- Q3b (Optimized): Risk distribution over latest (1 row per customer)
SELECT risk_label, COUNT(*) AS cnt
FROM customer_risk_score_latest
GROUP BY risk_label;

-- Q4: End-to-end join
SELECT
  c.full_name,
  ut.source_type,
  crs.risk_label,
  crs.risk_score,
  mm.model_version
FROM customer c
JOIN unstructured_text ut ON c.customer_id = ut.customer_id
JOIN customer_risk_score crs ON crs.text_id = ut.text_id
JOIN ml_model_metadata mm ON mm.model_id = crs.model_id
ORDER BY crs.scored_at DESC;

-- Q4b (Optimized): End-to-end join using latest table (less scan/sort)
SELECT
  c.full_name,
  ut.source_type,
  crs.risk_label,
  crs.risk_score,
  mm.model_version
FROM customer c
JOIN customer_risk_score_latest crs ON crs.customer_id = c.customer_id
JOIN unstructured_text ut ON ut.text_id = crs.text_id
JOIN ml_model_metadata mm ON mm.model_id = crs.model_id
ORDER BY crs.scored_at DESC;

-- Q5: Query optimization example
EXPLAIN
SELECT *
FROM customer_risk_score
WHERE risk_label='HIGH'
ORDER BY scored_at DESC
LIMIT 5;

-- Q5b (Optimized): Same pattern on latest table (with ix_crsl_label_scored)
EXPLAIN
SELECT *
FROM customer_risk_score_latest
WHERE risk_label='HIGH'
ORDER BY scored_at DESC
LIMIT 5;
