"""Transport unit/lifecycle checks; fake responses are not live model evidence."""

import io
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from epoch_backend import debugger_bridge as bridge

SCHEMA = {
    "type": "object",
    "properties": {"decision": {"type": "string"}},
    "required": ["decision"],
    "additionalProperties": False,
}


def request(**updates):
    return {
        "instructions": "Return a decision.",
        "input": {"task": "Local test"},
        "schema": SCHEMA,
        "timeout_seconds": 5,
        **updates,
    }


def route(provider="openai"):
    return {
        "available": True,
        "model": bridge.MODEL,
        "provider": provider,
        "endpoint": bridge.API_ENDPOINT if provider == "openai" else bridge.CODEX_ENDPOINT,
        "output_token_limit_supported": provider == "openai",
        "python": sys.executable,
    }


def response(**updates):
    return {
        "status": "completed",
        "model": bridge.MODEL,
        "output": [
            {"type": "reasoning", "summary": [{"text": "private reasoning never retained"}]},
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": '{"decision":"continue"}'},
                ],
            },
        ],
        "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
        **updates,
    }


def test_pre_cancelled_never_reads_configuration(monkeypatch):
    monkeypatch.setattr(bridge, "_detect_debugger", lambda _: pytest.fail("must not inspect"))
    cancelled = threading.Event()
    cancelled.set()
    result = bridge.complete(request(), lambda _: None, cancelled)
    assert result["error"]["code"] == "cancelled"


@pytest.mark.parametrize("limit", [True, 0, 601, "600", 1.5])
def test_invalid_limits_cannot_start_network(limit, monkeypatch):
    monkeypatch.setattr(bridge, "_detect_debugger", lambda _: pytest.fail("must not inspect"))
    result = bridge.complete(request(timeout_seconds=limit), lambda _: None, threading.Event())
    assert result["error"]["code"] == "invalid_request"


def test_external_schema_reference_is_rejected_without_network():
    schema = {**SCHEMA, "properties": {"decision": {"$ref": "https://example.com/schema"}}}
    result = bridge.complete(request(schema=schema), lambda _: None, threading.Event())
    assert result["error"]["code"] == "invalid_request"


def test_api_key_route_has_priority_and_no_credentials_returned(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-this-must-never-be-printed")
    detected = bridge.detect_debugger()
    assert detected["provider"] == "openai"
    assert detected["endpoint"] == bridge.API_ENDPOINT
    assert detected["connectivity_verified"] is False
    assert "sk-test" not in json.dumps(detected)


def test_existing_codex_inspection_does_not_make_model_request(monkeypatch, tmp_path):
    from epoch_backend import hermes_bridge

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        hermes_bridge,
        "_installation_paths",
        lambda: (
            tmp_path,
            tmp_path,
            Path(sys.executable),
        ),
    )
    calls = []

    def inspect(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"available":true}')

    monkeypatch.setattr(bridge.subprocess, "run", inspect)
    detected = bridge.detect_debugger()
    assert detected["provider"] == "openai-codex"
    assert detected["model"] == "gpt-5.6-luna"
    assert calls[0][0][-2:] == ["--inspect", str(tmp_path)]
    assert detected["output_token_limit_supported"] is False


def test_missing_route_is_explicit(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "_detect_debugger",
        lambda _: {
            "available": False,
            "error": "No selected credential",
        },
    )
    result = bridge.complete(request(), lambda _: None, threading.Event())
    assert result["error"]["code"] == "debugger_unavailable"


def test_inspection_resource_failure_reports_unavailable(monkeypatch, tmp_path):
    from epoch_backend import hermes_bridge

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        hermes_bridge,
        "_installation_paths",
        lambda: (
            tmp_path,
            tmp_path,
            Path(sys.executable),
        ),
    )

    def cannot_start_reader(*args, **kwargs):
        raise RuntimeError("cannot start a new thread")

    monkeypatch.setattr(bridge.subprocess, "run", cannot_start_reader)
    assert bridge.detect_debugger()["available"] is False


def test_request_is_exact_model_no_tools_no_storage_and_codex_token_limit_disclosed():
    body = bridge._wire_body(request(max_output_tokens=1024, model="different"), route())
    assert body["model"] == "gpt-5.6-luna"
    assert "tools" not in body and body["store"] is False
    assert body["max_output_tokens"] == 1024
    assert body["text"]["format"]["strict"] is True
    assert "max_output_tokens" not in bridge._wire_body(request(), route("openai-codex"))


def test_private_reasoning_is_ignored_and_usage_retained():
    result = bridge._result_from_response(response(), route(), {})
    assert result["output"] == {"decision": "continue"}
    assert result["usage"]["total_tokens"] == 25
    assert "private reasoning" not in json.dumps(result)


@pytest.mark.parametrize(
    "change,code",
    [
        ({"model": "gpt-6-astra"}, "model_mismatch"),
        ({"status": "incomplete"}, "incomplete_response"),
        ({"output": [{"type": "function_call", "name": "terminal"}]}, "unexpected_output"),
        (
            {
                "output": [
                    {"type": "message", "role": "assistant", "content": [{"type": "refusal"}]}
                ]
            },
            "refused",
        ),
        ({"output": []}, "invalid_output"),
    ],
)
def test_incomplete_refused_or_wrong_model_cannot_succeed(change, code):
    result = bridge._result_from_response(response(**change), route(), {})
    assert result["error"]["code"] == code
    assert result["success"] is False


