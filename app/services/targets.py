from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import TargetType
from app.models.target import Target
from app.schemas.target import CreateTargetRequest


class TargetNotFoundError(Exception):
    pass


class TargetConflictError(Exception):
    pass


def create_target(db: Session, payload: CreateTargetRequest) -> Target:
    target = Target(
        name=payload.name,
        target_type=payload.target_type,
        base_url=payload.base_url,
        endpoint_path=payload.endpoint_path,
        timeout_ms=payload.timeout_ms,
        headers_json=payload.headers,
    )
    db.add(target)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise TargetConflictError from None
    db.refresh(target)
    return target


def list_targets(
    db: Session, *, limit: int, offset: int, target_type: TargetType | None = None
) -> list[Target]:
    statement = select(Target)
    if target_type is not None:
        statement = statement.where(Target.target_type == target_type)

    statement = statement.order_by(Target.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement).all())


def get_target_or_raise(db: Session, target_id: UUID) -> Target:
    target = db.get(Target, target_id)
    if target is None:
        raise TargetNotFoundError
    return target
