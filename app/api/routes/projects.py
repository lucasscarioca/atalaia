from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, require_api_token
from app.models.remote import Project
from app.schemas.remote import (
    CaseRead,
    ProjectCreate,
    ProjectRead,
    SuiteCreate,
    SuiteRead,
    SuiteRegistrationResponse,
)
from app.services.remote import get_or_create_project, register_suite

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(payload: ProjectCreate, db: DBSession, _token=Depends(require_api_token)) -> ProjectRead:
    project = get_or_create_project(db, slug=payload.slug, name=payload.name, description=payload.description)
    db.commit()
    return ProjectRead.model_validate(project)


@router.get("/{project_slug}", response_model=ProjectRead)
def get_project(project_slug: str, db: DBSession, _token=Depends(require_api_token)) -> ProjectRead:
    project = db.scalar(select(Project).where(Project.slug == project_slug))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return ProjectRead.model_validate(project)


@router.post("/{project_slug}/suites", response_model=SuiteRegistrationResponse)
def create_suite(
    project_slug: str, payload: SuiteCreate, db: DBSession, _token=Depends(require_api_token)
) -> SuiteRegistrationResponse:
    project, suite, cases = register_suite(db, project_slug=project_slug, suite=payload)
    db.commit()
    return SuiteRegistrationResponse(
        project=ProjectRead.model_validate(project),
        suite=SuiteRead.model_validate(suite),
        cases=[CaseRead.model_validate(case) for case in cases],
    )
