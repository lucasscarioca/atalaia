from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.target import Target
from app.schemas.target import CreateTargetRequest, TargetResponse
from app.services import targets as target_service

router = APIRouter(prefix="/targets", tags=["targets"])


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(
    payload: CreateTargetRequest, db: Session = Depends(get_db)
) -> Target:
    try:
        return target_service.create_target(db, payload)
    except target_service.TargetConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Target name already exists",
        ) from None


@router.get("", response_model=list[TargetResponse])
def list_targets(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Target]:
    return target_service.list_targets(db, limit=limit, offset=offset)


@router.get("/{target_id}", response_model=TargetResponse)
def get_target(target_id: UUID, db: Session = Depends(get_db)) -> Target:
    try:
        return target_service.get_target_or_raise(db, target_id)
    except target_service.TargetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from None
