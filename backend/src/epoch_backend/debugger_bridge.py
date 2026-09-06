"""One bounded OpenAI debugger request; model output never executes tools or code.

The network request lives in a killable standard-library child process. Credentials
are read in that child and are never written into request files or returned events.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

MODEL = "gpt-5.6-luna"
API_ENDPOINT = "https://api.openai.com/v1/responses"
CODEX_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
_PREFIX = "EPOCH_DEBUGGER:"
_MAX_REQUEST_BYTES = 500_000
_MAX_RESPONSE_BYTES = 1_000_000
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
_SECRET_KEYS = {
    "api_key",
    "access_token",
    "refresh_token",
    "id_token",
    "authorization",
    "account_id",
    "chatgpt-account-id",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _clean(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if str(key).lower() in _SECRET_KEYS else _clean(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_clean(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[redacted]")
        value = re.sub(r"\bBearer\s+\S+", "Bearer [redacted]", value, flags=re.IGNORECASE)
        value = re.sub(r"\bsk-[A-Za-z0-9_-]{10,}", "[redacted]", value)
    return value


def _process_options() -> dict:
    return (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )


def _inspect(home: Path) -> dict:
    """Child-only credential inspection; emits presence and route metadata only."""
    import yaml  # Available in the detected Hermes Python environment.

    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8")) or {}
    model = config.get("model", {})
    if not isinstance(model, dict) or model.get("provider") != "openai-codex":
        raise ValueError("Existing Hermes route must be openai-codex")
    endpoint = str(model.get("base_url") or "https://chatgpt.com/backend-api/codex")
    if endpoint.rstrip("/") != CODEX_ENDPOINT.removesuffix("/responses"):
        raise ValueError("Only the official OpenAI Codex endpoint is supported")
    auth = json.loads((home / "auth.json").read_text(encoding="utf-8"))
    present = bool(
        auth.get("providers", {}).get("openai-codex", {}).get("tokens", {}).get("access_token")
    )
    return {"available": present, "credential_present": present}


def _detect_debugger(timeout: float) -> dict:
    metadata = {"model": MODEL, "connectivity_verified": False}
    if os.environ.get("OPENAI_API_KEY", "").strip():
        return {
            **metadata,
            "available": True,
            "provider": "openai",
            "endpoint": API_ENDPOINT,
            "credential_source": "OPENAI_API_KEY",
            "python": sys.executable,
            "output_token_limit_supported": True,
        }
    from epoch_backend.hermes_bridge import _installation_paths

    paths = _installation_paths()
    if paths is None:
        return {
            **metadata,
            "available": False,
            "provider": "openai",
            "endpoint": API_ENDPOINT,
            "error": "Set OPENAI_API_KEY or configure the existing Hermes OpenAI Codex route",
        }
    home, _, python = paths
    route = {
        **metadata,
        "provider": "openai-codex",
        "endpoint": CODEX_ENDPOINT,
        "credential_source": "existing_hermes_access_token",
        "home": str(home),
        "python": str(python),
        "output_token_limit_supported": False,
    }
    try:
        process = subprocess.run(
            [str(python), str(Path(__file__).resolve()), "--inspect", str(home)],
            capture_output=True,
            text=True,
            timeout=max(0.01, min(timeout, 10)),
            check=False,
            **_process_options(),
        )
        inspected = json.loads(process.stdout) if not process.returncode else {}
        if not inspected.get("available"):
            raise ValueError("Credential unavailable")
        return {**route, "available": True}
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return {
            **route,
            "available": False,
            "error": "Existing Hermes OpenAI Codex credential/configuration is unavailable",
        }


def detect_debugger() -> dict:
    """Read configuration only; availability does not claim model/account connectivity."""
    return _detect_debugger(10)


def _failure(code: str, message: str, route: dict | None = None, baseline: dict | None = None):
    route = route or {}
    return {
        "success": False,
        "output": None,
        "model": MODEL,
        "provider": route.get("provider"),
        "usage": {},
        "baseline": baseline or {},
        "missing_evidence": ["Debugger did not return a complete validated decision"],
        "error": {"code": code, "message": message},
    }


def _validate_schema(schema: Any) -> None:
    from jsonschema import Draft202012Validator

    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("schema must describe a JSON object")
    Draft202012Validator.check_schema(schema)

    # Remote schema resolution would create an unapproved second network path.
    def check_refs(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"$ref", "$dynamicRef"} and (
                    not isinstance(item, str) or not item.startswith("#")
                ):
                    raise ValueError("Only local schema references are supported")
                check_refs(item)
        elif isinstance(value, list):
            for item in value:
                check_refs(item)

    check_refs(schema)


def complete(
    request: dict[str, Any],
    on_event: Callable[[dict], None],
    cancel_event: threading.Event,
) -> dict[str, Any]:
    """Perform at most one network request; caller owns the aggregate 20-turn budget.

    Request keys: instructions (str), input (dict), schema (JSON Schema object),
    timeout_seconds (1..600), max_output_tokens (256..16384, default 4096).
    No model, provider, credential or endpoint override can be supplied by the LLM.
    """
    started = time.monotonic()
    if cancel_event.is_set():
        return _failure("cancelled", "Debugger cancelled before startup")
    try:
        timeout = request["timeout_seconds"]
        tokens = request.get("max_output_tokens", 4096)
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError("timeout_seconds must be an integer from 1 to 600")
        if type(tokens) is not int or not 256 <= tokens <= 16384:
            raise ValueError("max_output_tokens must be an integer from 256 to 16384")
        if not isinstance(request.get("instructions"), str) or not request["instructions"].strip():
            raise ValueError("instructions must be a nonempty string")
        if not isinstance(request.get("input"), dict):
            raise ValueError("input must be an object")
        _validate_schema(request.get("schema"))
        selected = {key: request[key] for key in ("instructions", "input", "schema")}
        selected.update(timeout_seconds=timeout, max_output_tokens=tokens)
        # Treat content as data; strip accidental credential fields before transmission.
        selected["instructions"] = _clean(selected["instructions"])
        selected["input"] = _clean(selected["input"])
        if len(json.dumps(selected).encode()) > _MAX_REQUEST_BYTES:
            raise ValueError("Debugger request exceeds the input size limit")
    except Exception:
        return _failure("invalid_request", "Debugger request or limits are invalid")
    deadline = started + timeout
    route = _detect_debugger(deadline - time.monotonic())
    if cancel_event.is_set():
        return _failure("cancelled", "Debugger cancelled during startup", route)
    if not route.get("available"):
        return _failure("debugger_unavailable", route["error"], route)
    if time.monotonic() >= deadline:
        return _failure("timeout", "Debugger wall-time limit reached during startup", route)
    baseline = {
        "model": MODEL,
        "provider": route["provider"],
        "endpoint": route["endpoint"],
        "instructions_sha256": _digest(selected["instructions"]),
        "input_sha256": _digest(selected["input"]),
        "schema_sha256": _digest(selected["schema"]),
        "bridge_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reasoning_effort": "low",
        "tools": [],
        "store": False,
        "automatic_retries": 0,
        "requested_max_output_tokens": tokens,
        "output_token_limit_supported": route["output_token_limit_supported"],
    }
    payload = {"request": selected, "route": route, "baseline": baseline}
    environment = {key: value for key, value in os.environ.items() if key.upper() in _SAFE_ENV}
    environment.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    if route["provider"] == "openai":
        environment["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    from epoch_backend.hermes_bridge import _terminate

    process = None
    reader = None
    try:
        process = subprocess.Popen(
            [route["python"], str(Path(__file__).resolve()), "--worker"],
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            **_process_options(),
        )
        pending: queue.Queue[str | None] = queue.Queue()

        def read_stdout() -> None:
            assert process and process.stdout
            for line in process.stdout:
                pending.put(line)
            pending.put(None)

        reader = threading.Thread(target=read_stdout, daemon=True)
        reader.start()
        assert process.stdin
        process.stdin.write(json.dumps(payload))
        process.stdin.close()
        on_event(
            {"type": "debugger.started", "data": {"model": MODEL, "provider": route["provider"]}}
        )
        result = None
        while True:
            if cancel_event.is_set():
                return _failure("cancelled", "Debugger request cancelled", route, baseline)
            if time.monotonic() >= deadline:
                return _failure("timeout", "Debugger wall-time limit reached", route, baseline)
            try:
                line = pending.get(timeout=min(0.05, max(0.001, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if line is None:
                break
            if line.startswith(_PREFIX):
                result = json.loads(line[len(_PREFIX) :])
        if not isinstance(result, dict):
            return _failure(
                "worker_failed", "Debugger worker exited without a result", route, baseline
            )
        result = _clean(result, (os.environ.get("OPENAI_API_KEY", ""),))
        if result.get("success"):
            from jsonschema import Draft202012Validator

            try:
                Draft202012Validator(selected["schema"]).validate(result["output"])
            except Exception:
                return _failure(
                    "invalid_output",
                    "Debugger output failed the trusted JSON schema",
                    route,
                    baseline,
                )
        on_event(
            {
                "type": "debugger.completed",
                "data": {
                    "success": result.get("success") is True,
                    "model": MODEL,
                    "usage": result.get("usage", {}),
                    "baseline": result.get("baseline", baseline),
                },
            }
        )
        return result
    except Exception:
        return _failure(
            "bridge_error",
            "Debugger transport failed; no automatic retry was made",
            route,
            baseline,
        )
    finally:
        if process:
            _terminate(process)
            if process.stdout:
                process.stdout.close()
        if reader:
            reader.join(timeout=1)


def _wire_body(request: dict, route: dict) -> dict:
    body = {
        "model": MODEL,
        "instructions": request["instructions"],
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(request["input"], sort_keys=True),
                    }
                ],
            }
        ],
        "store": False,
        "stream": True,
        "reasoning": {"effort": "low"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "epoch_debugger_decision",
                "strict": True,
                "schema": request["schema"],
            }
        },
    }
    if route["provider"] == "openai":
        body["max_output_tokens"] = request["max_output_tokens"]
    return body


def _consume_sse(stream: Any) -> dict:
    """Reassemble public completed output items; never retain private reasoning.

    The installed Codex route sends output_item.done messages and an empty output
    array in response.completed. Requiring the latter array alone loses actual
    assistant output. Partial deltas are never used as a completed decision.
    """
    consumed = 0
    completed_items: dict[int, dict] = {}
    for raw in stream:
        consumed += len(raw)
        if consumed > _MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeded byte limit")
        if not raw.startswith(b"data:"):
            continue
        data = raw[5:].strip()
        if data == b"[DONE]":
            continue
        event = json.loads(data)
        if event.get("type") == "response.output_item.done":
            item = event.get("item", {})
            if item.get("type") != "reasoning":
                index = event.get("output_index", len(completed_items))
                completed_items[index] = item
        if event.get("type") == "response.completed":
            response = event["response"]
            if not response.get("output") and completed_items:
                response["output"] = [completed_items[index] for index in sorted(completed_items)]
            return response
        if event.get("type") in {"response.failed", "response.incomplete", "error"}:
            raise ValueError("OpenAI response did not complete")
    raise ValueError("OpenAI stream ended without a completed response")


def _result_from_response(response: dict, route: dict, baseline: dict) -> dict:
    if response.get("status") != "completed":
        return _failure(
            "incomplete_response", "OpenAI did not complete the decision", route, baseline
        )
    actual_model = response.get("model")
    if actual_model != MODEL:
        return _failure(
            "model_mismatch", "OpenAI returned a different model than requested", route, baseline
        )
    texts = []
    for item in response.get("output", []):
        if item.get("type") == "reasoning":
            continue
        if item.get("type") != "message" or item.get("role") != "assistant":
            return _failure(
                "unexpected_output", "Debugger returned a non-message output", route, baseline
            )
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                return _failure("refused", "OpenAI declined the debugger request", route, baseline)
            if content.get("type") == "output_text":
                texts.append(content.get("text", ""))
    try:
        output = json.loads("".join(texts))
        if not isinstance(output, dict):
            raise ValueError("Expected object")
    except (ValueError, TypeError):
        return _failure("invalid_output", "Debugger did not return a JSON object", route, baseline)
    raw_usage = response.get("usage") or {}
    usage = {
        key: raw_usage[key]
        for key in ("input_tokens", "output_tokens", "total_tokens")
        if type(raw_usage.get(key)) is int and raw_usage[key] >= 0
    }
    missing = [] if usage else ["OpenAI response omitted token usage"]
    return {
        "success": True,
        "output": output,
        "model": MODEL,
        "provider": route["provider"],
        "usage": usage,
        "baseline": {**baseline, "response_model": actual_model},
        "missing_evidence": missing,
        "error": None,
    }


def _worker(payload: dict) -> dict:
    import urllib.error
    import urllib.request

    route, request, baseline = payload["route"], payload["request"], payload["baseline"]
    secrets = []
    try:
        if route["provider"] == "openai":
            token = os.environ["OPENAI_API_KEY"]
            endpoint = API_ENDPOINT
            headers = {}
        elif route["provider"] == "openai-codex":
            source_home = Path(route["home"])
            identity_before = hashlib.sha256((source_home / "auth.json").read_bytes()).hexdigest()
            auth = json.loads((source_home / "auth.json").read_text(encoding="utf-8"))
            tokens = auth.get("providers", {}).get("openai-codex", {}).get("tokens", {})
            token = tokens.get("access_token", "")
            endpoint = CODEX_ENDPOINT
            headers = {"originator": "epoch", "User-Agent": "Epoch/0.1"}
            if tokens.get("account_id"):
                headers["ChatGPT-Account-ID"] = tokens["account_id"]
                secrets.append(tokens["account_id"])
        else:
            raise ValueError("Unsupported route")
        if not token:
            return _failure(
                "credential_unavailable",
                "Selected OpenAI credential is unavailable",
                route,
                baseline,
            )
        secrets.append(token)
        headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            }
        )

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, response_headers, newurl):
                raise ValueError("Redirects are not permitted")

        # Explicit endpoint and direct TLS connection. No environment proxy or redirect
        # may route the selected credential to another host.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        wire = urllib.request.Request(
            endpoint,
            data=json.dumps(_wire_body(request, route)).encode(),
            headers=headers,
            method="POST",
        )
        with opener.open(wire, timeout=request["timeout_seconds"]) as response:
            parsed = _consume_sse(response)
        result = _result_from_response(parsed, route, baseline)
        if route["provider"] == "openai-codex":
            result["baseline"]["credential_file_unchanged"] = (
                identity_before
                == hashlib.sha256((source_home / "auth.json").read_bytes()).hexdigest()
            )
        return _clean(result, tuple(secrets))
    except urllib.error.HTTPError as error:
        # Error bodies can include prompts or credentials; retain only the status.
        return _failure(
            "openai_http_error",
            f"OpenAI returned HTTP {error.code}; no retry or model fallback",
            route,
            baseline,
        )
    except Exception:
        return _failure(
            "openai_transport_error",
            "OpenAI request failed or returned incomplete data; no retry was made",
            route,
            baseline,
        )


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--inspect":
        try:
            print(json.dumps(_inspect(Path(sys.argv[2]))))
        except Exception:
            print(json.dumps({"available": False}))
            raise SystemExit(1) from None
    elif len(sys.argv) == 2 and sys.argv[1] == "--worker":
        try:
            data = json.loads(sys.stdin.read(_MAX_REQUEST_BYTES + 20_000))
            print(_PREFIX + json.dumps(_worker(data)), flush=True)
        except Exception:
            print(
                _PREFIX + json.dumps(_failure("worker_error", "Debugger worker failed safely")),
                flush=True,
            )
    else:
        raise SystemExit("Use the Epoch backend debugger adapter")
