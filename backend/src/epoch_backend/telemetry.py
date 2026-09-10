"""Durable, additive OTLP telemetry. This module never controls task execution."""

import gzip
import hashlib
import hmac
import io
import json
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing
from datetime import UTC, datetime

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from epoch_backend.trace_store import TraceStore

MAX_BYTES = 4 * 1024 * 1024
MAX_SPANS = 1000
CLOUD_ENDPOINT = "https://ingest.neatlogs.com/v1/traces"
# Only these bounded structural fields may leave the machine. Span names, messages,
# events, links, arbitrary resource attributes and input/output content are excluded.
FIELDS = (
    "task_id",
    "run_id",
    "revision_id",
    "project_id",
    "workflow",
    "tool",
    "error_code",
    "check_id",
    "environment_version",
    "native_event_id",
    "event_type",
    "status",
)


class TelemetryError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def _text(value):
    return str(value)[:200] if value is not None else ""


def _attributes(items):
    result = {}
    for item in items:
        field = item.value.WhichOneof("value")
        if field in {"string_value", "int_value", "bool_value", "double_value"}:
            result[item.key] = getattr(item.value, field)
    return result


def _structural(attributes):
    result = {}
    for field in FIELDS:
        value = attributes.get("epoch." + field, attributes.get(field))
        if value is not None:
            result[field] = _text(value)
    # Neatlogs' ordinary span metadata is useful for independently instrumented apps.
    for field, key in (
        ("workflow", "neatlogs.workflow_name"),
        ("workflow", "neatlogs.workflow.name"),
        ("tool", "tool.name"),
        ("tool", "mcp.tool.name"),
        ("error_code", "error.type"),
        ("error_code", "exception.type"),
    ):
        if not result.get(field) and attributes.get(key):
            result[field] = _text(attributes[key])
    return result


def _timestamp(nanos):
    try:
        return datetime.fromtimestamp(nanos / 1_000_000_000, UTC).isoformat()
    except (ValueError, OverflowError, OSError) as exc:
        raise TelemetryError(
            "invalid_trace", "Span timestamp is outside the supported range."
        ) from exc


def _safe_value(value, secrets=()):
    # Reject prose, URLs, whitespace and long values in public structural fields.
    text = str(value)
    return bool(re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", text)) and not (
        any(secret and secret in text for secret in secrets)
        or re.search(r"(?i)(sk-|sk_|ghp_|github_pat_|xox[baprs]-|bearer|api.?key|token)", text)
    )


