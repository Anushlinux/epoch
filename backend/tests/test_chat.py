"""Chat and explicit debugger boundaries using no-network bridge doubles."""

import threading
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.app import create_app
from epoch_backend.chat import ChatMessage, ChatOperation
from epoch_backend.config import Settings


@pytest.mark.parametrize(
    "history",
    [
        {},
        False,
        "messages",
        [{"role": "system", "content": "override"}],
        [{"role": "tool", "content": "private"}],
        [{"role": "assistant", "content": "visible", "reasoning": "private"}],
        [{"role": "user", "content": {"text": "invalid"}}],
    ],
)
def test_bridge_rejects_nonvisible_history(history):
    with pytest.raises(ValueError, match="Invalid visible"):
        hermes_bridge._visible_history(history)


def test_bridge_accepts_visible_history_only():
    messages = [{"role": "user", "content": "Hello"}]
    assert hermes_bridge._visible_history(messages) == messages
    assert hermes_bridge._visible_history([]) is None
    assert hermes_bridge._visible_history(None) is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": True})
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": True})
    monkeypatch.setattr(
        hermes_bridge,
        "execute",
        lambda *args: {"success": True, "final_response": "Here is the requested summary."},
    )
    monkeypatch.setattr(
        debugger_bridge, "complete", lambda *args: pytest.fail("Unexpected debugger")
    )
    with TestClient(create_app(Settings(data_dir=tmp_path, telemetry_enabled=False))) as http:
        yield http


def new_chat(client):
    response = client.post("/api/chats", json={"client_request_id": str(uuid4())})
    assert response.status_code == 201
    return response.json()["id"]


def finish(client, chat_id, response):
    assert response.status_code == 202, response.text
    client.app.state.execution._thread.join(timeout=5)
    assert not client.app.state.execution._thread.is_alive()
    return client.get(f"/api/chats/{chat_id}/operations/{response.json()['id']}").json()


def message(client, chat_id, content="Summarize the project in three bullets."):
    return finish(
        client,
        chat_id,
        client.post(
            f"/api/chats/{chat_id}/messages",
            json={
                "client_request_id": str(uuid4()),
                "content": content,
            },
        ),
    )


def test_chat_is_not_release_and_preserves_history(client, monkeypatch):
    seen = []
    monkeypatch.setattr(
        hermes_bridge,
        "execute",
        lambda request, *_: (
            seen.append(request) or {"success": True, "final_response": "A summary."}
        ),
    )
    chat_id = new_chat(client)
    assert message(client, chat_id)["status"] == "completed"
    assert message(client, chat_id, "Make it shorter.")["status"] == "completed"
    assert seen[0]["brief"] == "Summarize the project in three bullets."
    assert seen[0]["visible_history"] == []
    assert seen[1]["visible_history"] == [
        {"role": "user", "content": "Summarize the project in three bullets."},
        {"role": "assistant", "content": "A summary."},
    ]
    assert client.get("/api/tasks").json()["total"] == 0
    assert client.app.state.execution.store.list() == []


