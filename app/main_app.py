# app/main_app.py
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Optional

from db_connection import DB, DBConfig


def log_event(db: DB, event_type: str, msg: str):
    db.execute(
        """
        INSERT INTO pipeline_event(event_type, entity_type, entity_id, message)
        VALUES (%s, 'SYSTEM', NULL, %s)
        """,
        (event_type, msg[:2000]),
    )


def show_active_model(db: DB):
    rows = db.fetchall_dict(
        """
        SELECT model_id, model_name, model_version, algorithm, trained_at, eval_metric_name, eval_metric_value, artifact_path
        FROM ml_model_metadata
        WHERE is_active=1
        ORDER BY trained_at DESC
        LIMIT 5
        """
    )
    if not rows:
        print("No active model.")
        return
    print("\nActive model(s):")
    for r in rows:
        print(f"- model_id={r['model_id']} {r['model_name']} {r['model_version']} {r['algorithm']} trained_at={r['trained_at']} metric={r['eval_metric_name']}={r['eval_metric_value']} artifact={r['artifact_path']}")


def show_active_model_orm():
    try:
        from sqlalchemy import desc, select

        from orm import get_session
        from models import MlModelMetadata
    except Exception as e:
        raise SystemExit(f"ORM dependencies not available. Install requirements.txt (SQLAlchemy, PyMySQL). Details: {e}")

    with get_session() as s:
        rows = s.execute(
            select(MlModelMetadata)
            .where(MlModelMetadata.is_active == 1)
            .order_by(desc(MlModelMetadata.trained_at))
            .limit(5)
        ).scalars().all()

        if not rows:
            print("No active model.")
            return

        print("\nActive model(s):")
        for r in rows:
            print(
                f"- model_id={r.model_id} {r.model_name} {r.model_version} {r.algorithm} "
                f"trained_at={r.trained_at} metric={r.eval_metric_name}={r.eval_metric_value} artifact={r.artifact_path}"
            )


def ingest_text(db: DB, customer_id: int, source_type: str, raw_text: str):
    db.execute(
        """
        INSERT INTO unstructured_text(customer_id, source_type, raw_text, is_processed)
        VALUES (%s, %s, %s, 0)
        """,
        (customer_id, source_type, raw_text),
    )
    log_event(db, "INGEST", f"Ingested text for customer_id={customer_id}, source_type={source_type}")
    db.commit()
    print("✅ Ingested unstructured text into DB.")


def run_inference(batch_size: int = 50):
    # call your existing ML script
    cmd = [sys.executable, "ml/risk_model_inference.py", "--batch_size", str(batch_size)]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)
    print("✅ Inference completed (risk + premium suggestion written back).")


def customer_dashboard(db: DB, customer_id: int):
    # Latest risk record + join to text + policy + latest adjustment
    rows = db.fetchall_dict(
        """
        SELECT
          c.customer_id, c.full_name,
          ut.text_id, ut.source_type, ut.ingested_at, ut.processed_at,
          LEFT(ut.raw_text, 160) AS text_preview,
          crs.risk_score_id, crs.risk_label, crs.risk_score, crs.scored_at,
          mm.model_version,
          p.policy_id, p.product_type, p.base_premium, p.status,
          ppa.adjustment_pct, ppa.suggested_premium, ppa.decision_status, ppa.created_at AS adjustment_time
        FROM customer c
        LEFT JOIN customer_risk_score_latest crs
          ON crs.customer_id = c.customer_id
        LEFT JOIN unstructured_text ut
          ON ut.text_id = crs.text_id
        LEFT JOIN ml_model_metadata mm
          ON mm.model_id = crs.model_id
        LEFT JOIN policy p
          ON p.customer_id = c.customer_id
        LEFT JOIN policy_premium_adjustment ppa
          ON ppa.customer_id = c.customer_id
        WHERE c.customer_id = %s
        ORDER BY ppa.created_at DESC
        LIMIT 1
        """,
        (customer_id,),
    )
    if not rows:
        print("Customer not found.")
        return

    r = rows[0]
    print("\n=== Customer Risk Dashboard ===")
    print(f"Customer: {r['customer_id']} | {r['full_name']}")
    print(f"Latest Text: text_id={r['text_id']} source={r['source_type']} ingested={r['ingested_at']} processed={r['processed_at']}")
    print(f"Text Preview: {r['text_preview']}")
    print(f"Risk: risk_score_id={r['risk_score_id']} label={r['risk_label']} score={r['risk_score']} scored_at={r['scored_at']} model={r['model_version']}")
    print(f"Policy: policy_id={r['policy_id']} type={r['product_type']} base={r['base_premium']} status={r['status']}")
    print(f"Premium Suggestion: pct={r['adjustment_pct']} suggested={r['suggested_premium']} status={r['decision_status']} at={r['adjustment_time']}")
    print("==============================\n")


