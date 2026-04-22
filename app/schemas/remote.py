from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenCreate(_Model):
    name: str = Field(min_length=1, max_length=200)


class TokenCreated(_Model):
    token_id: UUID
    name: str
    token_prefix: str
    token: str


class ProjectCreate(_Model):
    slug: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ProjectRead(_Model):
    id: UUID
    slug: str
    name: str
    description: str | None
    created_at: datetime


class CaseCreate(_Model):
    case_key: str = Field(min_length=1, max_length=120)
    input: dict[str, Any]
    expected: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class SuiteCreate(_Model):
    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    cases: list[CaseCreate] = Field(default_factory=list)


class SuiteRead(_Model):
    id: UUID
    project_id: UUID
    slug: str
    name: str
    description: str | None
    metadata_json: dict[str, Any]
    created_at: datetime


class CaseRead(_Model):
    id: UUID
    suite_id: UUID
    case_key: str
    input_json: dict[str, Any]
    expected_json: dict[str, Any]
    metadata_json: dict[str, Any]
    created_at: datetime


class SuiteRegistrationResponse(_Model):
    project: ProjectRead
    suite: SuiteRead
    cases: list[CaseRead]


class RemoteSuiteCase(_Model):
    id: str
    input: dict[str, Any]
    expected: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemoteSuite(_Model):
    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    cases: list[RemoteSuiteCase] = Field(default_factory=list)


class SuiteBundle(_Model):
    format: Literal["zip"] = "zip"
    module_name: str = Field(min_length=1)
    object_name: str = Field(min_length=1)
    package_name: str = Field(min_length=1)
    archive_base64: str = Field(min_length=1)


class RunCreate(_Model):
    suite_spec: str = Field(min_length=1)
    suite: RemoteSuite
    bundle: SuiteBundle
    project_slug: str = Field(default="default", min_length=1, max_length=100)
    reference_run_id: UUID | None = None


class RunSummary(_Model):
    total: int = 0
    passed: int = 0
    failed: int = 0
    error: int = 0
    invalid_case: int = 0


class RunResultRead(_Model):
    case_id: str
    status: Literal["passed", "failed", "error", "invalid_case"]
    score: float | None
    expected: dict[str, Any]
    actual: dict[str, Any] | None
    latency_ms: int | None
    error: str | None


class RunCaseWrite(_Model):
    case_id: str
    status: Literal["passed", "failed", "error", "invalid_case"]
    score: float | None
    expected: dict[str, Any]
    actual: dict[str, Any] | None
    latency_ms: int | None
    error: str | None = None


class RunArtifactWrite(_Model):
    artifact_key: str
    kind: str
    path: str | None = None
    mime_type: str | None = None
    payload: Any = None


class RunComplete(_Model):
    status: Literal["completed", "failed"]
    summary: RunSummary
    metrics: dict[str, Any]
    cases: list[RunCaseWrite] = Field(default_factory=list)
    artifacts: list[RunArtifactWrite] = Field(default_factory=list)


class RunListRead(_Model):
    run_id: UUID
    project_id: UUID
    suite_id: UUID
    suite_name: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ArtifactRead(_Model):
    artifact_id: str
    kind: str
    path: str | None
    mime_type: str | None
    payload: Any | None = None


class RunRead(_Model):
    run_id: UUID
    project_id: UUID
    suite_id: UUID
    suite_name: str
    reference_run_id: UUID | None
    status: Literal["queued", "running", "completed", "failed"]
    config: dict[str, Any]
    summary: RunSummary
    metrics: dict[str, Any]
    cases: list[RunResultRead]
    artifacts: list[ArtifactRead]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RunCreateResponse(_Model):
    run_id: UUID
    status: Literal["queued", "running", "completed", "failed"]
