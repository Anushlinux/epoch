"""Adapter lifecycle/security checks using an explicitly fake executor, never inference."""

import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from epoch_backend import hermes_bridge as bridge


def test_missing_installation_is_reported(monkeypatch):
    monkeypatch.setattr(bridge, "_installation_paths", lambda: None)
    assert bridge.detect_installation()["available"] is False
    result = bridge.execute({}, lambda _: None, threading.Event())
    assert result["error"]["code"] == "hermes_unavailable"


def test_precancelled_does_not_probe_installation(monkeypatch):
    def unexpected():
        pytest.fail("A cancelled execution must not start Hermes")

    monkeypatch.setattr(bridge, "detect_installation", unexpected)
    cancelled = threading.Event()
    cancelled.set()
    assert bridge.execute({}, lambda _: None, cancelled)["error"]["code"] == "cancelled"


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@example.com/v1",
        "https://example.com/v1?api_key=secret",
        "https://example.com/v1#secret",
    ],
)
def test_provider_metadata_rejects_urls_with_credentials(url):
    with pytest.raises(ValueError):
        bridge._safe_url(url)


def test_inspection_does_not_import_agent_or_emit_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bridge, "_installation_paths", lambda: (tmp_path, tmp_path, Path(sys.executable))
    )
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "model": "configured-model",
                    "provider": "openai-codex",
                    "base_url": "https://example.com",
                }
            ),
        )

    monkeypatch.setattr(bridge.subprocess, "run", run)
    result = bridge.detect_installation()
    assert result["available"] is True
    assert calls[0][-2:] == ["--inspect", str(tmp_path)]
    assert "token" not in json.dumps(result)


@pytest.fixture
def fake_installation(tmp_path, monkeypatch):
    installed = {
        "available": True,
        "python": sys.executable,
        "home": str(tmp_path / "source-home"),
        "checkout": str(tmp_path / "checkout"),
        "model": "test-model",
        "provider": "openai-codex",
        "base_url": "https://chatgpt.com/backend-api/codex",
    }
    monkeypatch.setattr(bridge, "detect_installation", lambda: installed)
    return installed


def _request(tmp_path):
    return {
        "task_id": "test-task",
        "run_id": "test-run",
        "brief": "Execute a simulated release",
        "work_dir": str(tmp_path / "work"),
        "mcp_command": sys.executable,
        "mcp_args": ["-m", "epoch_backend.mcp_server"],
        "timeout_seconds": 10,
        "max_turns": 4,
    }


def test_process_protocol_ignores_unstructured_output_and_filters_environment(
    tmp_path,
    monkeypatch,
    fake_installation,
):
    real_popen = subprocess.Popen
    monkeypatch.setenv("UNRELATED_API_KEY", "secret-never-in-child")
    observed = {}
    result = {"success": True, "final_response": "Done", "baseline": {}, "missing_evidence": []}
    items = [
        {"kind": "event", "data": {"type": "executor.step", "data": {"step": 1}}},
        {"kind": "result", "data": result},
    ]
    script = "print('unstructured output deliberately discarded')\n" + "\n".join(
        f"print({(bridge._PREFIX + json.dumps(item))!r}, flush=True)" for item in items
    )

    def launch(command, **kwargs):
        observed.update(kwargs)
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(bridge.subprocess, "Popen", launch)
    events = []
    assert bridge.execute(_request(tmp_path), events.append, threading.Event()) == result
    assert events == [items[0]["data"]]
    assert "UNRELATED_API_KEY" not in observed["env"]
    assert observed["env"]["HERMES_HOME"] == "hermes-home"
    assert observed["cwd"] == tmp_path / "work"
    assert observed["env"]["TERMINAL_CWD"] == str(Path(bridge.__file__).resolve().parents[2])
    assert "secret-never-in-child" not in (tmp_path / "work" / "executor-request.json").read_text()


@pytest.mark.parametrize(
    "field,value",
    [("max_turns", 31), ("max_turns", True), ("timeout_seconds", 601), ("timeout_seconds", 0)],
)
def test_rejects_unbounded_limits(tmp_path, fake_installation, field, value):
    request = _request(tmp_path)
    request[field] = value
    assert (
        bridge.execute(request, lambda _: None, threading.Event())["error"]["code"]
        == "invalid_limits"
    )


def test_refuses_reused_memory_directory(tmp_path, fake_installation):
    request = _request(tmp_path)
    (Path(request["work_dir"]) / "hermes-home").mkdir(parents=True)
    result = bridge.execute(request, lambda _: None, threading.Event())
    assert result["error"]["code"] == "used_workspace"


def test_wall_clock_limit_terminates_child(tmp_path, monkeypatch, fake_installation):
    real_popen = subprocess.Popen
    processes = []

    def launch(command, **kwargs):
        if command[0] == "taskkill":
            return real_popen(command, **kwargs)
        process = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(bridge.subprocess, "Popen", launch)
    request = {**_request(tmp_path), "timeout_seconds": 1}
    start = time.monotonic()
    result = bridge.execute(request, lambda _: None, threading.Event())
    assert result["error"]["code"] == "timeout"
    assert time.monotonic() - start < 15
    assert processes[0].poll() is not None


