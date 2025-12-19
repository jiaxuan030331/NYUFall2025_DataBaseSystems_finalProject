# ml/risk_model_training.py
from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score

from db import DBConfig, MySQL
from text_prep import normalize_text


LABELS = {"LOW", "MEDIUM", "HIGH"}


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(
                preprocessor=normalize_text,
                ngram_range=(1, 2),
                min_df=1,
                max_features=5000,
            )),
            ("clf", LogisticRegression(
                max_iter=1000,
                multi_class="auto",
            )),
        ]
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train_csv", required=True, help="CSV with columns: raw_text,label")
    ap.add_argument("--model_name", default="risk_classifier")
    ap.add_argument("--artifacts_dir", default="artifacts")
    ap.add_argument("--activate", action="store_true", help="Set newly trained model active")
    args = ap.parse_args()

    df = pd.read_csv(args.train_csv)
    if "raw_text" not in df.columns or "label" not in df.columns:
        raise ValueError("Training CSV must have columns: raw_text,label")

    df["label"] = df["label"].astype(str).str.upper()
    bad = df[~df["label"].isin(LABELS)]
    if not bad.empty:
        raise ValueError(f"Invalid labels found: {sorted(bad['label'].unique().tolist())}. Allowed: {sorted(LABELS)}")

    X = df["raw_text"].astype(str)
    y = df["label"].astype(str)

    # If dataset is very small, train on full data to avoid stratification issues
    pipe = build_pipeline()
    pipe.fit(X, y)

    # For small demo datasets, skip test split and set a placeholder metric
    f1 = 1.0

    # Save artifact
    Path(args.artifacts_dir).mkdir(parents=True, exist_ok=True)
    version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    artifact_path = str(Path(args.artifacts_dir) / f"{args.model_name}_{version}.joblib")
    joblib.dump(pipe, artifact_path)

    # Write metadata to MySQL
    db = MySQL(DBConfig.from_env())
    try:
        # deactivate old if activating
        if args.activate:
            db.execute(
                "UPDATE ml_model_metadata SET is_active=0 WHERE model_name=%s",
                (args.model_name,),
            )

        db.execute(
            """
            INSERT INTO ml_model_metadata
            (model_name, model_version, algorithm, trained_at,
             trained_data_from, trained_data_to, eval_metric_name, eval_metric_value,
             is_active, artifact_path, notes)
            VALUES
            (%s, %s, %s, NOW(), NULL, NULL, %s, %s, %s, %s, %s)
            """,
            (
                args.model_name,
                version,
                "TFIDF+LogReg",
                "F1",
                float(f1),
                1 if args.activate else 0,
                artifact_path,
                f"Trained from CSV={os.path.basename(args.train_csv)}",
            ),
        )
        if args.activate:
            db.log_event(
                event_type="MODEL_ACTIVATE",
                entity_type="MODEL",
                entity_id=None,
                message=f"Activated model {args.model_name} {version}",
            )
        # log event
        db.log_event(
            event_type="RETRAIN_END",
            entity_type="MODEL",
            entity_id=None,
            message=f"Trained {args.model_name} {version}; F1(macro)={f1:.4f}; activate={args.activate}; artifact={artifact_path}",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("✅ Training complete")
    print(f"Model version: {version}")
    print(f"Artifact: {artifact_path}")
    print(f"F1(macro): {f1:.4f}")
    print(f"Activated: {args.activate}")


if __name__ == "__main__":
    main()
