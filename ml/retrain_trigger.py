# ml/retrain_trigger.py
from __future__ import annotations

import argparse
import subprocess
import sys

from db import DBConfig, MySQL


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold_new_texts", type=int, default=20, help="If unprocessed texts >= threshold, trigger retrain")
    ap.add_argument("--train_csv", required=True, help="Labeled training csv path")
    ap.add_argument("--activate", action="store_true", help="Activate new model after retraining")
    args = ap.parse_args()

    db = MySQL(DBConfig.from_env())
    try:
        cnt = db.fetchall(
            "SELECT COUNT(*) FROM unstructured_text WHERE is_processed=0"
        )[0][0]
        cnt = int(cnt)

        if cnt < args.threshold_new_texts:
            print(f"No retrain. Unprocessed texts={cnt} < threshold={args.threshold_new_texts}")
            return

        db.log_event("RETRAIN_START", "SYSTEM", None, f"Trigger retrain: unprocessed_texts={cnt} >= {args.threshold_new_texts}")
        db.commit()

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Trigger training script
    cmd = [
        sys.executable, "ml/risk_model_training.py",
        "--train_csv", args.train_csv,
        "--model_name", "risk_classifier",
        "--artifacts_dir", "artifacts",
    ]
    if args.activate:
        cmd.append("--activate")

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)
    print("✅ Retrain finished.")


if __name__ == "__main__":
    main()
