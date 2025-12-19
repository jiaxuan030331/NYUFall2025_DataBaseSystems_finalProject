from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customer"

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class Policy(Base):
    __tablename__ = "policy"

    policy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.customer_id"))
    product_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_premium: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class UnstructuredText(Base):
    __tablename__ = "unstructured_text"

    text_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.customer_id"))
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingested_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class MlModelMetadata(Base):
    __tablename__ = "ml_model_metadata"

    model_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    algorithm: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trained_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    trained_data_from: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    trained_data_to: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    eval_metric_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    eval_metric_value: Mapped[object | None] = mapped_column(Numeric(10, 6), nullable=True)
    is_active: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class CustomerRiskScoreLatest(Base):
    __tablename__ = "customer_risk_score_latest"

    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customer.customer_id"), primary_key=True)
    risk_score_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("unstructured_text.text_id"), nullable=True)
    model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ml_model_metadata.model_id"), nullable=True)
    risk_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_score: Mapped[object | None] = mapped_column(Numeric(10, 6), nullable=True)
    explanation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scored_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


class PolicyPremiumAdjustment(Base):
    __tablename__ = "policy_premium_adjustment"

    adjustment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("policy.policy_id"), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customer.customer_id"), nullable=True)
    model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ml_model_metadata.model_id"), nullable=True)
    risk_score_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustment_pct: Mapped[object | None] = mapped_column(Numeric(6, 2), nullable=True)
    suggested_premium: Mapped[object | None] = mapped_column(Numeric(12, 2), nullable=True)
    decision_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)


