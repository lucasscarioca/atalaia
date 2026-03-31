import time


def _wait_for_run_status(client, run_id: str, expected_statuses: set[str]) -> dict:
    deadline = time.time() + 5
    while time.time() < deadline:
        run_response = client.get(f"/runs/{run_id}")
        assert run_response.status_code == 200
        run = run_response.json()
        if run["status"] in expected_statuses:
            return run
        time.sleep(0.05)

    raise AssertionError(f"Run did not reach status in time: {expected_statuses}")


def _wait_for_run_completion(client, run_id: str) -> dict:
    return _wait_for_run_status(client, run_id, {"completed", "failed"})


def test_create_run_executes_and_stores_results(
    client, clean_db_tables, local_target_base_url
) -> None:
    dataset_response = client.post(
        "/datasets",
        json={"name": "Run dataset", "task_type": "classification"},
    )
    dataset_id = dataset_response.json()["id"]
    client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "label:cancellation"},
                    "expected": {"label": "cancellation"},
                },
                {
                    "case_key": "intent-002",
                    "input": {"text": "label:upgrade"},
                    "expected": {"label": "upgrade"},
                },
            ]
        },
    )

    target_response = client.post(
        "/targets",
        json={
            "name": "Run target",
            "base_url": local_target_base_url,
            "endpoint_path": "/classify",
        },
    )
    target_id = target_response.json()["id"]

    run_response = client.post(
        "/runs",
        json={"dataset_id": dataset_id, "target_id": target_id},
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "queued"

    run = _wait_for_run_completion(client, run["id"])

    assert run["summary_json"] == {
        "total": 2,
        "passed": 2,
        "failed": 0,
        "error": 0,
        "invalid_case": 0,
    }
    assert run["metrics_json"]["accuracy"] == 1.0

    results_response = client.get(f"/runs/{run['id']}/results")

    assert results_response.status_code == 200
    results = results_response.json()
    assert len(results) == 2
    assert results[0]["status"] == "passed"
    assert results[1]["status"] == "passed"


def test_create_run_exposes_running_state(
    client, clean_db_tables, local_target_base_url
) -> None:
    dataset_response = client.post(
        "/datasets",
        json={"name": "Slow run dataset", "task_type": "classification"},
    )
    dataset_id = dataset_response.json()["id"]
    client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "sleep:0.4:cancellation"},
                    "expected": {"label": "cancellation"},
                }
            ]
        },
    )
    target_response = client.post(
        "/targets",
        json={
            "name": "Slow run target",
            "base_url": local_target_base_url,
            "endpoint_path": "/classify",
        },
    )
    target_id = target_response.json()["id"]

    run_response = client.post(
        "/runs",
        json={"dataset_id": dataset_id, "target_id": target_id},
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "queued"

    running_run = _wait_for_run_status(client, run["id"], {"running", "completed"})
    assert running_run["status"] in {"running", "completed"}

    completed_run = _wait_for_run_completion(client, run["id"])
    assert completed_run["status"] == "completed"
    assert completed_run["summary_json"]["passed"] == 1


def test_create_run_records_failed_and_error_results(
    client, clean_db_tables, local_target_base_url
) -> None:
    dataset_response = client.post(
        "/datasets",
        json={"name": "Mixed result dataset", "task_type": "classification"},
    )
    dataset_id = dataset_response.json()["id"]
    client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "wrong:cancellation"},
                    "expected": {"label": "cancellation"},
                },
                {
                    "case_key": "intent-002",
                    "input": {"text": "malformed"},
                    "expected": {"label": "billing"},
                },
            ]
        },
    )
    target_response = client.post(
        "/targets",
        json={
            "name": "Mixed result target",
            "base_url": local_target_base_url,
            "endpoint_path": "/classify",
        },
    )
    target_id = target_response.json()["id"]

    run_response = client.post(
        "/runs",
        json={"dataset_id": dataset_id, "target_id": target_id},
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "queued"

    run = _wait_for_run_completion(client, run["id"])

    assert run["summary_json"] == {
        "total": 2,
        "passed": 0,
        "failed": 1,
        "error": 1,
        "invalid_case": 0,
    }
    assert run["metrics_json"]["accuracy"] == 0.0

    results_response = client.get(f"/runs/{run['id']}/results?limit=1&offset=1")

    assert results_response.status_code == 200
    results = results_response.json()
    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert results[0]["error_type"] == "invalid_response"


def test_create_run_records_unexpected_background_failure(
    client, clean_db_tables, local_target_base_url, monkeypatch
) -> None:
    dataset_response = client.post(
        "/datasets",
        json={"name": "Crash dataset", "task_type": "classification"},
    )
    dataset_id = dataset_response.json()["id"]
    client.post(
        f"/datasets/{dataset_id}/cases:import",
        json={
            "cases": [
                {
                    "case_key": "intent-001",
                    "input": {"text": "label:cancellation"},
                    "expected": {"label": "cancellation"},
                }
            ]
        },
    )
    target_response = client.post(
        "/targets",
        json={
            "name": "Crash target",
            "base_url": local_target_base_url,
            "endpoint_path": "/classify",
        },
    )
    target_id = target_response.json()["id"]

    def crash(*args, **kwargs):
        raise RuntimeError("simulated background crash")

    monkeypatch.setattr("app.services.runs._execute_classification_case", crash)

    run_response = client.post(
        "/runs",
        json={"dataset_id": dataset_id, "target_id": target_id},
    )

    assert run_response.status_code == 201
    run = _wait_for_run_completion(client, run_response.json()["id"])

    assert run["status"] == "failed"
    assert run["summary_json"] == {
        "run_error": {
            "type": "RuntimeError",
            "message": "simulated background crash",
        }
    }
    assert run["metrics_json"] == {}

    results_response = client.get(f"/runs/{run['id']}/results")
    assert results_response.status_code == 200
    assert results_response.json() == []