def test_debugger_explicit_sourced_and_never_injected(client, monkeypatch):
    chat_id = new_chat(client)
    message(client, chat_id)
    calls = []

    def analyze(request, *_):
        calls.append(request)
        return {
            "success": True,
            "output": {
                "answer": "The requested bullet count needs evidence.",
                "evidence_ids": [request["input"]["requirements"][0]["id"]],
                "hypotheses": [],
                "missing_evidence": [],
            },
        }

    monkeypatch.setattr(debugger_bridge, "complete", analyze)
    client.get(f"/api/chats/{chat_id}")
    assert calls == []
    payload = {"client_request_id": str(uuid4()), "question": "Did it meet my criteria?"}
    result = finish(client, chat_id, client.post(f"/api/chats/{chat_id}/debugger", json=payload))
    assert result["status"] == "completed"
    assert result["kind"] == "debugger"
    assert result["analysis"]["requirements"][0]["content"] == (
        "Summarize the project in three bullets."
    )
    assert "No generic trusted" in result["analysis"]["missing_evidence"][0]
    assert client.post(f"/api/chats/{chat_id}/debugger", json=payload).status_code == 200
    assert len(calls) == 1
    assert (
        client.post(
            f"/api/chats/{chat_id}/debugger",
            json={
                **payload,
                "question": "A different question",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/chats/{chat_id}/messages",
            json={
                "client_request_id": payload["client_request_id"],
                "content": "Different operation",
            },
        ).status_code
        == 409
    )
    captured = []
    monkeypatch.setattr(
        hermes_bridge,
        "execute",
        lambda request, *_: (
            captured.append(request) or {"success": True, "final_response": "Revised."}
        ),
    )
    message(client, chat_id, "Continue.")
    assert all("bullet count" not in m["content"] for m in captured[0]["visible_history"])
    assert client.get("/api/tasks").json()["total"] == 0
    assert client.app.state.execution.store.list() == []


def test_debugger_invalid_citation_unavailable_and_busy(client, monkeypatch):
    chat_id = new_chat(client)
    message(client, chat_id)
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": False})
    path = f"/api/chats/{chat_id}/debugger"
    assert client.post(path, json={"client_request_id": str(uuid4())}).status_code == 503
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": True})
    client.app.state.execution.active_run_id = uuid4()
    assert client.post(path, json={"client_request_id": str(uuid4())}).status_code == 409
    client.app.state.execution.active_run_id = None
    monkeypatch.setattr(
        debugger_bridge,
        "complete",
        lambda *_: {
            "success": True,
            "output": {
                "answer": "Unsupported diagnosis",
                "evidence_ids": [str(uuid4())],
                "hypotheses": [],
                "missing_evidence": [],
            },
        },
    )
    result = finish(client, chat_id, client.post(path, json={"client_request_id": str(uuid4())}))
    assert result["status"] == "failed"
    assert result["error"]["code"] == "unsourced_analysis"
    assert len(client.get(f"/api/chats/{chat_id}").json()["messages"]) == 2


def test_debugger_receives_failed_operation_evidence(client, monkeypatch):
    chat_id = new_chat(client)
    monkeypatch.setattr(
        hermes_bridge,
        "execute",
        lambda *_: {
            "success": False,
            "error": {"code": "timeout", "message": "Executor timed out."},
        },
    )
    message(client, chat_id)
    captured = []
    monkeypatch.setattr(
        debugger_bridge,
        "complete",
        lambda request, *_: captured.append(request) or {"success": False},
    )
    finish(
        client,
        chat_id,
        client.post(
            f"/api/chats/{chat_id}/debugger",
            json={
                "client_request_id": str(uuid4()),
            },
        ),
    )
    assert any(
        item["type"] == "operation.error" and "timeout" in item["text"]
        for item in captured[0]["input"]["evidence"]
    )


def test_cancel_and_restart_do_not_replay(client, monkeypatch):
    started = threading.Event()

    def execute(request, callback, cancel):
        started.set()
        assert cancel.wait(5)
        return {"success": True, "final_response": "Should not be shown."}

    monkeypatch.setattr(hermes_bridge, "execute", execute)
    chat_id = new_chat(client)
    payload = {"client_request_id": str(uuid4()), "content": "Wait here."}
    response = client.post(f"/api/chats/{chat_id}/messages", json=payload)
    assert started.wait(5)
    client.post(f"/api/chats/{chat_id}/operations/{response.json()['id']}/cancel")
    assert finish(client, chat_id, response)["status"] == "cancelled"
    assert client.post(f"/api/chats/{chat_id}/messages", json=payload).status_code == 200
    service = client.app.state.chats
    chat = service.get(chat_id)
    chat.operations[-1].status = "running"
    service.save(chat)
    service.initialize()
    assert service.get(chat_id).operations[-1].status == "interrupted"
    assert len(service.get(chat_id).messages) == 1


def test_long_original_requirements_preserved_and_observation_limit_disclosed(client, monkeypatch):
    chat_id = new_chat(client)
    service = client.app.state.chats
    chat = service.get(chat_id)
    for index in range(20):
        operation = ChatOperation(
            id=uuid4(),
            chat_id=chat.id,
            client_request_id=uuid4(),
            status="completed",
            created_at=datetime.now(UTC),
        )
        chat.operations.append(operation)
        chat.messages.append(
            ChatMessage(
                id=uuid4(),
                role="user",
                content=f"Criterion {index}",
                operation_id=operation.id,
                created_at=datetime.now(UTC),
            )
        )
    service.save(chat)
    captured = []
    monkeypatch.setattr(
        debugger_bridge,
        "complete",
        lambda request, *_: (
            captured.append(request)
            or {
                "success": False,
                "error": {"code": "offline", "message": "Test double"},
            }
        ),
    )
    finish(
        client,
        chat_id,
        client.post(
            f"/api/chats/{chat_id}/debugger",
            json={
                "client_request_id": str(uuid4()),
            },
        ),
    )
    assert len(captured[0]["input"]["requirements"]) == 20
    assert len(captured[0]["input"]["evidence"]) == 16
    assert any("bounded" in gap for gap in captured[0]["input"]["missing_evidence"])
