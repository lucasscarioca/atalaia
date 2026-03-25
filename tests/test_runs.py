import httpx


def test_create_run_executes_and_stores_results(
    client, clean_db_tables, monkeypatch
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
                    "input": {"text": "cancel my account"},
                    "expected": {"label": "cancellation"},
                },
                {
                    "case_key": "intent-002",
                    "input": {"text": "upgrade my plan"},
                    "expected": {"label": "upgrade"},
                },
            ]
        },
    )

    target_response = client.post(
        "/targets",
        json={
            "name": "Run target",
            "base_url": "https://target.example.com",
            "endpoint_path": "/classify",
        },
    )
    target_id = target_response.json()["id"]

    def fake_post(url, json, headers, timeout):
        request = httpx.Request("POST", url)
        label = "cancellation" if "cancel" in json["input"]["text"] else "upgrade"
        return httpx.Response(200, json={"label": label}, request=request)

    monkeypatch.setattr("app.target_client.http.httpx.post", fake_post)

    run_response = client.post(
        "/runs",
        json={"dataset_id": dataset_id, "target_id": target_id},
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "completed"
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


def test_create_run_records_failed_and_error_results(
    client, clean_db_tables, monkeypatch
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
                    "input": {"text": "cancel"},
                    "expected": {"label": "cancellation"},
                },
                {
                    "case_key": "intent-002",
                    "input": {"text": "billing"},
                    "expected": {"label": "billing"},
                },
            ]
        },
    )
    target_response = client.post(
        "/targets",
        json={
            "name": "Mixed result target",
            "base_url": "https://target.example.com",
            "endpoint_path": "/classify",
        },
    )
    target_id = target_response.json()["id"]

    def fake_post(url, json, headers, timeout):
        request = httpx.Request("POST", url)
        text = json["input"]["text"]
        if text == "cancel":
            return httpx.Response(200, json={"label": "wrong-label"}, request=request)
        return httpx.Response(200, json={"oops": True}, request=request)

    monkeypatch.setattr("app.target_client.http.httpx.post", fake_post)

    run_response = client.post(
        "/runs",
        json={"dataset_id": dataset_id, "target_id": target_id},
    )

    assert run_response.status_code == 201
    run = run_response.json()
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
