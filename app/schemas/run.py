from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import ResultStatus, RunStatus


class CreateRunRequest(BaseModel):
    dataset_id: UUID
    target_id: UUID
    config: dict[str, Any] = Field(default_factory=dict)


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    target_id: UUID
    status: RunStatus
    summary_json: dict[str, Any]
    metrics_json: dict[str, Any]
    config_json: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RunResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    dataset_case_id: UUID
    status: ResultStatus
    score: float | None
    expected_json: dict[str, Any]
    actual_json: dict[str, Any] | None
    latency_ms: int | None
    error_type: str | None
    error_message: str | None
    created_at: datetime


class RunSummaryResponse(BaseModel):
    run: RunResponse
    results: list[RunResultResponse]
