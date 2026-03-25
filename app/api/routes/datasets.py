from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.dataset import Dataset
from app.schemas.dataset import (
    ClassificationCaseResponse,
    CreateDatasetRequest,
    DatasetResponse,
    ImportDatasetCasesRequest,
    ImportDatasetCasesResponse,
)
from app.services import datasets as dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_dataset(
    payload: CreateDatasetRequest, db: Session = Depends(get_db)
) -> Dataset:
    return dataset_service.create_dataset(db, payload)


@router.get("", response_model=list[DatasetResponse])
def list_datasets(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Dataset]:
    return dataset_service.list_datasets(db, limit=limit, offset=offset)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: UUID, db: Session = Depends(get_db)) -> Dataset:
    try:
        return dataset_service.get_dataset_or_raise(db, dataset_id)
    except dataset_service.DatasetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from None


@router.post(
    "/{dataset_id}/cases:import",
    response_model=ImportDatasetCasesResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_dataset_cases(
    dataset_id: UUID, payload: ImportDatasetCasesRequest, db: Session = Depends(get_db)
) -> ImportDatasetCasesResponse:
    try:
        cases = dataset_service.import_dataset_cases(db, dataset_id, payload)
    except dataset_service.DatasetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from None
    except dataset_service.DuplicateCaseKeysInPayloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate case_key values in import payload",
                "case_keys": exc.case_keys,
            },
        ) from None
    except dataset_service.DatasetTaskTypeMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except dataset_service.DatasetCaseConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more case_key values already exist in this dataset",
        ) from None

    return ImportDatasetCasesResponse(
        dataset_id=dataset_id,
        imported_count=len(cases),
        cases=[ClassificationCaseResponse.model_validate(case) for case in cases],
    )


@router.get("/{dataset_id}/cases", response_model=list[ClassificationCaseResponse])
def list_dataset_cases(
    dataset_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ClassificationCaseResponse]:
    try:
        cases = dataset_service.list_dataset_cases(
            db, dataset_id, limit=limit, offset=offset
        )
    except dataset_service.DatasetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found"
        ) from None

    return [ClassificationCaseResponse.model_validate(case) for case in cases]
