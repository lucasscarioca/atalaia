from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.enums import ResultStatus, RunStatus
from app.db.session import get_db
from app.models.run import Run
from app.models.run_result import RunResult
from app.schemas.run import (
    CreateRunRequest,
    RunResponse,
    RunResultResponse,
    RunSummaryResponse,
)
from app.services import runs as run_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: CreateRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Run:
    try:
        run = run_service.create_run(db, payload)
    except run_service.DatasetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        ) from None
    except run_service.TargetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        ) from None
    except run_service.UnsupportedTaskTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported task_type '{exc.args[0]}' for run execution",
        ) from None
    except run_service.UnsupportedTargetTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported target_type '{exc.args[0]}' for run execution",
        ) from None

    background_tasks.add_task(run_service.execute_run_in_background, run.id)
    return run


@router.get("", response_model=list[RunResponse])
def list_runs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    run_status: RunStatus | None = Query(default=None, alias="status"),
    dataset_id: UUID | None = Query(default=None),
    target_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Run]:
    return run_service.list_runs(
        db,
        limit=limit,
        offset=offset,
        status=run_status,
        dataset_id=dataset_id,
        target_id=target_id,
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(run_id: UUID, db: Session = Depends(get_db)) -> Run:
    try:
        return run_service.get_run_or_raise(db, run_id)
    except run_service.RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from None


@router.get("/{run_id}/summary", response_model=RunSummaryResponse)
def get_run_summary(
    run_id: UUID, db: Session = Depends(get_db)
) -> RunSummaryResponse:
    try:
        run, results = run_service.get_run_summary_or_raise(db, run_id)
    except run_service.RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from None

    return RunSummaryResponse(
        run=RunResponse.model_validate(run),
        results=[RunResultResponse.model_validate(result) for result in results],
    )


@router.get("/{run_id}/results", response_model=list[RunResultResponse])
def list_run_results(
    run_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    result_status: ResultStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[RunResult]:
    try:
        return run_service.list_run_results(
            db, run_id, limit=limit, offset=offset, status=result_status
        )
    except run_service.RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        ) from None