@pytest.mark.parametrize(
    "unexpected_tool,probe_only", [(False, False), (True, False), (True, True)]
)
def test_worker_scopes_tools_preserves_settings_and_redacts_token(
    tmp_path,
    monkeypatch,
    capsys,
    fake_installation,
    unexpected_tool,
    probe_only,
):
    source = Path(fake_installation["home"])
    source.mkdir()
    original_config = json.dumps(
        {
            "model": {
                "default": "test-model",
                "provider": "openai-codex",
                "base_url": "https://chatgpt.com/backend-api/codex",
            },
            "agent": {"reasoning_effort": "medium", "service_tier": "auto"},
        }
    )
    (source / "config.yaml").write_text(original_config)
    original_auth = json.dumps(
        {
            "providers": {
                "openai-codex": {
                    "tokens": {
                        "access_token": "PRIVATE-TEST-TOKEN",
                        "refresh_token": "PRIVATE-REFRESH",
                    },
                }
            }
        }
    )
    (source / "auth.json").write_text(original_auth)
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    observed = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            observed.update(kwargs)
            name = "terminal" if unexpected_tool else "mcp_epoch_discover_tools"
            self.tools = [{"function": {"name": name}}]
            self._cached_system_prompt = "Fixed test-only prompt"
            self._cached_system_prompt_static = "Fixed test-only prompt"

        def run_conversation(self, brief, task_id):
            observed["ran"] = True
            observed["step_callback"](1, None)
            observed["tool_start_callback"]("call-1", "mcp_epoch_discover_tools", {})
            observed["tool_complete_callback"](
                "call-1", "mcp_epoch_discover_tools", {}, {"ok": True}
            )
            return {
                "completed": True,
                "final_response": "PRIVATE-TEST-TOKEN must be hidden",
                "api_calls": 1,
            }

        def close(self):
            observed["closed"] = True

        def _build_system_prompt(self):
            return self._cached_system_prompt

    monkeypatch.setitem(sys.modules, "yaml", SimpleNamespace(safe_load=json.loads))
    monkeypatch.setitem(sys.modules, "run_agent", SimpleNamespace(AIAgent=FakeAgent))
    monkeypatch.setitem(
        sys.modules,
        "tools.mcp_tool_discovery",
        SimpleNamespace(
            discover_mcp_tools=lambda **_: ["mcp_epoch_discover_tools"],
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "tools.mcp_tool_lifecycle",
        SimpleNamespace(
            shutdown_mcp_servers=lambda: None,
        ),
    )
    monkeypatch.setattr(
        bridge,
        "_source_baseline",
        lambda _: {
            "implementation_commit": "test-only",
            "implementation_sha256": "unchanged",
        },
    )
    monkeypatch.setattr(logging, "disable", lambda _: None)
    monkeypatch.setattr(sys, "path", sys.path[:])
    request = {
        **_request(tmp_path),
        "installation": fake_installation,
        "isolated_home": str(isolated),
        "probe_only": probe_only,
    }
    if probe_only:
        monkeypatch.setattr(bridge, "_read_token", lambda *_: pytest.fail("Probe read credentials"))
    code = bridge._worker(request)
    output = capsys.readouterr().out
    assert "PRIVATE-TEST-TOKEN" not in output
    assert "PRIVATE-REFRESH" not in output
    assert (source / "config.yaml").read_text() == original_config
    assert (source / "auth.json").read_text() == original_auth
    assert "PRIVATE" not in (isolated / "config.yaml").read_text()
    isolated_config = json.loads((isolated / "config.yaml").read_text())
    assert isolated_config["tools"]["tool_search"]["enabled"] == "off"
    assert isolated_config["agent"]["coding_context"] == "off"
    assert isolated_config["mcp_servers"]["epoch"]["tools"] == {
        "include": ["discover_tools", "describe_tool", "invoke_tool"],
        "resources": False,
        "prompts": False,
    }
    assert not (isolated / "auth.json").exists()
    assert observed["enabled_toolsets"] == ["mcp-epoch"]
    assert observed["skip_memory"] is observed["skip_context_files"] is True
    assert observed["skip_background_review"] is True
    assert observed["reasoning_config"] == {"enabled": True, "effort": "medium"}
    assert observed["closed"] is True
    if probe_only:
        assert code == 0
        assert "ran" not in observed
        assert "inference was not invoked" in output
    elif unexpected_tool:
        assert code == 1
        assert "ran" not in observed
        assert "beyond the Epoch MCP grant" in output
    else:
        assert code == 0, output
        assert '"user_settings_unchanged": true' in output
        assert '"system_prompt_unchanged": true' in output
        assert "executor.tool_completed" in output