def customer_dashboard_orm(customer_id: int):
    try:
        from sqlalchemy import and_, desc, func, select

        from orm import get_session
        from models import (
            Customer,
            CustomerRiskScoreLatest,
            MlModelMetadata,
            Policy,
            PolicyPremiumAdjustment,
            UnstructuredText,
        )
    except Exception as e:
        raise SystemExit(f"ORM dependencies not available. Install requirements.txt (SQLAlchemy, PyMySQL). Details: {e}")

    with get_session() as s:
        # Latest premium adjustment per customer (if any)
        latest_adj = (
            select(
                PolicyPremiumAdjustment.customer_id.label("customer_id"),
                func.max(PolicyPremiumAdjustment.created_at).label("max_created_at"),
            )
            .group_by(PolicyPremiumAdjustment.customer_id)
            .subquery()
        )

        stmt = (
            select(
                Customer.customer_id,
                Customer.full_name,
                UnstructuredText.text_id,
                UnstructuredText.source_type,
                UnstructuredText.ingested_at,
                UnstructuredText.processed_at,
                func.left(UnstructuredText.raw_text, 160).label("text_preview"),
                CustomerRiskScoreLatest.risk_score_id,
                CustomerRiskScoreLatest.risk_label,
                CustomerRiskScoreLatest.risk_score,
                CustomerRiskScoreLatest.scored_at,
                MlModelMetadata.model_version,
                Policy.policy_id,
                Policy.product_type,
                Policy.base_premium,
                Policy.status,
                PolicyPremiumAdjustment.adjustment_pct,
                PolicyPremiumAdjustment.suggested_premium,
                PolicyPremiumAdjustment.decision_status,
                PolicyPremiumAdjustment.created_at.label("adjustment_time"),
            )
            .select_from(Customer)
            .outerjoin(CustomerRiskScoreLatest, CustomerRiskScoreLatest.customer_id == Customer.customer_id)
            .outerjoin(UnstructuredText, UnstructuredText.text_id == CustomerRiskScoreLatest.text_id)
            .outerjoin(MlModelMetadata, MlModelMetadata.model_id == CustomerRiskScoreLatest.model_id)
            .outerjoin(Policy, Policy.customer_id == Customer.customer_id)
            .outerjoin(latest_adj, latest_adj.c.customer_id == Customer.customer_id)
            .outerjoin(
                PolicyPremiumAdjustment,
                and_(
                    PolicyPremiumAdjustment.customer_id == Customer.customer_id,
                    PolicyPremiumAdjustment.created_at == latest_adj.c.max_created_at,
                ),
            )
            .where(Customer.customer_id == customer_id)
            .limit(1)
        )

        row = s.execute(stmt).first()
        if not row:
            print("Customer not found.")
            return

        r = row._mapping
        print("\n=== Customer Risk Dashboard ===")
        print(f"Customer: {r['customer_id']} | {r['full_name']}")
        print(f"Latest Text: text_id={r['text_id']} source={r['source_type']} ingested={r['ingested_at']} processed={r['processed_at']}")
        print(f"Text Preview: {r['text_preview']}")
        print(f"Risk: risk_score_id={r['risk_score_id']} label={r['risk_label']} score={r['risk_score']} scored_at={r['scored_at']} model={r['model_version']}")
        print(f"Policy: policy_id={r['policy_id']} type={r['product_type']} base={r['base_premium']} status={r['status']}")
        print(f"Premium Suggestion: pct={r['adjustment_pct']} suggested={r['suggested_premium']} status={r['decision_status']} at={r['adjustment_time']}")
        print("==============================\n")


def top_high_risk(db: DB, top_n: int = 5):
    rows = db.fetchall_dict(
        """
        SELECT
          c.customer_id, c.full_name,
          crs.risk_label, crs.risk_score, crs.scored_at
        FROM customer c
        JOIN customer_risk_score_latest crs ON crs.customer_id=c.customer_id
        WHERE crs.scored_at >= DATE_SUB(CURDATE(), INTERVAL 2 YEAR)
        ORDER BY crs.risk_score DESC
        LIMIT %s
        """,
        (top_n,),
    )
    print(f"\nTop {top_n} high-risk customers (last 2 years):")
    for r in rows:
        print(f"- {r['customer_id']} {r['full_name']} | {r['risk_label']} {r['risk_score']} @ {r['scored_at']}")
    print()


