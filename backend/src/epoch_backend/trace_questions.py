"""Durable explicit local questions, isolated from execution and repair services."""

import asyncio
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime

from epoch_backend.trace_ollama import PROMPT_VERSION, ModelAnswerError, OllamaError, answer_question
from epoch_backend.trace_retrieval import build_snapshot, encoded
from epoch_backend.trace_store import TraceError


def now():
    return datetime.now(UTC).isoformat()


class TraceQuestions:
    def __init__(self, settings, traces):
        self.settings, self.traces = settings, traces
        self.path = traces.path
        self.ready = False
        self.warning = None
        self.task = None
        self.active_id = None
        self.closing = False
        self.external_busy = lambda: False

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        try:
            with closing(self._connect()) as db, db:
                db.execute("""CREATE TABLE IF NOT EXISTS trace_questions (
                    id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    state TEXT NOT NULL, record_json TEXT NOT NULL)""")
                db.execute("CREATE INDEX IF NOT EXISTS trace_question_history "
                           "ON trace_questions(trace_id,created_at DESC,id)")
                rows = db.execute("SELECT record_json FROM trace_questions WHERE state='running'").fetchall()
                for row in rows:
                    record = json.loads(row[0])
                    record.update(state="failed", completed_at=now(), error={
                        "code": "interrupted", "message": "The server stopped before this answer completed. Submit a new question to try again."})
                    db.execute("UPDATE trace_questions SET state='failed',record_json=? WHERE id=?",
                               (encoded(record), record["id"]))
            self.ready = True
        except (sqlite3.Error, OSError, ValueError):
            self.warning = "Question storage is unavailable; trace collection and browsing remain separate."

    def runtime_info(self):
        return {"available": self.ready and not self.closing, "provider": "ollama",
                "model": self.settings.trace_model, "base_url": self.settings.ollama_base_url,
                "connection_status": "checked_on_question", "active_question_id": self.active_id,
                "timeout_seconds": self.settings.trace_question_timeout_seconds,
                "model_busy": self.external_busy() or self.active_id is not None,
                "warnings": [self.warning] if self.warning else []}

    def _require_ready(self):
        if not self.ready or self.closing:
            raise TraceError("questions_unavailable", self.warning or "Question service is unavailable.", 503)

    def get(self, trace_id, question_id):
        self._require_ready()
        self.traces._ids(trace_id)
        with closing(self._connect()) as db:
            row = db.execute("SELECT record_json FROM trace_questions WHERE trace_id=? AND id=?",
                             (trace_id, question_id)).fetchone()
        if row is None:
            raise TraceError("question_not_found", "Question not found for this trace.", 404)
        return json.loads(row[0])

    def list(self, trace_id, limit=5, offset=0):
        self._require_ready()
        self.traces._ids(trace_id)
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            total = db.execute("SELECT count(*) FROM trace_questions WHERE trace_id=?", (trace_id,)).fetchone()[0]
            rows = db.execute("SELECT record_json FROM trace_questions WHERE trace_id=? "
                              "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?", (trace_id, limit, offset)).fetchall()
        return {"items": [json.loads(row[0]) for row in rows], "total": total, "limit": limit, "offset": offset}

    def submit(self, trace_id, payload):
        # Called on the application's event loop: no await separates reservation and scheduling.
        self._require_ready()
        self.traces._ids(trace_id, payload.span_id)
        question_id = str(payload.client_request_id)
        with closing(self._connect()) as db:
            existing = db.execute("SELECT record_json FROM trace_questions WHERE id=?", (question_id,)).fetchone()
        if existing:
            record = json.loads(existing[0])
            if (record["trace_id"], record["question"], record["span_id"]) != (trace_id, payload.question, payload.span_id):
                raise TraceError("question_conflict", "This request ID already belongs to a different question.", 409)
            return record, False
        if self.external_busy() or (self.task is not None and not self.task.done()):
            raise TraceError("model_busy", "A local trace question is already running. Wait for it to finish before asking another.", 409)
        snapshot = build_snapshot(self.traces, trace_id, payload.question, payload.span_id)
        if not snapshot["evidence"]:
            raise TraceError("no_question_evidence", "No usable spans fit the evidence snapshot. Inspect the indexing warnings.", 422)
        record = {"id": question_id, "trace_id": trace_id, "question": payload.question,
                  "span_id": payload.span_id, "state": "running", "created_at": now(),
                  "completed_at": None, "model": self.settings.trace_model,
                  "ollama_base_url": self.settings.ollama_base_url, "snapshot": snapshot,
                  "answer": None, "error": None, "usage": None, "prompt_version": PROMPT_VERSION}
        with closing(self._connect()) as db, db:
            db.execute("INSERT INTO trace_questions VALUES(?,?,?,?,?)",
                       (question_id, trace_id, record["created_at"], "running", encoded(record)))
        self.active_id = question_id
        self.task = asyncio.create_task(self._answer(record))
        return record, True

    async def _answer(self, record):
        try:
            answer, usage = await answer_question(self.settings, record["question"], record["snapshot"])
            record.update(state="answered", answer=answer, usage=usage)
        except asyncio.CancelledError:
            record.update(state="failed", error={"code": "interrupted",
                "message": "The server stopped before this answer completed. Submit a new question to try again."})
        except TraceError as exc:
            record.update(state="failed", error={"code": exc.code, "message": exc.message})
            if isinstance(exc, (OllamaError, ModelAnswerError)):
                record["error"]["details"] = exc.details
        except Exception:
            record.update(state="failed", error={"code": "question_failed",
                "message": "The local question could not be completed. Original trace evidence is unchanged."})
        finally:
            record["completed_at"] = now()
            try:
                with closing(self._connect()) as db, db:
                    db.execute("UPDATE trace_questions SET state=?,record_json=? WHERE id=?",
                               (record["state"], encoded(record), record["id"]))
            except (sqlite3.Error, OSError):
                self.warning = "The last answer could not be saved. Restart the server to mark its question interrupted."
            self.active_id = None

    async def close(self):
        self.closing = True
        if self.task is not None and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
