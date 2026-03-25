from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import ResultStatus, enum_values
from app.db.mixins import TimestampMixin


class RunResult(TimestampMixin, Base):
    __tablename__ = "run_results"
    __table_args__ = (
        UniqueConstraint("run_id", "dataset_case_id", name="uq_run_result_case"),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_run_results_latency_non_negative",
        ),
        Index("ix_run_results_run_status", "run_id", "status"),
        Index("ix_run_results_run_created_at", "run_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    dataset_case_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dataset_cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ResultStatus] = mapped_column(
        Enum(
            ResultStatus,
            name="result_status_enum",
            native_enum=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    expected_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actual_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["Run"] = relationship("Run", back_populates="results")
