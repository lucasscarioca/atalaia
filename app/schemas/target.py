from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import TargetType


class CreateTargetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: TargetType = TargetType.HTTP
    base_url: str = Field(min_length=1)
    endpoint_path: str = Field(min_length=1, max_length=200)
    timeout_ms: int = Field(default=10000, gt=0)
    headers: dict[str, Any] | None = None


class UpdateTargetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: TargetType = TargetType.HTTP
    base_url: str = Field(min_length=1)
    endpoint_path: str = Field(min_length=1, max_length=200)
    timeout_ms: int = Field(default=10000, gt=0)
    headers: dict[str, Any] | None = None


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    target_type: TargetType
    base_url: str
    endpoint_path: str
    timeout_ms: int
    headers_json: dict[str, Any] | None
    created_at: datetime
