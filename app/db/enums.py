from enum import StrEnum


class TaskType(StrEnum):
    CLASSIFICATION = "classification"
    QA_WITH_CONTEXT = "qa_with_context"
    STRUCTURED_EXTRACTION = "structured_extraction"
    TOOL_USING_AGENT = "tool_using_agent"


class TargetType(StrEnum):
    HTTP = "http"
    PYTHON_ADAPTER = "python_adapter"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResultStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    INVALID_CASE = "invalid_case"


def enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]