def test_sse_ignores_private_events_and_requires_completion():
    events = [
        b'data: {"type":"response.reasoning.delta","delta":"private"}\n\n',
        b"data: " + json.dumps({"type": "response.completed", "response": response()}).encode(),
    ]
    assert bridge._consume_sse(events)["status"] == "completed"
    with pytest.raises(ValueError, match="without a completed"):
        bridge._consume_sse(events[:1])


def test_redaction_handles_secret_keys_known_values_and_embedded_tokens():
    cleaned = bridge._clean(
        {
            "authorization": "secret",
            "access_token": "secret",
            "nested": ["Bearer secret", "before known-secret after", "sk-abcdefghijklmno"],
        },
        ("known-secret",),
    )
    encoded = json.dumps(cleaned)
    assert "known-secret" not in encoded
    assert "abcdefghijklmno" not in encoded
    assert cleaned["authorization"] == "[redacted]"


def test_codex_completed_empty_array_reassembles_completed_public_messages():
    message = response()["output"][1]
    events = [
        {
            "type": "response.output_item.done",
            "output_index": 0,
            "item": {"type": "reasoning", "content": "private never retained"},
        },
        {"type": "response.output_item.done", "output_index": 1, "item": message},
        {"type": "response.completed", "response": response(output=[])},
    ]
    parsed = bridge._consume_sse([b"data: " + json.dumps(event).encode() for event in events])
    assert parsed["output"] == [message]
    assert bridge._result_from_response(parsed, route(), {})["success"] is True
    assert "private never retained" not in json.dumps(parsed)


def fake_worker(monkeypatch, output):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key-value")
    monkeypatch.setattr(bridge, "_detect_debugger", lambda _: route())
    real_popen = subprocess.Popen
    calls = []

    def spawn(command, **kwargs):
        if "--worker" not in command:
            return real_popen(command, **kwargs)
        calls.append((command, kwargs))
        script = (
            "import json,sys; json.load(sys.stdin); "
            f"print({bridge._PREFIX + json.dumps(output)!r},flush=True)"
        )
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(bridge.subprocess, "Popen", spawn)
    return calls


def test_subprocess_output_validated_and_only_one_request(monkeypatch):
    fake_result = bridge._result_from_response(response(), route(), {})
    calls = fake_worker(monkeypatch, fake_result)
    events = []
    result = bridge.complete(request(), events.append, threading.Event())
    assert result["success"] is True
    assert len(calls) == 1
    assert [event["type"] for event in events] == ["debugger.started", "debugger.completed"]
    assert "OPENAI_BASE_URL" not in calls[0][1]["env"]
    assert "secret-key-value" not in json.dumps(result)


def test_invalid_llm_json_cannot_pass_trusted_schema(monkeypatch):
    result = bridge._result_from_response(response(), route(), {})
    result["output"] = {"decision": "continue", "disable_checks": True}
    fake_worker(monkeypatch, result)
    observed = bridge.complete(request(), lambda _: None, threading.Event())
    assert observed["error"]["code"] == "invalid_output"


@pytest.mark.parametrize("cancel", [False, True])
def test_parent_kills_slow_network_worker_on_limit(monkeypatch, cancel):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(bridge, "_detect_debugger", lambda _: route())
    real_popen = subprocess.Popen
    processes = []

    def spawn(command, **kwargs):
        if "--worker" not in command:
            return real_popen(command, **kwargs)
        process = real_popen(
            [
                sys.executable,
                "-c",
                "import json,sys,time; json.load(sys.stdin); time.sleep(20)",
            ],
            **kwargs,
        )
        processes.append(process)
        return process

    monkeypatch.setattr(bridge.subprocess, "Popen", spawn)
    cancelled = threading.Event()
    timer = threading.Timer(0.2, cancelled.set) if cancel else None
    if timer:
        timer.start()
    started = time.monotonic()
    result = bridge.complete(request(timeout_seconds=1), lambda _: None, cancelled)
    assert result["error"]["code"] == ("cancelled" if cancel else "timeout")
    assert time.monotonic() - started < 5
    assert processes[0].poll() is not None


@pytest.mark.parametrize(
    "body", [b"secret-value", b'{"error":{"message":"Unsupported secret-value"}}']
)
def test_worker_http_error_never_retries_or_returns_error_body(monkeypatch, body):
    import urllib.error
    import urllib.request

    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    calls = []

    def open_error(*args, **kwargs):
        calls.append((args, kwargs))
        raise urllib.error.HTTPError(bridge.API_ENDPOINT, 403, "secret-value", {}, io.BytesIO(body))

    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *args: SimpleNamespace(open=open_error)
    )
    result = bridge._worker(
        {"route": route(), "request": request(max_output_tokens=512), "baseline": {}}
    )
    assert len(calls) == 1
    assert result["error"]["code"] == "openai_http_error"
    assert "secret-value" not in json.dumps(result)


def test_worker_uses_fixed_endpoint_ignoring_supplied_override(monkeypatch):
    import urllib.request

    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    seen = []
    event = {"type": "response.completed", "response": response()}

    class Stream(io.BytesIO):
        pass

    def open_ok(wire, **kwargs):
        seen.append(wire)
        return Stream(b"data: " + json.dumps(event).encode() + b"\n\n")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: SimpleNamespace(open=open_ok))
    result = bridge._worker(
        {
            "route": {**route(), "endpoint": "https://evil.example"},
            "request": request(max_output_tokens=512),
            "baseline": {},
        }
    )
    assert result["success"] is True
    assert seen[0].full_url == bridge.API_ENDPOINT
