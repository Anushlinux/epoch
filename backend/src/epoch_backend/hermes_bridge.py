"""Bounded adapter for an existing Hermes checkout; no model calls during imports.

The child entry point intentionally uses only the standard library until it enters
the user's existing Hermes Python environment. Tokens never cross its stdout pipe.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_PREFIX = "EPOCH_BRIDGE:"
_SAFE_ENV = {
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
    "LOCALAPPDATA",
    "APPDATA",
    "LANG",
    "LC_ALL",
}
_SECRET_KEYS = {"api_key", "access_token", "refresh_token", "id_token", "authorization"}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _safe_url(value: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(value)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Provider endpoint must not contain credentials or query parameters")
    return urlunsplit(parts)


def _installation_paths() -> tuple[Path, Path, Path] | None:
    candidates = []
    if os.environ.get("EPOCH_HERMES_HOME"):
        candidates.append(Path(os.environ["EPOCH_HERMES_HOME"]))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "hermes")
    candidates.append(Path.home() / ".hermes")
    command = shutil.which("hermes")
    if command:
        candidates.append(Path(command).resolve().parent.parent)
    for home in candidates:
        checkout = Path(os.environ.get("EPOCH_HERMES_CHECKOUT", home / "hermes-agent"))
        for name in ("venv", ".venv"):
            python = checkout / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if python.is_file() and (checkout / "run_agent.py").is_file():
                return home.resolve(), checkout.resolve(), python.resolve()
    return None


def _process_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def detect_installation() -> dict[str, Any]:
    """Read installation/config metadata only; availability does not prove connectivity."""
    paths = _installation_paths()
    if paths is None:
        return {
            "available": False,
            "error": "Hermes checkout/Python not found; see HERMES_SETUP.md",
        }
    home, checkout, python = paths
    try:
        output = subprocess.run(
            [str(python), str(Path(__file__).resolve()), "--inspect", str(home)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            **_process_options(),
        )
        metadata = json.loads(output.stdout)
        if output.returncode:
            raise ValueError("Hermes model configuration is unavailable")
        return {
            "available": bool(metadata.get("model") and metadata.get("provider")),
            "home": str(home),
            "checkout": str(checkout),
            "python": str(python),
            **metadata,
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"available": False, "error": "Cannot read Hermes model configuration safely"}


def _terminate(process: subprocess.Popen[str]) -> None:
    """Terminate the worker and its MCP child, not unrelated Hermes sessions."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
            **_process_options(),
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=3)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _failure(code: str, message: str, baseline: dict | None = None) -> dict:
    return {
        "success": False,
        "final_response": "",
        "baseline": baseline or {},
        "missing_evidence": ["Executor did not produce a complete result"],
        "error": {"code": code, "message": message},
    }


def probe_tools(
    mcp_command: str,
    mcp_args: list[str],
    work_dir: str,
    timeout_seconds: int = 45,
) -> dict:
    """Discover the installed tool surface with a placeholder token and no inference."""
    return execute(
        {
            "task_id": "epoch-discovery-probe",
            "run_id": "epoch-discovery-probe",
            "brief": "",
            "mcp_command": mcp_command,
            "mcp_args": mcp_args,
            "work_dir": work_dir,
            "timeout_seconds": timeout_seconds,
            "max_turns": 1,
            "probe_only": True,
        },
        lambda _: None,
        threading.Event(),
    )


