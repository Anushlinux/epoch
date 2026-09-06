"""Observable HTTP foundation behavior; no executor or external service required."""

import os
from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend.app import create_app
from epoch_backend.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for key in tuple(os.environ):
        if key.startswith("EPOCH_"):
            monkeypatch.delenv(key)
    return Settings(data_dir=tmp_path / "data", _env_file=None)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as http:
        yield http


def request_body(**overrides):
    return {
        "client_request_id": str(uuid4()),
        "message": "Summarize this week's project updates.",
        **overrides,
    }


def assert_error(response, status):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert isinstance(error["code"], str) and error["code"]
    assert isinstance(error["message"], str) and error["message"]
    assert isinstance(error["details"], list)
    return error


def test_health_identifies_foundation_without_claiming_execution(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "phase": 1,
        "storage": "ok",
        "execution_enabled": False,
    }


def test_corrupt_storage_reports_unavailable_without_exposing_contents_or_paths(client, settings):
    existing = client.post("/api/tasks", json=request_body()).json()
    secret = "private-database-contents"
    settings.database_path.write_bytes(secret.encode())
    responses = [
        client.get("/api/health"),
        client.get("/api/tasks"),
        client.get(f"/api/tasks/{existing['id']}"),
        client.post("/api/tasks", json=request_body()),
    ]
    for response in responses:
        assert_error(response, 503)
        assert secret not in response.text
        assert str(settings.data_dir) not in response.text
        assert "Traceback" not in response.text


def test_app_factory_does_not_initialize_storage(settings):
    create_app(settings)
    assert not settings.data_dir.exists()


def test_create_get_and_restart_preserve_original_pending_task(settings):
    payload = request_body(message="  Prepare the project update.  ")
    with TestClient(create_app(settings)) as first:
        response = first.post("/api/tasks", json=payload)
        assert response.status_code == 201, response.text
        task = response.json()
        assert task["schema_version"] == 1
        assert task["status"] == "pending"
        assert task["request"] == {
            **payload,
            "message": "Prepare the project update.",
            "project_id": "demo",
        }
        for field in ("created_at", "updated_at"):
            assert datetime.fromisoformat(task[field].replace("Z", "+00:00")).tzinfo
        assert first.get(f"/api/tasks/{task['id']}").json() == task

    with TestClient(create_app(settings)) as restarted:
        restored = restarted.get(f"/api/tasks/{task['id']}")
        assert restored.status_code == 200
        assert restored.json() == task
        assert restarted.get("/api/tasks").json()["total"] == 1


def test_normalized_retry_is_idempotent_and_preserves_timestamps(client):
    payload = request_body(message="  Prepare update  ", project_id=" demo ")
    original = client.post("/api/tasks", json=payload)
    assert original.status_code == 201
    retry = client.post(
        "/api/tasks", json={**payload, "message": "Prepare update", "project_id": "demo"}
    )
    assert retry.status_code == 200, retry.text
    assert retry.json() == original.json()
    assert client.get("/api/tasks").json()["total"] == 1


@pytest.mark.parametrize("changed", [{"message": "A different task"}, {"project_id": "other"}])
def test_conflicting_request_id_does_not_overwrite_task(client, changed):
    payload = request_body()
    original = client.post("/api/tasks", json=payload).json()
    assert_error(client.post("/api/tasks", json={**payload, **changed}), 409)
    assert client.get(f"/api/tasks/{original['id']}").json() == original
    assert client.get("/api/tasks").json()["total"] == 1


def test_listing_has_bounded_newest_first_pagination(client):
    tasks = [client.post("/api/tasks", json=request_body()).json() for _ in range(3)]
    page = client.get("/api/tasks", params={"limit": 2, "offset": 1})
    assert page.status_code == 200
    assert page.json() == {
        "items": [tasks[1], tasks[0]],
        "total": 3,
        "limit": 2,
        "offset": 1,
    }
    assert client.get("/api/tasks?offset=99").json()["items"] == []


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=wrong"])
def test_invalid_pagination_uses_error_envelope(client, query):
    assert_error(client.get(f"/api/tasks?{query}"), 422)


def test_unknown_task_and_malformed_task_id_are_distinct(client):
    assert_error(client.get(f"/api/tasks/{uuid4()}"), 404)
    assert_error(client.get("/api/tasks/not-a-uuid"), 422)


@pytest.mark.parametrize(
    "overrides",
    [
        {"message": " \n\t "},
        {"message": "x" * 16001},
        {"project_id": " "},
        {"project_id": "x" * 101},
        {"client_request_id": "not-a-uuid"},
        {"unexpected": "field"},
    ],
)
def test_invalid_task_is_rejected_without_persisting(client, overrides):
    assert_error(client.post("/api/tasks", json=request_body(**overrides)), 422)
    assert client.get("/api/tasks").json()["total"] == 0


def test_validation_does_not_echo_submitted_secrets(client):
    secret = "private-request-token-should-never-appear-in-errors"
    response = client.post(
        "/api/tasks", json=request_body(message=secret, client_request_id=secret)
    )
    assert_error(response, 422)
    assert secret not in response.text
    assert "input" not in response.json()["error"]["details"][0]


def test_malformed_json_uses_safe_error_envelope(client):
    secret = "private-request-token-should-never-appear-in-errors"
    response = client.post(
        "/api/tasks",
        content='{"message": "' + secret,
        headers={"Content-Type": "application/json"},
    )
    assert_error(response, 422)
    assert secret not in response.text


def test_frontend_origin_has_cors_permission(client):
    origin = "http://localhost:5173"
    preflight = client.options(
        "/api/tasks",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    created = client.post("/api/tasks", json=request_body(), headers={"Origin": origin})
    assert created.status_code == 201
    assert created.headers["access-control-allow-origin"] == origin


def test_untrusted_browser_origin_cannot_create_task(client):
    response = client.post(
        "/api/tasks", json=request_body(), headers={"Origin": "https://untrusted.example"}
    )
    assert_error(response, 403)
    assert "access-control-allow-origin" not in response.headers
    assert client.get("/api/tasks").json()["total"] == 0


def test_openapi_describes_intake_contract_and_error_responses(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    create = schema["paths"]["/api/tasks"]["post"]
    assert {"200", "201", "409", "422"} <= create["responses"].keys()
    request_schema = schema["components"]["schemas"]["TaskCreate"]
    assert {"client_request_id", "message"} <= set(request_schema["required"])
    assert request_schema["additionalProperties"] is False
