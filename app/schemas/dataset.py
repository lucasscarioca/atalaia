from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import TaskType


class CreateDatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    task_type: TaskType = TaskType.CLASSIFICATION
    description: str | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    task_type: TaskType
    description: str | None
    created_at: datetime


class ClassificationInput(BaseModel):
    text: str = Field(min_length=1)


class ClassificationExpected(BaseModel):
    label: str = Field(min_length=1)


class ClassificationCaseCreate(BaseModel):
    case_key: str = Field(min_length=1, max_length=200)
    task_type: TaskType = TaskType.CLASSIFICATION
    input: ClassificationInput
    expected: ClassificationExpected
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassificationCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    dataset_id: UUID
    case_key: str
    task_type: TaskType
    input: dict[str, Any] = Field(alias="input_json")
    expected: dict[str, Any] = Field(alias="expected_json")
    metadata: dict[str, Any] = Field(alias="metadata_json")
    created_at: datetime


class ImportDatasetCasesRequest(BaseModel):
    format: Literal["jsonl", "csv", "manual"] = "manual"
    cases: list[ClassificationCaseCreate] = Field(default_factory=list, min_length=1)


class ImportDatasetCasesResponse(BaseModel):
    dataset_id: UUID
    imported_count: int
    cases: list[ClassificationCaseResponse]
