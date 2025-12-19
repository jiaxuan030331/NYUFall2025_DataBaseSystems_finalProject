# ml/risk_model_inference.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import joblib

from db import DBConfig, MySQL


def label_to_adjustment_pct(label: str) -> float:
    # policy for demo/report
    if label == "HIGH":
        return 15.0
    if label == "MEDIUM":
        return 5.0
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch_size", type=int, default=50)
    ap.add_argument("--model_name", default="risk_classifier")
    ap.add_argument("--artifact_override", default="", help="If provided, use this artifact path instead of active model")
    ap.add_argument(
        "--rescore_recent_days",
        type=int,
        default=0,
        help="If >0, (re)score texts ingested within the last N days, even if already processed. "
             "Unprocessed texts will still be marked processed; processed texts remain processed.",
    )
    args = ap.parse_args()

    db = MySQL(DBConfig.from_env())
    try:
        # 1) pick active model
        model_id = db.get_active_model_id(args.model_name)
        if model_id is None:
            raise RuntimeError("No active model found in ml_model_metadata. Train & activate a model first.")

        rows = db.fetchall_dict(
            """
            SELECT model_id, artifact_path
            FROM ml_model_metadata
            WHERE model_id=%s
            """,
            (model_id,),
        )
        artifact_path = args.artifact_override.strip() or rows[0]["artifact_path"]
        if not artifact_path:
            raise RuntimeError("Active model has empty artifact_path. Please set it in ml_model_metadata.")

        if not Path(artifact_path).exists():
            raise RuntimeError(f"Model artifact not found: {artifact_path}")

        model = joblib.load(artifact_path)

        # 2) fetch texts to score
        if args.rescore_recent_days and args.rescore_recent_days > 0:
            texts = db.fetchall_dict(
                """
                SELECT text_id, customer_id, raw_text
                FROM unstructured_text
                WHERE ingested_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                ORDER BY ingested_at ASC
                LIMIT %s
                """,
                (int(args.rescore_recent_days), int(args.batch_size)),
            )
        else:
            texts = db.fetchall_dict(
                """
                SELECT text_id, customer_id, raw_text
                FROM unstructured_text
                WHERE is_processed=0
                ORDER BY ingested_at ASC
                LIMIT %s
                """,
                (args.batch_size,),
            )

        if not texts:
            if args.rescore_recent_days and args.rescore_recent_days > 0:
                print(f"No recent texts found for rescore (last {args.rescore_recent_days} days). ✅ Nothing to do.")
            else:
                print("No unprocessed text found. ✅ Nothing to do.")
            return

        raw_list = [t["raw_text"] for t in texts]
        preds = model.predict(raw_list)

        # try to get probabilities for a score (0..1)
        # if model supports predict_proba, use max class probability as risk_score
        risk_scores = []
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(raw_list)
            # max probability per sample as confidence proxy
            risk_scores = [float(p.max()) for p in proba]
        else:
            risk_scores = [0.5 for _ in preds]

        # 3) write back risk scores
        inserts = []
        for t, label, score in zip(texts, preds, risk_scores):
            inserts.append((
                int(t["customer_id"]),
                int(t["text_id"]),
                int(model_id),
                str(label).upper(),
                float(score),
                f"artifact={Path(artifact_path).name}",
            ))

        db.executemany(
            """
            INSERT INTO customer_risk_score
              (customer_id, text_id, model_id, risk_label, risk_score, explanation)
            VALUES
              (%s, %s, %s, %s, %s, %s)
            """,
            inserts
        )

        # 3b) maintain "latest" risk per customer (optimization for dashboard/top)
        # We keep history in customer_risk_score, and upsert the most recent record per customer.
        latest_rows = []
        for (customer_id, text_id, _model_id, risk_label, risk_score, explanation) in inserts:
            rs = db.fetchall(
                """
                SELECT risk_score_id, scored_at
                FROM customer_risk_score
                WHERE customer_id=%s AND text_id=%s AND model_id=%s
                ORDER BY scored_at DESC, risk_score_id DESC
                LIMIT 1
                """,
                (int(customer_id), int(text_id), int(model_id)),
            )
            if not rs:
                continue
            risk_score_id = int(rs[0][0])
            scored_at = rs[0][1]
            latest_rows.append((
                int(customer_id),
                risk_score_id,
                int(text_id),
                int(model_id),
                str(risk_label).upper(),
                float(risk_score),
                str(explanation),
                scored_at,
            ))

        if latest_rows:
            db.executemany(
                """
                INSERT INTO customer_risk_score_latest
                  (customer_id, risk_score_id, text_id, model_id, risk_label, risk_score, explanation, scored_at)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  risk_score_id=VALUES(risk_score_id),
                  text_id=VALUES(text_id),
                  model_id=VALUES(model_id),
                  risk_label=VALUES(risk_label),
                  risk_score=VALUES(risk_score),
                  explanation=VALUES(explanation),
                  scored_at=VALUES(scored_at)
                """,
                latest_rows,
            )

        # mark unprocessed texts as processed (safe in both modes)
        text_ids = [int(t["text_id"]) for t in texts]
        # build IN (...) safely
        placeholders = ",".join(["%s"] * len(text_ids))
        db.execute(
            f"""
            UPDATE unstructured_text
            SET is_processed=1, processed_at=NOW()
            WHERE text_id IN ({placeholders}) AND is_processed=0
            """,
            tuple(text_ids),
        )

        db.log_event(
            event_type="RESCORE" if (args.rescore_recent_days and args.rescore_recent_days > 0) else "INFER",
            entity_type="SYSTEM",
            entity_id=None,
            message=(
                f"{'Rescore' if (args.rescore_recent_days and args.rescore_recent_days > 0) else 'Inference'} completed: "
                f"model_id={model_id}, artifact={artifact_path}, texts_scored={len(text_ids)}, "
                f"rescore_recent_days={int(args.rescore_recent_days)}"
            ),
        )

        # 4) create premium adjustment suggestions (for ACTIVE policies only)
        # policy: based on latest risk per customer, update suggestion table
        # (simple demo: insert suggestions; you can choose to prevent duplicates in app layer)
        for t, label in zip(texts, preds):
            customer_id = int(t["customer_id"])
            pct = float(label_to_adjustment_pct(str(label).upper()))

            # find customer's active policy
            pol = db.fetchall_dict(
                """
                SELECT policy_id, base_premium
                FROM policy
                WHERE customer_id=%s AND status='ACTIVE'
                ORDER BY policy_id ASC
                LIMIT 1
                """,
                (customer_id,),
            )
            if not pol:
                continue

            policy_id = int(pol[0]["policy_id"])
            base_premium = float(pol[0]["base_premium"])

            # find latest risk_score_id for this customer and this text and model
            rs = db.fetchall(
                """
                SELECT risk_score_id, risk_score
                FROM customer_risk_score
                WHERE customer_id=%s AND text_id=%s AND model_id=%s
                ORDER BY scored_at DESC, risk_score_id DESC
                LIMIT 1
                """,
                (customer_id, int(t["text_id"]), int(model_id)),
            )
            if not rs:
                continue

            risk_score_id = int(rs[0][0])
            suggested = round(base_premium * (1.0 + pct / 100.0), 2)

            db.execute(
                """
                INSERT INTO policy_premium_adjustment
                  (policy_id, customer_id, model_id, risk_score_id, adjustment_pct, suggested_premium, decision_status)
                VALUES
                  (%s, %s, %s, %s, %s, %s, 'SUGGESTED')
                """,
                (policy_id, customer_id, int(model_id), risk_score_id, pct, suggested),
            )

        db.commit()
        print(f"✅ Done. Scored {len(text_ids)} text(s). Risk scores + suggestions written back to MySQL.")
        print(f"Used model_id={model_id}, artifact={artifact_path}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