def execute(
    request: dict[str, Any],
    on_event: Callable[[dict], None],
    cancel_event: threading.Event,
) -> dict[str, Any]:
    """Run one pre-authored brief, streaming observable events and bounding wall time.

    ``success`` describes executor completion only. Independent state evaluation is
    the caller's responsibility. Callers must supply trusted process arguments.
    """
    if cancel_event.is_set():
        return _failure("cancelled", "Execution cancelled before startup")
    installation = detect_installation()
    if not installation.get("available"):
        return _failure("hermes_unavailable", str(installation.get("error", "Hermes unconfigured")))
    timeout = request.get("timeout_seconds", 180)
    turns = request.get("max_turns", 12)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 600:
        return _failure("invalid_limits", "timeout_seconds must be an integer from 1 to 600")
    if isinstance(turns, bool) or not isinstance(turns, int) or not 1 <= turns <= 30:
        return _failure("invalid_limits", "max_turns must be an integer from 1 to 30")
    work = Path(request["work_dir"]).resolve()
    work.mkdir(parents=True, exist_ok=True)
    isolated_home = work / "hermes-home"
    if isolated_home.exists():
        return _failure("used_workspace", "Use a fresh run directory to prevent memory reuse")
    isolated_home.mkdir()
    payload = {
        **request,
        "timeout_seconds": timeout,
        "max_turns": turns,
        "installation": installation,
        "isolated_home": str(isolated_home),
    }
    request_path = work / "executor-request.json"
    request_path.write_text(json.dumps(payload), encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if key.upper() in _SAFE_ENV}
    environment.update(
        {
            # Hermes preserves relative home paths. The OS cwd remains this run's
            # work directory, so storage is fresh while profile wording is stable.
            "HERMES_HOME": "hermes-home",
            "TERMINAL_CWD": str(Path(__file__).resolve().parents[2]),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HERMES_ENABLE_PROJECT_PLUGINS": "0",
            "HERMES_INTERACTIVE": "0",
            "HERMES_TELEMETRY_ENABLED": "false",
        }
    )
    process = subprocess.Popen(
        [installation["python"], str(Path(__file__).resolve()), "--worker", str(request_path)],
        cwd=work,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        **_process_options(),
    )
    output: queue.Queue[str | None] = queue.Queue()

    def read_output() -> None:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                if line.startswith(_PREFIX):
                    output.put(line[len(_PREFIX) :])
        finally:
            output.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    baseline: dict = {}
    result = None
    try:
        while True:
            if cancel_event.is_set():
                return _failure(
                    "cancelled", "Execution cancelled; inspect state before retry", baseline
                )
            if time.monotonic() >= deadline:
                return _failure(
                    "timeout", "Executor time limit reached; inspect state before retry", baseline
                )
            try:
                line = output.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("kind") == "result":
                result = item["data"]
            elif item.get("kind") == "event":
                event = item["data"]
                if event.get("type") == "executor.baseline":
                    baseline = event["data"]
                on_event(event)
        return result or _failure("executor_failed", "Hermes exited without a result", baseline)
    finally:
        _terminate(process)
        if process.stdout:
            process.stdout.close()
        reader.join(timeout=1)


def _read_model(home: Path) -> tuple[dict, dict]:
    import yaml  # Supplied by the existing Hermes environment, never Epoch's parent process.

    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8")) or {}
    model = config.get("model", {})
    if not isinstance(model, dict):
        raise ValueError("Hermes model/provider must be explicitly configured")
    metadata = {
        "model": model.get("default", ""),
        "provider": model.get("provider", ""),
        "base_url": _safe_url(model.get("base_url", "") or ""),
    }
    if not all(isinstance(value, str) for value in metadata.values()):
        raise ValueError("Unsupported Hermes model configuration")
    return model, metadata


def _read_token(home: Path, provider: str, model: dict) -> str:
    """Read only the selected route's existing credential; never refresh or copy it."""
    if provider == "openai-codex":
        auth = json.loads((home / "auth.json").read_text(encoding="utf-8"))
        return auth.get("providers", {}).get(provider, {}).get("tokens", {}).get("access_token", "")
    env_name = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "custom": "OPENAI_API_KEY",
    }.get(provider)
    if env_name is None:
        raise ValueError("Configured provider is not yet supported by the isolated bridge")
    if model.get("api_key"):
        return str(model["api_key"])
    from dotenv import dotenv_values

    return str(dotenv_values(home / ".env").get(env_name) or os.environ.get(env_name) or "")


