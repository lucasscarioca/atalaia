from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetCase
from app.schemas.dataset import CreateDatasetRequest, ImportDatasetCasesRequest


class DatasetNotFoundError(Exception):
    pass


class DuplicateCaseKeysInPayloadError(Exception):
    def __init__(self, case_keys: list[str]) -> None:
        self.case_keys = case_keys
        super().__init__("Duplicate case_key values in import payload")


class DatasetCaseConflictError(Exception):
    pass


class DatasetTaskTypeMismatchError(Exception):
    def __init__(self, case_task_type: str, dataset_task_type: str) -> None:
        self.case_task_type = case_task_type
        self.dataset_task_type = dataset_task_type
        super().__init__(
            f"Case task_type '{case_task_type}' does not match dataset task_type '{dataset_task_type}'"
        )


def create_dataset(db: Session, payload: CreateDatasetRequest) -> Dataset:
    dataset = Dataset(
        name=payload.name,
        task_type=payload.task_type,
        description=payload.description,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


def list_datasets(db: Session, *, limit: int, offset: int) -> list[Dataset]:
    statement = (
        select(Dataset).order_by(Dataset.created_at.desc()).limit(limit).offset(offset)
    )
    return list(db.scalars(statement).all())


def get_dataset_or_raise(db: Session, dataset_id: UUID) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise DatasetNotFoundError
    return dataset


def import_dataset_cases(
    db: Session, dataset_id: UUID, payload: ImportDatasetCasesRequest
) -> list[DatasetCase]:
    dataset = get_dataset_or_raise(db, dataset_id)

    case_key_counts = Counter(case.case_key for case in payload.cases)
    duplicate_case_keys = sorted(
        case_key for case_key, count in case_key_counts.items() if count > 1
    )
    if duplicate_case_keys:
        raise DuplicateCaseKeysInPayloadError(duplicate_case_keys)

    cases: list[DatasetCase] = []
    for case in payload.cases:
        if case.task_type != dataset.task_type:
            raise DatasetTaskTypeMismatchError(
                case_task_type=case.task_type.value,
                dataset_task_type=dataset.task_type.value,
            )

        dataset_case = DatasetCase(
            dataset_id=dataset.id,
            case_key=case.case_key,
            task_type=case.task_type,
            input_json=case.input.model_dump(),
            expected_json=case.expected.model_dump(),
            metadata_json=case.metadata,
        )
        db.add(dataset_case)
        cases.append(dataset_case)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DatasetCaseConflictError from None

    for case in cases:
        db.refresh(case)

    return cases


def list_dataset_cases(
    db: Session, dataset_id: UUID, *, limit: int, offset: int
) -> list[DatasetCase]:
    get_dataset_or_raise(db, dataset_id)
    statement = (
        select(DatasetCase)
        .where(DatasetCase.dataset_id == dataset_id)
        .order_by(DatasetCase.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())
