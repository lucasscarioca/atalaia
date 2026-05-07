from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DBSession, require_api_token
from app.models.remote import Run, RunArtifact, RunCaseResult
from app.schemas.remote import (
    ArtifactRead,
    RunComplete,
    RunCreate,
    RunCreateResponse,
    RunListRead,
    RunRead,
    RunResultRead,
    RunSummary,
)
from app.services.remote import complete_run, create_run, get_run_summary, list_runs, start_run

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunListRead])
def list_runs_endpoint(
    db: DBSession,
    _token=Depends(require_api_token),
    status_filter: str | None = None,
    project_slug: str | None = None,
) -> list[RunListRead]:
    runs = list_runs(db, status=status_filter, project_slug=project_slug)
    return [
        RunListRead(
            run_id=run.id,
            project_id=run.project_id,
            suite_id=run.suite_id,
            suite_name=run.suite.name,
            status=run.status,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        for run in runs
    ]


@router.post("/runs", response_model=RunCreateResponse)
def create_run_endpoint(payload: RunCreate, db: DBSession, token=Depends(require_api_token)) -> RunCreateResponse:
    run = create_run(db, payload, token=token)
    db.commit()
    return RunCreateResponse(run_id=run.id, status=run.status)


@router.post("/runs/{run_id}/start", response_model=RunRead)
def start_run_endpoint(run_id: UUID, db: DBSession, _token=Depends(require_api_token)) -> RunRead:
    run = db.scalar(select(Run).where(Run.id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    try:
        start_run(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(run)
    return _serialize_run(db, run)


@router.post("/runs/{run_id}/complete", response_model=RunRead)
def complete_run_endpoint(
    run_id: UUID, payload: RunComplete, db: DBSession, _token=Depends(require_api_token)
) -> RunRead:
    run = db.scalar(select(Run).where(Run.id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    try:
        complete_run(db, run, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    db.refresh(run)
    return _serialize_run(db, run)


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: UUID, db: DBSession, _token=Depends(require_api_token)) -> RunRead:
    run = db.scalar(select(Run).where(Run.id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return _serialize_run(db, run)


def _serialize_run(db: DBSession, run: Run) -> RunRead:
    results = db.scalars(select(RunCaseResult).where(RunCaseResult.run_id == run.id)).all()
    artifacts = db.scalars(select(RunArtifact).where(RunArtifact.run_id == run.id)).all()

    return RunRead(
        run_id=run.id,
        project_id=run.project_id,
        suite_id=run.suite_id,
        suite_name=run.suite.name,
        reference_run_id=run.reference_run_id,
        status=run.status,
        config=run.config_json,
        summary=RunSummary(**get_run_summary(run)),
        metrics=run.metrics_json,
        cases=[
            RunResultRead(
                case_id=result.case_key,
                status=result.status,
                score=result.score,
                expected=result.expected_json,
                actual=result.actual_json,
                latency_ms=result.latency_ms,
                error=(result.error_message if result.error_message else None),
            )
            for result in results
        ],
        artifacts=[
            ArtifactRead(
                artifact_id=f"{artifact.id}:{artifact.artifact_key}",
                kind=artifact.kind,
                path=artifact.path,
                mime_type=artifact.mime_type,
                payload=_artifact_payload(artifact),
            )
            for artifact in artifacts
        ],
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/runs/{run_id}/artifacts", response_model=list[ArtifactRead])
def list_run_artifacts(run_id: UUID, db: DBSession, _token=Depends(require_api_token)) -> list[ArtifactRead]:
    run = db.scalar(select(Run).where(Run.id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    artifacts = db.scalars(select(RunArtifact).where(RunArtifact.run_id == run.id)).all()
    return [
        ArtifactRead(
            artifact_id=f"{artifact.id}:{artifact.artifact_key}",
            kind=artifact.kind,
            path=artifact.path,
            mime_type=artifact.mime_type,
            payload=_artifact_payload(artifact),
        )
        for artifact in artifacts
    ]


@router.get("/runs/{run_id}/artifacts/{artifact_key}", response_model=ArtifactRead)
def get_run_artifact(run_id: UUID, artifact_key: str, db: DBSession, _token=Depends(require_api_token)) -> ArtifactRead:
    run = db.scalar(select(Run).where(Run.id == run_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")

    artifact = db.scalar(
        select(RunArtifact).where(RunArtifact.run_id == run.id, RunArtifact.artifact_key == artifact_key)
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")

    return ArtifactRead(
        artifact_id=f"{artifact.id}:{artifact.artifact_key}",
        kind=artifact.kind,
        path=artifact.path,
        mime_type=artifact.mime_type,
        payload=_artifact_payload(artifact),
    )


def _artifact_payload(artifact: RunArtifact) -> object | None:
    if artifact.kind == "bundle" and isinstance(artifact.payload_json, dict) and "bundle" in artifact.payload_json:
        return artifact.payload_json["bundle"]
    return artifact.payload_json
