from app.db.enums import TaskType
from app.schemas.dataset import ClassificationCaseCreate


def test_classification_case_schema_defaults() -> None:
    case = ClassificationCaseCreate(
        case_key="intent-001",
        input={"text": "cancel my subscription"},
        expected={"label": "cancellation"},
    )

    assert case.task_type == TaskType.CLASSIFICATION
    assert case.input.text == "cancel my subscription"
    assert case.expected.label == "cancellation"
