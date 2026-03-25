from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import TargetType, enum_values
from app.db.mixins import TimestampMixin


class Target(TimestampMixin, Base):
    __tablename__ = "targets"
    __table_args__ = (
        CheckConstraint("timeout_ms > 0", name="ck_targets_timeout_ms_positive"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    target_type: Mapped[TargetType] = mapped_column(
        Enum(
            TargetType,
            name="target_type_enum",
            native_enum=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    endpoint_path: Mapped[str] = mapped_column(String(200), nullable=False)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    headers_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
