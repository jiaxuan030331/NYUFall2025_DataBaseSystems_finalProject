# ml/db.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple, List, Dict

import mysql.connector


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str

    @staticmethod
    def from_env() -> "DBConfig":
        return DBConfig(
            host=os.getenv("DB_HOST", "101.47.177.55"),
            port=int(os.getenv("DB_PORT", "3308")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "admin123"),
            database=os.getenv("DB_NAME", "insurance_ods"),
        )


class MySQL:
    def __init__(self, cfg: DBConfig):
        self.cfg = cfg
        self.conn = mysql.connector.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            autocommit=False,
        )

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> int:
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        rowcount = cur.rowcount
        cur.close()
        return rowcount

    def executemany(self, sql: str, seq_params: Iterable[Sequence[Any]]) -> int:
        cur = self.conn.cursor()
        cur.executemany(sql, list(seq_params))
        rowcount = cur.rowcount
        cur.close()
        return rowcount

    def fetchall(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Tuple[Any, ...]]:
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows

    def fetchall_dict(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    # ---------- Project-specific helpers ----------

    def get_active_model_id(self, model_name: str = "risk_classifier") -> Optional[int]:
        rows = self.fetchall(
            """
            SELECT model_id
            FROM ml_model_metadata
            WHERE model_name=%s AND is_active=1
            ORDER BY trained_at DESC
            LIMIT 1
            """,
            (model_name,),
        )
        return int(rows[0][0]) if rows else None

    def log_event(self, event_type: str, entity_type: str = "SYSTEM", entity_id: Optional[int] = None, message: str = ""):
        self.execute(
            """
            INSERT INTO pipeline_event(event_type, entity_type, entity_id, message)
            VALUES (%s, %s, %s, %s)
            """,
            (event_type, entity_type, entity_id, message[:2000]),
        )
