from app.db.enums import TaskType


def test_create_and_get_dataset(client, clean_db_tables) -> None:
    create_response = client.post(
        "/datasets",
        json={
            "name": "Support intents",
            "task_type": "classification",
            "description": "Seed support dataset",
        },
    )

    assert create_response.status_code == 201

    created_dataset = create_response.json()
    assert created_dataset["name"] == "Support intents"
    assert created_dataset["task_type"] == TaskType.CLASSIFICATION.value
    assert created_dataset["description"] == "Seed support dataset"

    get_response = client.get(f"/datasets/{created_dataset['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created_dataset


def test_list_datasets_returns_created_items(client, clean_db_tables) -> None:
    first_response = client.post(
        "/datasets",
        json={"name": "Dataset one", "task_type": "classification"},
    )
    second_response = client.post(
        "/datasets",
        json={"name": "Dataset two", "task_type": "classification"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    list_response = client.get("/datasets")

    assert list_response.status_code == 200
    datasets = list_response.json()

    assert len(datasets) == 2
    assert datasets[0]["name"] == "Dataset two"
    assert datasets[1]["name"] == "Dataset one"


def test_list_datasets_supports_limit_and_offset(client, clean_db_tables) -> None:
    client.post(
        "/datasets",
        json={"name": "Dataset one", "task_type": "classification"},
    )
    client.post(
        "/datasets",
        json={"name": "Dataset two", "task_type": "classification"},
    )
    client.post(
        "/datasets",
        json={"name": "Dataset three", "task_type": "classification"},
    )

    list_response = client.get("/datasets?limit=1&offset=1")

    assert list_response.status_code == 200
    datasets = list_response.json()

    assert len(datasets) == 1
    assert datasets[0]["name"] == "Dataset two"


def test_list_datasets_supports_task_type_filter(client, clean_db_tables) -> None:
    client.post(
        "/datasets",
        json={"name": "Classification dataset", "task_type": "classification"},
    )
    client.post(
        "/datasets",
        json={"name": "QA dataset", "task_type": "qa_with_context"},
    )

    list_response = client.get("/datasets?task_type=qa_with_context")

    assert list_response.status_code == 200
    datasets = list_response.json()

    assert len(datasets) == 1
    assert datasets[0]["name"] == "QA dataset"


def test_import_dataset_cases(client, clean_db_tables) -> None:
    create_response = client.post(
        "/datasets",
        json={"name": "Importable dataset", "task_type": "classification"},
    )
    dataset_id = create_response.json()["id"]

    import_response = client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "format": "manual",
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "I want to cancel my subscription"},
                    "expected": {"label": "cancellation"},
                    "metadata": {"source": "manual"},
                },
                {
                    "case_key": "intent-002",
                    "input": {"text": "Please upgrade my plan"},
                    "expected": {"label": "upgrade"},
                },
            ],
        },
    )

    assert import_response.status_code == 201

    imported = import_response.json()
    assert imported["dataset_id"] == dataset_id
    assert imported["imported_count"] == 2
    assert imported["cases"][0]["case_key"] == "intent-001"
    assert imported["cases"][0]["input"] == {
        "text": "I want to cancel my subscription"
    }
    assert imported["cases"][0]["expected"] == {"label": "cancellation"}
    assert imported["cases"][0]["metadata"] == {"source": "manual"}
    assert imported["cases"][1]["metadata"] == {}


def test_import_dataset_cases_rejects_duplicate_case_keys(
    client, clean_db_tables
) -> None:
    create_response = client.post(
        "/datasets",
        json={"name": "Duplicate check dataset", "task_type": "classification"},
    )
    dataset_id = create_response.json()["id"]

    import_response = client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "cancel"},
                    "expected": {"label": "cancellation"},
                },
                {
                    "case_key": "intent-001",
                    "input": {"text": "upgrade"},
                    "expected": {"label": "upgrade"},
                },
            ]
        },
    )

    assert import_response.status_code == 409
    assert import_response.json()["detail"]["message"] == (
        "Duplicate case_key values in import payload"
    )


def test_list_dataset_cases(client, clean_db_tables) -> None:
    create_response = client.post(
        "/datasets",
        json={"name": "Case listing dataset", "task_type": "classification"},
    )
    dataset_id = create_response.json()["id"]

    client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "cancel"},
                    "expected": {"label": "cancellation"},
                },
                {
                    "case_key": "intent-002",
                    "input": {"text": "upgrade"},
                    "expected": {"label": "upgrade"},
                },
            ]
        },
    )

    list_response = client.get(f"/datasets/{dataset_id}/cases?limit=1&offset=1")

    assert list_response.status_code == 200
    cases = list_response.json()
    assert len(cases) == 1
    assert cases[0]["case_key"] == "intent-002"
