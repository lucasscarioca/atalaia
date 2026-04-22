from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.enums import ResultStatus, RunStatus
from app.models.remote import ApiToken, EvalCase, EvalSuite, Project, Run, RunArtifact, RunCaseResult
from app.schemas.remote import CaseCreate, RunComplete, RunCreate, SuiteCreate


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        elif cleaned and cleaned[-1] != "-":
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "suite"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return f"oe_{secrets.token_urlsafe(32)}"


def get_or_create_project(db: Session, *, slug: str, name: str | None = None, description: str | None = None) -> Project:
    project = db.scalar(select(Project).where(Project.slug == slug))
    if project is not None:
        return project
    project = Project(slug=slug, name=name or slug.replace("-", " ").title(), description=description)
    db.add(project)
    db.flush()
    return project


def create_api_token(db: Session, *, name: str) -> tuple[ApiToken, str]:
    token = generate_token()
    prefix = token[:12]
    row = ApiToken(name=name, token_prefix=prefix, token_hash=hash_token(token))
    db.add(row)
    db.flush()
    return row, token


def find_token_by_plaintext(db: Session, token: str) -> ApiToken | None:
    token_hash = hash_token(token)
    return db.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash, ApiToken.revoked_at.is_(None)))


def register_suite(
    db: Session,
    *,
    project_slug: str,
    suite: SuiteCreate,
) -> tuple[Project, EvalSuite, list[EvalCase]]:
    project = get_or_create_project(db, slug=project_slug)
    suite_row = db.scalar(
        select(EvalSuite).where(EvalSuite.project_id == project.id, EvalSuite.slug == suite.slug)
    )
    if suite_row is None:
        suite_row = EvalSuite(
            project_id=project.id,
            slug=suite.slug,
            name=suite.name,
            description=suite.description,
            metadata_json=suite.metadata,
        )
        db.add(suite_row)
        db.flush()
    else:
        suite_row.name = suite.name
        suite_row.description = suite.description
        suite_row.metadata_json = suite.metadata

    case_rows: list[EvalCase] = []
    existing_cases = {case.case_key: case for case in suite_row.cases}
    for case in suite.cases:
        row = existing_cases.get(case.case_key)
        if row is None:
            row = EvalCase(
                suite_id=suite_row.id,
                case_key=case.case_key,
                input_json=case.input,
                expected_json=case.expected,
                metadata_json=case.metadata,
            )
            db.add(row)
        else:
            row.input_json = case.input
            row.expected_json = case.expected
            row.metadata_json = case.metadata
        case_rows.append(row)

    db.flush()
    return project, suite_row, case_rows


def create_run(db: Session, payload: RunCreate, *, token: ApiToken | None) -> Run:
    suite_payload = SuiteCreate(
        slug=slugify(payload.suite.name),
        name=payload.suite.name,
        description=payload.suite.description,
        metadata=payload.suite.metadata,
        cases=[
            CaseCreate(case_key=case.id, input=case.input, expected=case.expected, metadata=case.metadata)
            for case in payload.suite.cases
        ],
    )
    project, suite_row, case_rows = register_suite(db, project_slug=payload.project_slug, suite=suite_payload)
    case_lookup = {case.case_key: case for case in case_rows}
    summary = {"total": len(payload.suite.cases), "passed": 0, "failed": 0, "error": 0, "invalid_case": len(payload.suite.cases)}
    run = Run(
        project_id=project.id,
        suite_id=suite_row.id,
        reference_run_id=payload.reference_run_id,
        status=RunStatus.QUEUED.value,
        summary_json=summary,
        metrics_json={"accuracy": None, "average_latency_ms": None},
        config_json={
            "suite_spec": payload.suite_spec,
            "suite": payload.suite.model_dump(),
            "bundle": payload.bundle.model_dump(),
            "project_slug": payload.project_slug,
        },
        requested_by_token_id=token.id if token is not None else None,
    )
    db.add(run)
    db.flush()

    for case in payload.suite.cases:
        db.add(
            RunCaseResult(
                run_id=run.id,
                case_id=case_lookup.get(case.id).id if case.id in case_lookup else None,
                case_key=case.id,
                status=ResultStatus.INVALID_CASE.value,
                score=None,
                expected_json=case.expected,
                actual_json=None,
                latency_ms=None,
                error_type="not_implemented",
                error_message="remote execution is not implemented yet",
            )
        )

    db.add(
        RunArtifact(
            run_id=run.id,
            artifact_key="suite.bundle",
            kind="bundle",
            path=None,
            mime_type="application/json",
            payload_json={
                "suite": payload.suite.model_dump(),
                "bundle": payload.bundle.model_dump(),
            },
        )
    )
    db.flush()
    return run


def list_runs(db: Session, *, status: str | None = None, project_slug: str | None = None) -> list[Run]:
    query = select(Run).join(Project)
    if status is not None:
        query = query.where(Run.status == status)
    if project_slug is not None:
        query = query.where(Project.slug == project_slug)
    query = query.order_by(Run.created_at.desc())
    return list(db.scalars(query).all())


def start_run(db: Session, run: Run) -> Run:
    if run.status != RunStatus.QUEUED.value:
        raise ValueError(f"run {run.id} cannot start from status {run.status}")
    run.status = RunStatus.RUNNING.value
    run.started_at = datetime.now(UTC)
    db.add(run)
    db.flush()
    return run


def complete_run(db: Session, run: Run, payload: RunComplete) -> Run:
    if run.status != RunStatus.RUNNING.value:
        raise ValueError(f"run {run.id} cannot complete from status {run.status}")

    db.execute(delete(RunCaseResult).where(RunCaseResult.run_id == run.id))
    db.execute(
        delete(RunArtifact).where(RunArtifact.run_id == run.id, RunArtifact.artifact_key != "suite.bundle")
    )

    case_lookup = {case.case_key: case.id for case in run.suite.cases}
    for case in payload.cases:
        db.add(
            RunCaseResult(
                run_id=run.id,
                case_id=case_lookup.get(case.case_id),
                case_key=case.case_id,
                status=ResultStatus(case.status).value,
                score=case.score,
                expected_json=case.expected,
                actual_json=case.actual,
                latency_ms=case.latency_ms,
                error_type="execution_error" if case.status in {"error", "failed"} else None,
                error_message=case.error,
            )
        )

    for artifact in payload.artifacts:
        db.add(
            RunArtifact(
                run_id=run.id,
                artifact_key=artifact.artifact_key,
                kind=artifact.kind,
                path=artifact.path,
                mime_type=artifact.mime_type,
                payload_json=artifact.payload,
            )
        )

    run.status = payload.status
    run.summary_json = payload.summary.model_dump()
    run.metrics_json = payload.metrics
    run.completed_at = datetime.now(UTC)
    db.add(run)
    db.flush()
    return run


def get_run_summary(run: Run) -> dict[str, int]:
    summary = {"total": 0, "passed": 0, "failed": 0, "error": 0, "invalid_case": 0}
    summary.update({k: int(v) for k, v in run.summary_json.items() if k in summary})
    return summary


def mark_token_used(db: Session, token: ApiToken) -> None:
    token.last_used_at = datetime.now(UTC)
    db.add(token)
