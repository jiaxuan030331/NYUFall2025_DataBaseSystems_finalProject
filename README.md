## NYU CSCI-GA.2433 (Database Systems) — MSDS Fall 2025 Final Project (Part IV)

**Course**: NYU MSDS, CSCI-GA.2433 Database Systems (Fall 2025)  
**Spec**: `ProjectPart4.pdf` (End-to-End Solution Integration and Data-Driven / Database Programming)  
**Authors**: Haixin Tan, Jiaxuan Huang  

### Overview
This repository implements an **end-to-end, data-driven, workflow-based database application** for an insurance OLTP/ODS on **MySQL 8.x**. It supports:
- Ingesting **unstructured text** (claim descriptions / reviews / support chats)
- Running **ML risk inference** (TF‑IDF + Logistic Regression) and writing results back to the database
- Generating **premium adjustment suggestions**
- Logging **pipeline events** for auditability
- Providing simple **end-user views** (customer dashboard + top‑N high risk customers)

### Tech Stack
- **Database**: MySQL 8.x
- **Language**: Python 3.x
- **ML**: scikit-learn
- **DB driver**: mysql-connector-python

### Repository Layout
- `app/`: workflow application (CLI)
- `ml/`: training, inference/write-back, retrain trigger
- `db/`: schema, seed data, representative queries + EXPLAIN
- `artifacts/`: trained model artifacts (`.joblib`)
- `img/`: ERD + evidence screenshots used in the report

### Setup
#### 1) Install Python dependencies

```bash
pip install scikit-learn pandas joblib mysql-connector-python
```

Optional (extra credit): install ORM dependencies:

```bash
pip install SQLAlchemy PyMySQL
```

#### 2) Configure database connection
Set these environment variables (recommended). If you do not set them, the code will fall back to defaults in `app/db_connection.py` and `ml/db.py`.

macOS/Linux:

```bash
export DB_HOST="127.0.0.1"
export DB_PORT="3306"
export DB_USER="root"
export DB_PASSWORD="your_mysql_password"
export DB_NAME="insurance_ods"
```

Windows (PowerShell):

```powershell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="your_mysql_password"
$env:DB_NAME="insurance_ods"
```

### Database Initialization
From a MySQL client:

```sql
SOURCE db/schema.sql;
SOURCE db/seed_data.sql;
```

Notes:
- `db/schema.sql` is the **Part IV workflow slice** schema (the runnable demo ODS).
- `db/full_schema.sql` is a **reference “full ERD” superset** (separate DB) to show how the Part IV slice was extracted.

### Run: ML Training + Activation
Train and activate a new model (writes to `ml_model_metadata` and saves an artifact under `artifacts/`):

```bash
python ml/risk_model_training.py \
  --train_csv ml/sample_unstructured_data_labeled.csv \
  --activate
```

### Run: Inference + Write-back
Scores unprocessed texts and writes:
- `customer_risk_score` (history)
- `customer_risk_score_latest` (materialized latest-per-customer view for fast queries)
- `policy_premium_adjustment`
- `pipeline_event`

```bash
python ml/risk_model_inference.py --batch_size 50
```

Optional: refresh scores for recently ingested texts (useful after a model update):

```bash
python ml/risk_model_inference.py --batch_size 200 --rescore_recent_days 30
```

### Run: End-to-End Workflow Application (CLI)
Show the active model:

```bash
python app/main_app.py --action show_model
```

Run app read queries using ORM (extra credit path):

```bash
python app/main_app.py --use_orm --action show_model
python app/main_app.py --use_orm --action dashboard --customer_id 3
python app/main_app.py --use_orm --action top --top_n 5
```

Ingest new unstructured text:

```bash
python app/main_app.py \
  --action ingest \
  --customer_id 3 \
  --source_type CLAIM_DESCRIPTION \
  --text "Multiple incidents again, missing documents, urgent payout request."
```

Trigger inference:

```bash
python app/main_app.py --action infer --batch_size 50
```

Run the automated pipeline (optional):
- Retrain if `unprocessed_texts >= threshold_new_texts` (requires `--train_csv`)
- Run inference on new texts
- Optionally rescore a recent window using the active model

```bash
python app/main_app.py --action pipeline \
  --train_csv ml/sample_unstructured_data_labeled.csv \
  --threshold_new_texts 20 \
  --batch_size 50 \
  --rescore_recent_days 30
```

View customer risk dashboard:

```bash
python app/main_app.py --action dashboard --customer_id 3
```

View top‑N high-risk customers:

```bash
python app/main_app.py --action top --top_n 5
```

### Query Optimization (Part IV Requirement)
We optimize key queries via:
- **Targeted secondary indexes** (in `db/schema.sql`)
- A **materialized latest-per-customer table**: `customer_risk_score_latest` (maintained by inference)

See representative queries and EXPLAIN statements in:
- `db/sample_queries.sql`

### Evidence Artifacts (for the final report)
The `img/` folder contains:
- ERD for the Part IV workflow slice (`insurance_ods.png`)
- Screenshots demonstrating ingestion, model metadata/versioning, write-back, premium suggestions, pipeline logs, and EXPLAIN.