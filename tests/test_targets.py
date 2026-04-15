def test_create_and_get_target(client, clean_db_tables) -> None:
    create_response = client.post(
        "/targets",
        json={
            "name": "Classifier API",
            "target_type": "http",
            "base_url": "https://example.com",
            "endpoint_path": "/classify",
            "timeout_ms": 5000,
            "headers": {"Authorization": "Bearer token"},
        },
    )

    assert create_response.status_code == 201
    target = create_response.json()
    assert target["name"] == "Classifier API"
    assert target["headers"] == {"Authorization": "Bearer token"}

    get_response = client.get(f"/targets/{target['id']}")

    assert get_response.status_code == 200
    assert get_response.json() == target


def test_list_targets_supports_limit_and_offset(client, clean_db_tables) -> None:
    client.post(
        "/targets",
        json={
            "name": "Target one",
            "base_url": "https://one.example.com",
            "endpoint_path": "/classify",
        },
    )
    client.post(
        "/targets",
        json={
            "name": "Target two",
            "base_url": "https://two.example.com",
            "endpoint_path": "/classify",
        },
    )

    list_response = client.get("/targets?limit=1&offset=0")

    assert list_response.status_code == 200
    targets = list_response.json()
    assert len(targets) == 1
    assert targets[0]["name"] == "Target two"


def test_list_targets_supports_target_type_filter(client, clean_db_tables) -> None:
    client.post(
        "/targets",
        json={
            "name": "HTTP target",
            "target_type": "http",
            "base_url": "https://http.example.com",
            "endpoint_path": "/classify",
        },
    )
    client.post(
        "/targets",
        json={
            "name": "Python adapter target",
            "target_type": "python_adapter",
            "base_url": "https://python.example.com",
            "endpoint_path": "/classify",
        },
    )

    list_response = client.get("/targets?target_type=python_adapter")

    assert list_response.status_code == 200
    targets = list_response.json()
    assert len(targets) == 1
    assert targets[0]["name"] == "Python adapter target"