def top_high_risk_orm(top_n: int = 5):
    try:
        from sqlalchemy import desc, select

        from orm import get_session
        from models import Customer, CustomerRiskScoreLatest
    except Exception as e:
        raise SystemExit(f"ORM dependencies not available. Install requirements.txt (SQLAlchemy, PyMySQL). Details: {e}")

    cutoff = datetime.now() - timedelta(days=365 * 2)

    with get_session() as s:
        rows = s.execute(
            select(
                Customer.customer_id,
                Customer.full_name,
                CustomerRiskScoreLatest.risk_label,
                CustomerRiskScoreLatest.risk_score,
                CustomerRiskScoreLatest.scored_at,
            )
            .select_from(Customer)
            .join(CustomerRiskScoreLatest, CustomerRiskScoreLatest.customer_id == Customer.customer_id)
            .where(CustomerRiskScoreLatest.scored_at >= cutoff)
            .order_by(desc(CustomerRiskScoreLatest.risk_score))
            .limit(top_n)
        ).all()

        print(f"\nTop {top_n} high-risk customers (last 2 years):")
        for r in rows:
            print(f"- {r.customer_id} {r.full_name} | {r.risk_label} {r.risk_score} @ {r.scored_at}")
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True, choices=["show_model", "ingest", "infer", "dashboard", "top", "pipeline"])
    ap.add_argument("--customer_id", type=int, default=0)
    ap.add_argument("--source_type", default="SUPPORT_CHAT",
                    choices=["CLAIM_DESCRIPTION", "CUSTOMER_REVIEW", "SUPPORT_CHAT", "OTHER"])
    ap.add_argument("--text", default="")
    ap.add_argument("--batch_size", type=int, default=50)
    ap.add_argument("--top_n", type=int, default=5)
    ap.add_argument("--use_orm", action="store_true", help="Use SQLAlchemy ORM for app read queries (show_model/dashboard/top)")
    ap.add_argument("--threshold_new_texts", type=int, default=20, help="For pipeline: trigger retrain if unprocessed texts >= threshold")
    ap.add_argument("--train_csv", default="", help="For pipeline: labeled training csv path used for retraining")
    ap.add_argument("--rescore_recent_days", type=int, default=0, help="For pipeline: after retrain, rescore texts ingested within last N days")
    args = ap.parse_args()

    if args.action == "infer":
        run_inference(args.batch_size)
        return

    if args.action == "pipeline":
        # Non-interactive orchestration:
        # 1) optional retrain trigger (if train_csv provided)
        # 2) run inference on unprocessed texts
        # 3) optional rescore of recent texts after (re)training/model activation
        if args.train_csv.strip():
            cmd = [
                sys.executable, "ml/retrain_trigger.py",
                "--threshold_new_texts", str(int(args.threshold_new_texts)),
                "--train_csv", args.train_csv.strip(),
                "--activate",
            ]
            print("Running:", " ".join(cmd))
            subprocess.check_call(cmd)
        else:
            print("Skipping retrain trigger (no --train_csv provided).")

        # Always score new/unprocessed texts
        run_inference(args.batch_size)

        # Optionally rescore recent window to refresh scores with the active model
        if args.rescore_recent_days and args.rescore_recent_days > 0:
            cmd = [
                sys.executable, "ml/risk_model_inference.py",
                "--batch_size", str(int(args.batch_size)),
                "--rescore_recent_days", str(int(args.rescore_recent_days)),
            ]
            print("Running:", " ".join(cmd))
            subprocess.check_call(cmd)
            print("✅ Rescore completed.")
        return

    db = DB(DBConfig.from_env())
    try:
        if args.action == "show_model":
            if args.use_orm:
                show_active_model_orm()
            else:
                show_active_model(db)

        elif args.action == "ingest":
            if args.customer_id <= 0 or not args.text.strip():
                raise SystemExit("ingest requires --customer_id and --text")
            ingest_text(db, args.customer_id, args.source_type, args.text)

        elif args.action == "dashboard":
            if args.customer_id <= 0:
                raise SystemExit("dashboard requires --customer_id")
            if args.use_orm:
                customer_dashboard_orm(args.customer_id)
            else:
                customer_dashboard(db, args.customer_id)

        elif args.action == "top":
            if args.use_orm:
                top_high_risk_orm(args.top_n)
            else:
                top_high_risk(db, args.top_n)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
