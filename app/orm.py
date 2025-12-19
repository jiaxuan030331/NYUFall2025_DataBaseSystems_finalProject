from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def get_engine_from_env(echo: bool = False) -> Engine:
    """
    SQLAlchemy engine for MySQL using PyMySQL.
    Uses the same DB_* env vars as the rest of the project.
    """
    host = _env("DB_HOST", "127.0.0.1")
    port = int(_env("DB_PORT", "3306"))
    user = _env("DB_USER", "root")
    password = _env("DB_PASSWORD", "")
    db = _env("DB_NAME", "insurance_ods")

    # Note: password may contain special chars; SQLAlchemy will handle URL escaping.
    url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"
    return create_engine(url, echo=echo, pool_pre_ping=True, future=True)


def get_session(echo: bool = False) -> Session:
    engine = get_engine_from_env(echo=echo)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal()


