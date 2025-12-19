USE insurance_ods;

-- Customers
INSERT INTO customer (full_name, email) VALUES
('Alice Tan', 'alice@example.com'),
('Ben Lim', 'ben@example.com'),
('Cheryl Ng', 'cheryl@example.com');

-- Policies
INSERT INTO policy (customer_id, product_type, base_premium, status) VALUES
(1, 'AUTO', 1200, 'ACTIVE'),
(2, 'HEALTH', 1800, 'ACTIVE'),
(3, 'HOME', 900, 'PENDING');

-- Unstructured Text
INSERT INTO unstructured_text (customer_id, source_type, raw_text) VALUES
(1, 'CUSTOMER_REVIEW', 'Service was smooth and fast'),
(2, 'SUPPORT_CHAT', 'Agent never called back, very frustrated'),
(3, 'CLAIM_DESCRIPTION', 'Multiple incidents and missing documents');

-- Initial ML Model (demo)
INSERT INTO ml_model_metadata
(model_name, model_version, algorithm, eval_metric_name, eval_metric_value, is_active, artifact_path)
VALUES
('risk_classifier', 'v20251216_191210_afcbb2', 'TFIDF+LogReg', 'F1', 0.80, 1, 'artifacts/risk_classifier_v20251216_191210_afcbb2.joblib');
