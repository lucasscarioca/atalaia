from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import ResultStatus, RunStatus
from app.db.mixins import TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    suites: Mapped[list[EvalSuite]] = relationship(back_populates="project", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="project", cascade="all, delete-orphan")


class EvalSuite(Base, TimestampMixin):
    __tablename__ = "eval_suites"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_eval_suites_project_slug"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped[Project] = relationship(back_populates="suites")
    cases: Mapped[list[EvalCase]] = relationship(back_populates="suite", cascade="all, delete-orphan")
    runs: Mapped[list[Run]] = relationship(back_populates="suite")


class EvalCase(Base, TimestampMixin):
    __tablename__ = "eval_cases"
    __table_args__ = (UniqueConstraint("suite_id", "case_key", name="uq_eval_cases_suite_key"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    suite_id: Mapped[UUID] = mapped_column(ForeignKey("eval_suites.id", ondelete="CASCADE"), nullable=False)
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    expected_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    suite: Mapped[EvalSuite] = relationship(back_populates="cases")
    results: Mapped[list[RunCaseResult]] = relationship(back_populates="case")


class ApiToken(Base, TimestampMixin):
    __tablename__ = "api_tokens"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    suite_id: Mapped[UUID] = mapped_column(ForeignKey("eval_suites.id", ondelete="RESTRICT"), nullable=False)
    reference_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[RunStatus] = mapped_column(String(32), nullable=False, default=RunStatus.QUEUED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    requested_by_token_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("api_tokens.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="runs")
    suite: Mapped[EvalSuite] = relationship(back_populates="runs")
    reference_run: Mapped[Run | None] = relationship(remote_side=[id])
    results: Mapped[list[RunCaseResult]] = relationship(back_populates="run", cascade="all, delete-orphan")
    artifacts: Mapped[list[RunArtifact]] = relationship(back_populates="run", cascade="all, delete-orphan")


class RunCaseResult(Base, TimestampMixin):
    __tablename__ = "run_case_results"
    __table_args__ = (UniqueConstraint("run_id", "case_key", name="uq_run_case_results_run_case_key"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[UUID | None] = mapped_column(ForeignKey("eval_cases.id", ondelete="SET NULL"), nullable=True)
    case_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ResultStatus] = mapped_column(String(32), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    actual_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    run: Mapped[Run] = relationship(back_populates="results")
    case: Mapped[EvalCase | None] = relationship(back_populates="results")


class RunArtifact(Base, TimestampMixin):
    __tablename__ = "run_artifacts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    artifact_key: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str | None] = mapped_column(Text(), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    run: Mapped[Run] = relationship(back_populates="artifacts")
