"""One warm Hermes process per local workspace, never shared between conversations."""

import hashlib
import hmac
import json
import os
import threading
import time
from pathlib import Path

from epoch_backend import hermes_bridge


def visible_history(chat):
    return [{"role": m.role, "content": m.content} for m in chat.messages if m.agent != "debugger"]


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class ConversationWorker:
    def __init__(self, settings):
        self.settings = settings
        self.timeout = getattr(settings, "chat_worker_idle_seconds", 300)
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.session = None
        self.identity = self.history = self.operation_id = None
        self.used_at = 0.0
        self.credential_salt = os.urandom(32)

    def initialize(self):
        self.thread = threading.Thread(target=self._reap, name="epoch-chat-worker-idle", daemon=True)
        self.thread.start()

    def _identity(self, chat, sandbox, request):
        paths = hermes_bridge._installation_paths()
        if paths is None:
            raise ValueError("Hermes installation unavailable")
        home, checkout, python = paths
        implementation = hermes_bridge._source_baseline(checkout)
        backend_sources = hashlib.sha256()
        for path in sorted(Path(__file__).parent.rglob("*.py")):
            backend_sources.update(str(path.relative_to(Path(__file__).parent)).encode())
            backend_sources.update(path.read_bytes())
        # Never persist or expose credential values or their reusable fingerprints.
        process_credentials = hmac.new(self.credential_salt, json.dumps({
            key: os.environ.get(key, "") for key in (
                "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
            )
        }, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        meta = {key: value for key, value in sandbox.metadata().items() if key != "operation_id"}
        runtime = self.settings.data_dir / "pdf" / "runtime.json"
        return _digest({
            "workspace": str(self.settings.data_dir.resolve()),
            "chat": str(chat.id), "project": chat.project_id, "environment": chat.environment,
            "sandbox": str(sandbox.path.resolve()), "authorization_and_versions": meta,
            "mcp_command": request["mcp_command"], "mcp_args": request["mcp_args"],
            "message_grant": {key: request.get(key) for key in ("max_turns", "timeout_seconds")},
            "installation": [str(home), str(checkout), str(python)],
            "implementation": implementation, "backend_sources": backend_sources.hexdigest(),
            "settings": hermes_bridge._settings_identity(home), "credentials": process_credentials,
            "pdf_image": self.settings.pdf_image_id,
            "pdf_runtime": hashlib.sha256(runtime.read_bytes()).hexdigest()
            if chat.environment == "pdf_workshop" and runtime.is_file() else None,
        })

    def _discard(self):
        session = self.session
        # Retain the reference if termination fails so another message cannot borrow it.
        if session is not None:
            session.close()
            if session.process is not None and session.process.poll() is None:
                raise RuntimeError("The previous Hermes worker has not stopped")
        self.session = self.identity = self.history = None

    def execute(self, chat, operation, sandbox, request, on_event, cancel):
        with self.lock:
            if self.stop.is_set() or self.operation_id is not None:
                raise RuntimeError("Conversation worker unavailable")
            # Claim cleanup responsibility before reading any identity evidence.
            # A failed read must discard the old process, even before a new run starts.
            self.operation_id = str(operation.id)
        on_event({"type": "executor.checking_session", "data": {}})
        if cancel.is_set():
            raise ValueError("Message cancelled before worker admission")
        identity = self._identity(chat, sandbox, request)
        history = _digest(request.get("visible_history", []))
        with self.lock:
            reusable = (
                self.timeout > 0 and self.session is not None and not self.session.closed
                and self.session.process is not None and self.session.process.poll() is None
                and self.identity == identity and self.history == history
                and time.monotonic() - self.used_at < self.timeout
            )
            if not reusable:
                self._discard()
                self.session = hermes_bridge.Session(request, on_event, cancel)
            self.identity = identity
            session = self.session
        operation.worker_reused = reusable
        on_event({"type": "executor.worker_reused" if reusable else "executor.worker_created",
                  "data": {"reused": reusable}})
        if reusable:
            on_event({"type": "executor.session_ready", "data": {
                key: session.baseline.get(key) for key in ("model", "provider")
            }})
        result = session.run_chat_message(request, on_event, cancel)
        # An environment/credential change during work is uncertain, never a reason to replay.
        try:
            if not cancel.is_set():
                on_event({"type": "executor.verifying", "data": {}})
            unchanged = cancel.is_set() or self._identity(chat, sandbox, request) == identity
        except Exception:
            unchanged = False
        if not unchanged:
            result = {**result, "success": False, "error": {
                "code": "worker_scope_changed",
                "message": "The executor or authorized environment changed during this message. "
                           "The worker will be discarded; completed tool effects may remain.",
            }}
        return result

    def finish(self, operation, result, chat, *, persisted):
        result = result or {}
        with self.lock:
            if self.operation_id != str(operation.id):
                return
            try:
                baseline = (result or {}).get("baseline", {})
                intact = all(baseline.get(key) is True for key in (
                    "implementation_unchanged", "user_settings_unchanged",
                    "system_prompt_unchanged", "system_prompt_static_unchanged", "discovery_unchanged",
                ))
                if (not persisted or operation.status != "completed" or not intact
                        or not result.get("history_retained") or result.get("missing_evidence")
                        or self.stop.is_set() or not self.timeout
                        or self.session.cancel_event.is_set()):
                    self._discard()
                else:
                    self.history = _digest(visible_history(chat))
                    self.used_at = time.monotonic()
            finally:
                self.operation_id = None

    def _reap(self):
        while not self.stop.wait(1):
            with self.lock:
                if (self.session is not None and self.operation_id is None
                        and time.monotonic() - self.used_at >= self.timeout):
                    try:
                        self._discard()
                    except Exception:
                        # Preserve the unusable slot and retry termination; never reuse it.
                        self.history = None

    def close(self):
        self.stop.set()
        with self.lock:
            self._discard()
        if self.thread is not None:
            self.thread.join(timeout=2)