def _source_baseline(checkout: Path) -> dict:
    command = {"capture_output": True, "check": True, "timeout": 15}
    commit = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
        **command,
    ).stdout.strip()
    paths = (
        subprocess.run(
            ["git", "-C", str(checkout), "ls-files", "-z", "*.py"],
            **command,
        )
        .stdout.decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted(filter(None, paths)):
        digest.update(name.encode())
        digest.update((checkout / name).read_bytes())
    return {"implementation_commit": commit, "implementation_sha256": digest.hexdigest()}


def _settings_identity(home: Path) -> dict:
    return {
        name: hashlib.sha256((home / name).read_bytes()).hexdigest()
        for name in ("config.yaml", "auth.json", ".env", "SOUL.md")
        if (home / name).is_file()
    }


def _worker(request: dict) -> int:
    """Existing-Hermes-interpreter entry point. No credentials are written to disk."""
    import logging

    write_lock = threading.Lock()
    secrets: list[str] = []

    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: "[redacted]" if k.lower() in _SECRET_KEYS else clean(v) for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value]
        if isinstance(value, str):
            for secret in secrets:
                value = value.replace(secret, "[redacted]")
        return value

    def emit(kind: str, data: dict) -> None:
        with write_lock:
            print(
                _PREFIX + json.dumps({"kind": kind, "data": clean(data)}, default=str), flush=True
            )

    def event(event_type: str, **data: Any) -> None:
        emit("event", {"type": event_type, "data": data})

    agent = None
    baseline: dict = {}
    observed_prompt_hashes: set[str] = set()

    def on_step(step: int, _: Any) -> None:
        prompt = getattr(agent, "_cached_system_prompt", None)
        if prompt is not None:
            fingerprint = _digest(prompt)
            observed_prompt_hashes.add(fingerprint)
            if "system_prompt_initial_sha256" not in baseline:
                baseline["system_prompt_initial_sha256"] = fingerprint
                event("executor.baseline", **baseline)
        event("executor.step", step=step)

    try:
        installation = request["installation"]
        source_home = Path(installation["home"])
        checkout = Path(installation["checkout"])
        isolated_home = Path(request["isolated_home"])
        settings_before = _settings_identity(source_home)
        model_config, metadata = _read_model(source_home)
        import yaml

        source_config = yaml.safe_load((source_home / "config.yaml").read_text())
        agent_config = source_config.get("agent", {})
        inference_options = {
            key: agent_config[key]
            for key in ("reasoning_effort", "service_tier")
            if key in agent_config
        }
        if any(metadata[key] != installation[key] for key in ("model", "provider", "base_url")):
            raise ValueError("Hermes route changed after run admission")
        probe_only = request.get("probe_only") is True
        token = (
            "epoch-discovery-probe-no-inference"
            if probe_only
            else _read_token(source_home, metadata["provider"], model_config)
        )
        if not token:
            raise ValueError("Selected Hermes route has no existing access credential")
        secrets.append(token)
        minimal_model = {
            key: model_config[key]
            for key in (
                "default",
                "provider",
                "base_url",
                "api_mode",
                "reasoning_effort",
                "reasoning",
                "max_tokens",
                "temperature",
            )
            if key in model_config
        }
        mcp_config = {
            "epoch": {
                "command": request["mcp_command"],
                "args": request["mcp_args"],
                "env": {
                    "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                "timeout": 30,
                "connect_timeout": 20,
                "tools": {
                    "include": ["discover_tools", "describe_tool", "invoke_tool"],
                    "resources": False,
                    "prompts": False,
                },
            }
        }
        config = {
            "model": minimal_model,
            "mcp_servers": mcp_config,
            "memory": {"memory_enabled": False, "user_profile_enabled": False},
            "plugins": {"enabled": []},
            "tools": {"tool_search": {"enabled": "off"}},
            "platform_toolsets": {"cli": ["mcp-epoch"]},
            "agent": {
                "max_turns": request["max_turns"],
                "coding_context": "off",
                **inference_options,
            },
            "telemetry": {"enabled": False},
            "updates": {"auto_update": False},
            "compression": {"enabled": False},
        }
        # JSON is a YAML subset, avoiding a second serializer and never including a token.
        (isolated_home / "config.yaml").write_text(json.dumps(config), encoding="utf-8")
        for name in ("skills", "memories", "plugins", "hooks"):
            (isolated_home / name).mkdir()
        sys.path.insert(0, str(checkout))
        logging.disable(logging.CRITICAL)
        from run_agent import AIAgent
        from tools.mcp_tool_discovery import discover_mcp_tools

        names = discover_mcp_tools(allowed_mcp_names=["epoch"])
        if not names:
            raise ValueError("Hermes could not discover Epoch MCP tools")
        event("executor.started", provider=metadata["provider"], model=metadata["model"])
        agent = AIAgent(
            model=metadata["model"],
            provider=metadata["provider"],
            requested_provider=metadata["provider"],
            api_key=token,
            base_url=metadata["base_url"] or None,
            api_mode=(
                "codex_responses"
                if metadata["provider"] == "openai-codex"
                else model_config.get("api_mode")
            ),
            enabled_toolsets=["mcp-epoch"],
            max_iterations=request["max_turns"],
            run_budget_seconds=request["timeout_seconds"],
            session_id=request["run_id"],
            platform="cli",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            skip_background_review=True,
            load_soul_identity=False,
            save_trajectories=False,
            fallback_model=None,
            credential_pool=None,
            reasoning_config=(
                {"enabled": True, "effort": inference_options["reasoning_effort"]}
                if inference_options.get("reasoning_effort")
                else None
            ),
            service_tier=inference_options.get("service_tier"),
            tool_start_callback=lambda call_id, name, arguments: event(
                "executor.tool_started", tool_call_id=call_id, name=name, arguments=arguments
            ),
            tool_complete_callback=lambda call_id, name, arguments, result: event(
                "executor.tool_completed",
                tool_call_id=call_id,
                name=name,
                arguments=arguments,
                result=result,
            ),
            interim_assistant_callback=lambda content, **_: event(
                "executor.message", content=content
            ),
            step_callback=on_step,
            clarify_callback=lambda *_, **__: "No clarification available; report missing input.",
        )
        definitions = getattr(agent, "tools", [])
        tool_names = [
            tool.get("function", {}).get("name", tool.get("name", "")) for tool in definitions
        ]
        if probe_only:
            probe_prompt = agent._build_system_prompt()
            prompt_path = isolated_home / "probe-system-prompt.txt"
            prompt_path.write_text(probe_prompt, encoding="utf-8")
            emit(
                "result",
                {
                    "success": bool(tool_names) and all(name in names for name in tool_names),
                    "final_response": "Discovery only; inference was not invoked",
                    "baseline": {
                        "tool_names": tool_names,
                        "discovered_names": names,
                        "system_prompt_sha256": _digest(probe_prompt),
                        "system_prompt_path": str(prompt_path),
                    },
                    "missing_evidence": [],
                },
            )
            return 0
        if not tool_names or any(name not in names for name in tool_names):
            raise ValueError(
                "Hermes exposed tools beyond the Epoch MCP grant: "
                + json.dumps({"exposed": tool_names, "discovered": names})
            )
        baseline = {
            **_source_baseline(checkout),
            **metadata,
            "model_configuration_sha256": _digest([minimal_model, inference_options]),
            "inference_options": inference_options,
            "user_settings_sha256": settings_before,
            "discovery_sha256": _digest(definitions),
            "tool_names": tool_names,
            "memory_state": "fresh_empty_home_memory_disabled",
            "logical_workspace": str(Path(__file__).resolve().parents[2]),
            "home_display": "hermes-home (relative to isolated run directory)",
            "coding_context": "off",
            "context_files": "disabled",
            "background_review": "disabled",
            "brief_sha256": hashlib.sha256(request["brief"].encode()).hexdigest(),
            "bridge_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        event("executor.baseline", **baseline)
        result = agent.run_conversation(request["brief"], task_id=request["task_id"])
        prompt = getattr(agent, "_cached_system_prompt", None)
        baseline["system_prompt_sha256"] = _digest(prompt) if prompt is not None else None
        baseline["system_prompt_unchanged"] = bool(observed_prompt_hashes) and (
            observed_prompt_hashes == {baseline["system_prompt_sha256"]}
        )
        static_prompt = getattr(agent, "_cached_system_prompt_static", None)
        baseline["system_prompt_static_sha256"] = (
            _digest(static_prompt) if static_prompt is not None else None
        )
        baseline["implementation_unchanged"] = (
            _source_baseline(checkout)["implementation_sha256"] == baseline["implementation_sha256"]
        )
        baseline["user_settings_unchanged"] = _settings_identity(source_home) == settings_before
        missing = (
            [] if prompt is not None else ["Hermes did not expose the effective system prompt"]
        )
        if not observed_prompt_hashes:
            missing.append("No pre-inference step callback captured the initial system prompt")
        final = str(result.get("final_response") or "")
        success = bool(result.get("completed", False)) and not result.get("failed")
        if not baseline["implementation_unchanged"]:
            success = False
            missing.append("Hermes implementation changed during the run")
        if not baseline["user_settings_unchanged"]:
            success = False
            missing.append("User Hermes settings changed concurrently during the run")
        if observed_prompt_hashes and not baseline["system_prompt_unchanged"]:
            success = False
            missing.append("Effective system prompt changed during the run")
        event("executor.baseline", **baseline)
        if final:
            event("executor.message", content=final, final=True)
        outcome = {
            "success": success,
            "final_response": final,
            "baseline": baseline,
            "missing_evidence": missing,
            "api_calls": result.get("api_calls"),
        }
        if not success:
            outcome["error"] = {
                "code": "executor_incomplete",
                "message": "Hermes did not complete its conversation",
            }
        emit("result", outcome)
        return 0
    except Exception as exc:
        # Known configuration failures are ours; external exceptions may contain secrets.
        message = (
            str(exc) if type(exc) is ValueError else f"Hermes bridge failed ({type(exc).__name__})"
        )
        event("executor.error", code="bridge_error", message=message)
        emit("result", _failure("bridge_error", message, baseline))
        return 1
    finally:
        if agent is not None:
            try:
                agent.close()
            except Exception:
                pass
        try:
            from tools.mcp_tool_lifecycle import shutdown_mcp_servers

            shutdown_mcp_servers()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--inspect":
        try:
            print(json.dumps(_read_model(Path(sys.argv[2]))[1]))
        except Exception:
            print(json.dumps({"error": "Hermes model configuration unavailable"}))
            raise SystemExit(1) from None
    elif len(sys.argv) == 3 and sys.argv[1] == "--worker":
        raise SystemExit(_worker(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))))
    else:
        raise SystemExit("Internal Hermes bridge entry point")