def _cloud_request(span, attributes, secrets=()):
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add()
    resource.resource.attributes.add(key="service.name").value.string_value = "epoch"
    scope = resource.scope_spans.add()
    scope.scope.name = "epoch.structural"
    clean = scope.spans.add()
    clean.trace_id, clean.span_id = span.trace_id, span.span_id
    clean.parent_span_id = span.parent_span_id
    clean.start_time_unix_nano, clean.end_time_unix_nano = (
        span.start_time_unix_nano,
        span.end_time_unix_nano,
    )
    clean.name = "epoch.event" if attributes.get("native_event_id") else "external.span"
    clean.kind = span.kind
    clean.status.code = span.status.code
    clean.attributes.add(key="openinference.span.kind").value.string_value = "CHAIN"
    for key, value in attributes.items():
        if key in FIELDS and _safe_value(value, secrets):
            clean.attributes.add(key="epoch." + key).value.string_value = str(value)
    return request.SerializeToString()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TelemetryService:
    def __init__(self, settings, incidents=None):
        self.settings, self.incidents = settings, incidents
        self.path = settings.data_dir / "telemetry.sqlite3"
        self.traces = TraceStore(self.path)
        self.enabled = getattr(settings, "telemetry_enabled", True)
        self.cloud_enabled = getattr(settings, "neatlogs_cloud_enabled", False)
        self._token = os.environ.get("EPOCH_TELEMETRY_TOKEN", "").strip()
        cloud_key = getattr(settings, "neatlogs_api_key", None)
        self._key = (
            cloud_key.get_secret_value()
            if cloud_key is not None
            else os.environ.get("NEATLOGS_API_KEY", "")
        ).strip()
        self._stop = threading.Event()
        self._thread = None
        self._ready = False
        self._warning = None

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=2)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""CREATE TABLE IF NOT EXISTS spans (
                identity TEXT PRIMARY KEY, native_event_id TEXT,
                record_json TEXT NOT NULL, cloud_payload BLOB NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt REAL NOT NULL DEFAULT 0, error TEXT,
                evidence_ingested INTEGER NOT NULL DEFAULT 0)""")
            connection.execute("CREATE INDEX IF NOT EXISTS span_native ON spans(native_event_id)")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(spans)")}
            if "local_source" not in columns:
                connection.execute("ALTER TABLE spans ADD COLUMN local_source BLOB")
            if "evidence_attempts" not in columns:
                connection.execute(
                    "ALTER TABLE spans ADD COLUMN evidence_attempts INTEGER DEFAULT 0"
                )
            connection.execute("""CREATE TABLE IF NOT EXISTS native_cursors (
                run_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS span_conflicts (
                identity TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                local_source BLOB NOT NULL, received_at TEXT NOT NULL,
                PRIMARY KEY(identity,payload_sha256))""")
            # A process may have died during export; retry the same stable IDs, bounded.
            connection.execute("""UPDATE spans SET status=CASE WHEN attempts>=3 THEN 'failed'
                ELSE 'pending' END, error='delivery_interrupted' WHERE status='sending'""")
            if self.enabled and self.cloud_enabled and self._key:
                connection.execute("UPDATE spans SET status='pending' WHERE status='disabled'")
        try:
            self.traces.initialize()
            self.traces.project_batch()
        except Exception:
            self.traces.warning = "Trace index initialization failed; original collection remains available."
        self._ready = True
        # Index retained evidence even when new collection is disabled.
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=7)

    def authorize(self, token):
        if not self.enabled or not self._ready:
            raise TelemetryError("telemetry_disabled", "The local collector is disabled.", 503)
        if not self._token:
            raise TelemetryError(
                "telemetry_unconfigured", "Set the process EPOCH_TELEMETRY_TOKEN.", 503
            )
        if not hmac.compare_digest(str(token or ""), self._token):
            raise TelemetryError("unauthorized", "Invalid local telemetry token.", 401)

    def ingest(self, body, encoding="identity"):
        if len(body) > MAX_BYTES:
            raise TelemetryError("trace_too_large", "Trace request exceeds 4 MiB.", 413)
        if encoding == "gzip":
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
                    body = stream.read(MAX_BYTES + 1)
            except (OSError, EOFError) as exc:
                raise TelemetryError("invalid_gzip", "Malformed gzip request.") from exc
        elif encoding not in {"", "identity"}:
            raise TelemetryError("unsupported_encoding", "Use identity or gzip encoding.", 415)
        if len(body) > MAX_BYTES:
            raise TelemetryError("trace_too_large", "Decoded trace request exceeds 4 MiB.", 413)
        request = ExportTraceServiceRequest()
        try:
            request.ParseFromString(body)
        except DecodeError as exc:
            raise TelemetryError("invalid_trace", "Malformed OTLP protobuf request.") from exc
        pending = []
        for resource in request.resource_spans:
            resource_attrs = _attributes(resource.resource.attributes)
            for scope in resource.scope_spans:
                for span in scope.spans:
                    if len(pending) >= MAX_SPANS:
                        raise TelemetryError("too_many_spans", "Limit requests to 1000 spans.", 413)
                    if (
                        len(span.trace_id) != 16
                        or len(span.span_id) != 8
                        or len(span.parent_span_id) not in {0, 8}
                        or not any(span.trace_id)
                        or not any(span.span_id)
                        or span.end_time_unix_nano < span.start_time_unix_nano
                    ):
                        raise TelemetryError("invalid_trace", "Invalid span identity or timing.")
                    attributes = _structural({**resource_attrs, **_attributes(span.attributes)})
                    if span.status.code == 2:
                        attributes["status"] = "error"
                        if not attributes.get("error_code"):
                            for event in span.events:
                                exception_type = _attributes(event.attributes).get("exception.type")
                                if exception_type:
                                    attributes["error_code"] = _text(exception_type)
                                    break
                        # ERROR is real failure evidence even without an explicit family.
                        attributes["error_code"] = attributes.get("error_code") or "span_error"
                    trace_id, span_id = span.trace_id.hex(), span.span_id.hex()
                    record = {
                        "source_type": "trace",
                        "source_id": f"{trace_id}:{span_id}",
                        "timestamp": _timestamp(span.start_time_unix_nano),
                        "project_id": attributes.get("project_id", "unassigned"),
                        "text": span.name[:500] or "External telemetry span",
                        "structured_payload": {
                            "status_code": span.status.code,
                            "start_time_unix_nano": str(span.start_time_unix_nano),
                            "end_time_unix_nano": str(span.end_time_unix_nano),
                            "attributes": attributes,
                        },
                        "source_ref": f"/api/telemetry/traces/{trace_id}/spans/{span_id}",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        **attributes,
                    }
                    original = ExportTraceServiceRequest()
                    resource_copy = original.resource_spans.add()
                    resource_copy.resource.CopyFrom(resource.resource)
                    resource_copy.schema_url = resource.schema_url
                    scope_copy = resource_copy.scope_spans.add()
                    scope_copy.scope.CopyFrom(scope.scope)
                    scope_copy.schema_url = scope.schema_url
                    scope_copy.spans.add().CopyFrom(span)
                    pending.append(
                        (
                            record,
                            _cloud_request(span, attributes, (self._key, self._token)),
                            original.SerializeToString(),
                        )
                    )
        # Check the complete batch under the write lock before inserting any new spans.
        conflicts, unique = [], {}
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            for record, payload, original in pending:
                identity = record["source_id"]
                previous = connection.execute(
                    "SELECT local_source,cloud_payload,native_event_id FROM spans WHERE identity=?",
                    (identity,),
                ).fetchone()
                prior = unique.get(identity)
                if prior is None and previous is not None:
                    prior = previous["local_source"] or previous["cloud_payload"]
                if prior is not None and not self._same_source(prior, original):
                    if previous is None:
                        # A collision inside a new batch must retain both versions.
                        conflicts.append((identity, prior))
                    conflicts.append((identity, original))
                else:
                    unique.setdefault(identity, original)
            for identity, original in conflicts:
                connection.execute(
                    "INSERT OR IGNORE INTO span_conflicts VALUES(?,?,?,?)",
                    (identity, hashlib.sha256(original).hexdigest(), original,
                     datetime.now(UTC).isoformat()),
                )
            if not conflicts:
                for record, payload, original in pending:
                    self._insert(connection, record, payload, original=original)
        if conflicts:
            raise TelemetryError(
                "span_conflict", "Span identity was reused with different content. "
                "The batch was rejected; original evidence and conflicting payloads are retained.", 409
            )
        self.traces.project_batch()
        self._deliver_evidence()
        return ExportTraceServiceResponse().SerializeToString()

    @staticmethod
    def _same_source(left, right):
        if left == right:
            return True
        return MessageToDict(ExportTraceServiceRequest.FromString(left)) == MessageToDict(
            ExportTraceServiceRequest.FromString(right)
        )

    def _save(self, record, payload, *, native=False, original=None):
        with closing(self._connect()) as connection, connection:
            self._insert(connection, record, payload, native=native, original=original)

    def _insert(self, connection, record, payload, *, native=False, original=None):
        connection.execute(
            """INSERT OR IGNORE INTO spans
                (identity,native_event_id,record_json,cloud_payload,status,evidence_ingested,
                 local_source) VALUES (?,?,?,?,?,?,?)""",
            (
                record["source_id"], record.get("native_event_id"), json.dumps(record), payload,
                "pending" if self.cloud_enabled and self._key else "disabled",
                int(native), original,
            ),
        )

    def _deliver_evidence(self):
        if self.incidents is None:
            return
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT identity,record_json FROM spans WHERE evidence_ingested=0 LIMIT 1000"
            ).fetchall()
        if not rows:
            return
        # Isolate malformed/oversized normalized records so one rejection cannot
        # prevent unrelated accepted traces from reaching incidents. Raw sources stay local.
        for row in rows:
            try:
                self.incidents.ingest_evidence([json.loads(row["record_json"])])
                with closing(self._connect()) as connection, connection:
                    connection.execute(
                        "UPDATE spans SET evidence_ingested=1 WHERE identity=?", (row["identity"],)
                    )
            except Exception:
                with closing(self._connect()) as connection, connection:
                    connection.execute(
                        """UPDATE spans SET evidence_attempts=evidence_attempts+1,
                        evidence_ingested=CASE WHEN evidence_attempts>=2 THEN -1 ELSE 0 END
                        WHERE identity=?""",
                        (row["identity"],),
                    )

    def project_events(self, record, sandbox):
        if not self.enabled or not self._ready:
            return
        try:
            metadata = sandbox.metadata()
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT sequence FROM native_cursors WHERE run_id=?", (str(record.id),)
                ).fetchone()
            cursor = row[0] if row else 0
            for event in sandbox.events(after=cursor):
                event_id = str(event["id"])
                attributes = {
                    "task_id": str(record.task_id),
                    "run_id": str(record.id),
                    "project_id": str(metadata.get("project_id", "unassigned")),
                    "workflow": "release",
                    "native_event_id": event_id,
                    "event_type": event["type"],
                    "environment_version": _text(getattr(record, "environment_version", "")),
                }
                event_payload = event.get("payload", {})
                for field in ("revision_id", "environment_version", "status"):
                    if event_payload.get(field) is not None:
                        attributes[field] = _text(event_payload[field])
                if event["type"].startswith("executor.tool_"):
                    attributes["tool"] = _text(event_payload.get("name"))
                elif event["type"].startswith("tool."):
                    attributes["tool"] = _text(event_payload.get("tool_name"))
                if isinstance(event_payload.get("error"), dict):
                    attributes["error_code"] = _text(event_payload["error"].get("code"))
                request = ExportTraceServiceRequest()
                span = request.resource_spans.add().scope_spans.add().spans.add()
                span.trace_id = hashlib.sha256(str(record.id).encode()).digest()[:16]
                span.span_id = hashlib.sha256(event_id.encode()).digest()[:8]
                nanos = int(datetime.fromisoformat(event["emitted_at"]).timestamp() * 1e9)
                span.start_time_unix_nano = span.end_time_unix_nano = nanos
                span.kind = 1
                if event["type"] in {"tool.error", "mcp.invalid_call", "executor.error"}:
                    span.status.code = 2
                    attributes["status"] = "error"
                    attributes["error_code"] = _text(
                        event_payload.get("code") or attributes.get("error_code") or "span_error"
                    )
                identity = f"{span.trace_id.hex()}:{span.span_id.hex()}"
                self._save(
                    {
                        "source_id": identity,
                        "native_event_id": event_id,
                        "source_type": "epoch",
                        "timestamp": event["emitted_at"],
                    },
                    _cloud_request(span, attributes, (self._key, self._token)),
                    native=True,
                )
                with closing(self._connect()) as connection, connection:
                    connection.execute(
                        """INSERT INTO native_cursors(run_id,sequence) VALUES (?,?)
                        ON CONFLICT(run_id) DO UPDATE
                        SET sequence=max(sequence,excluded.sequence)""",
                        (str(record.id), event["sequence"]),
                    )
            if self._warning and self._warning.startswith("Native telemetry"):
                self._warning = None
        except Exception:
            self._warning = "Native telemetry projection failed; task execution is unaffected."

    def _worker(self):
        while not self._stop.wait(1):
            try:
                self.traces.project_batch(self._stop)
                if not self.enabled:
                    continue
                self._deliver_evidence()
                if self.cloud_enabled and self._key:
                    self._export_one()
                if self._warning and self._warning.startswith("Telemetry background"):
                    self._warning = None
            except Exception:
                self._warning = "Telemetry background work failed; local records are retained."

    def _export_one(self):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT * FROM spans WHERE status='pending'
                AND attempts<3 AND next_attempt<=? ORDER BY rowid LIMIT 100""",
                (time.time(),),
            ).fetchall()
            if not rows:
                return
            connection.executemany(
                "UPDATE spans SET status='sending', attempts=attempts+1 WHERE identity=?",
                [(row["identity"],) for row in rows],
            )
        error, permanent = None, False
        # Reapply secret filtering after restart: a newly configured key may not
        # have been known when an older local-only payload was queued.
        outgoing = ExportTraceServiceRequest()
        for row in rows:
            stored = ExportTraceServiceRequest.FromString(row["cloud_payload"])
            original = stored.resource_spans[0].scope_spans[0].spans[0]
            cleaned = ExportTraceServiceRequest.FromString(
                _cloud_request(
                    original,
                    _structural(_attributes(original.attributes)),
                    (self._key, self._token),
                )
            )
            outgoing.resource_spans.extend(cleaned.resource_spans)
        request = urllib.request.Request(
            CLOUD_ENDPOINT,
            data=gzip.compress(outgoing.SerializeToString()),
            headers={
                "Content-Type": "application/x-protobuf",
                "Content-Encoding": "gzip",
                "x-api-key": self._key,
            },
            method="POST",
        )
        try:
            with urllib.request.build_opener(_NoRedirect).open(request, timeout=5) as response:
                result = ExportTraceServiceResponse()
                raw = response.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise ValueError("oversized_response")
                result.ParseFromString(raw)
                if result.partial_success.rejected_spans:
                    error, permanent = "cloud_rejected_spans", True
        except urllib.error.HTTPError as exc:
            error = f"cloud_http_{exc.code}"
            permanent = exc.code not in {408, 429, 500, 502, 503, 504}
        except Exception:
            error = "cloud_transport_failed"
        # OTLP partial rejection does not identify rejected span IDs. Preserve the
        # whole batch as failed rather than claiming individual acceptance.
        updates = []
        for row in rows:
            attempts = row["attempts"] + 1
            status = (
                "delivered"
                if error is None
                else ("failed" if permanent or attempts >= 3 else "pending")
            )
            updates.append((status, error, time.time() + 2**attempts, row["identity"]))
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                "UPDATE spans SET status=?, error=?, next_attempt=? WHERE identity=?", updates
            )

    def get_span(self, trace_id, span_id):
        if not re.fullmatch(r"[a-f0-9]{32}", trace_id) or not re.fullmatch(
            r"[a-f0-9]{16}", span_id
        ):
            raise TelemetryError("trace_not_found", "Trace span not found.", 404)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT local_source,record_json FROM spans WHERE identity=?",
                (f"{trace_id}:{span_id}",),
            ).fetchone()
        if row is None:
            raise TelemetryError("trace_not_found", "Trace span not found.", 404)
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "evidence": json.loads(row["record_json"]),
            "otlp": MessageToDict(ExportTraceServiceRequest.FromString(row["local_source"]))
            if row["local_source"]
            else None,
        }

    def runtime_info(self):
        counts = {}
        evidence_failed = 0
        conflicts = 0
        if self._ready:
            with closing(self._connect()) as connection:
                counts = dict(
                    connection.execute("SELECT status,count(*) FROM spans GROUP BY status")
                )
                evidence_failed = connection.execute(
                    "SELECT count(*) FROM spans WHERE evidence_ingested=-1"
                ).fetchone()[0]
                conflicts = connection.execute("SELECT count(*) FROM span_conflicts").fetchone()[0]
        warnings = []
        if evidence_failed:
            warnings.append(
                "Some traces could not be normalized for incidents; original sources are retained."
            )
        if self.enabled and not self._token:
            warnings.append("Set process EPOCH_TELEMETRY_TOKEN to accept local SDK traces.")
        if self.cloud_enabled and not self._key:
            warnings.append("Cloud export is enabled but NEATLOGS_API_KEY is missing.")
        if counts.get("failed", 0):
            warnings.append("Some cloud exports failed; records are retained locally.")
        if self._warning:
            warnings.append(self._warning)
        if conflicts:
            warnings.append("Conflicting span submissions were rejected; original evidence is unchanged.")
        index = self.traces.runtime_info()
        warnings.extend(index["warnings"])
        execution = getattr(self.incidents, "execution", None)
        warnings.extend(getattr(execution, "observation_warnings", []))
        return {
            "enabled": self.enabled,
            "collector_ready": self.enabled and self._ready and bool(self._token),
            "cloud_enabled": self.cloud_enabled,
            "cloud_configured": self.cloud_enabled and bool(self._key),
            "cloud_export_accepted": bool(counts.get("delivered")),
            "cloud_readback_verified": False,
            "stored_spans": sum(counts.values()),
            "evidence_failed": evidence_failed,
            "conflicting_payloads": conflicts,
            "trace_index": index,
            "queued": counts.get("pending", 0) + counts.get("sending", 0),
            "delivered": counts.get("delivered", 0),
            "failed": counts.get("failed", 0),
            "disabled": counts.get("disabled", 0),
            "warnings": warnings,
        }
