"""Rebuildable local projection over immutable OTLP sources, never a model input."""

import base64
import json
import math
import re
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from epoch_backend.trace_contracts import TraceSpan, TraceSpanSummary

SCHEMA_VERSION = 1
BATCH_SIZE = 200
SEARCH_FIELD_LIMIT = 64_000


class TraceError(Exception):
    def __init__(self, code, message, status=422):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def attribute_value(value):
    field = value.WhichOneof("value")
    if field == "array_value":
        return [attribute_value(item) for item in value.array_value.values]
    if field == "kvlist_value":
        return attributes(value.kvlist_value.values)
    if field == "bytes_value":
        return {"base64": base64.b64encode(value.bytes_value).decode("ascii")}
    if field is None:
        return None
    result = getattr(value, field)
    if isinstance(result, float) and not math.isfinite(result):
        return str(result)
    return result


def attributes(items):
    return {item.key: attribute_value(item.value) for item in items}


def _first(values, *keys):
    for key in keys:
        value = values.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value):
            return str(value)
    return None


def _content(values, key, prefix):
    if key in values:
        raw = values[key]
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw, parse_constant=_invalid_json_constant)
                # Keep the source string if a JSON number exceeds float range.
                _json(parsed)
                return True, parsed
            except (ValueError, RecursionError):
                pass
        return True, raw
    messages = {key: value for key, value in values.items() if key.startswith(prefix)}
    return bool(messages), messages or None


def _invalid_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _time(micros):
    return datetime.fromtimestamp(micros / 1_000_000, UTC).isoformat()


def _normalize(raw):
    request = ExportTraceServiceRequest.FromString(raw)
    resource = request.resource_spans[0]
    scope = resource.scope_spans[0]
    span = scope.spans[0]
    local = attributes(span.attributes)
    resource_values = attributes(resource.resource.attributes)
    combined = {**resource_values, **local}
    has_input, input_value = _content(combined, "input.value", "llm.input_messages.")
    has_output, output_value = _content(combined, "output.value", "llm.output_messages.")
    trace_id, span_id = span.trace_id.hex(), span.span_id.hex()
    start_us, end_us = span.start_time_unix_nano // 1000, span.end_time_unix_nano // 1000
    warnings = []
    if not has_input:
        warnings.append("Input was not captured for this span.")
    if not has_output:
        warnings.append("Output was not captured for this span.")
    if span.dropped_attributes_count or span.dropped_events_count or span.dropped_links_count:
        warnings.append("The exporter reports dropped attributes, events or links.")
    record = TraceSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=span.parent_span_id.hex() or None,
        name=span.name,
        kind=_first(combined, "openinference.span.kind", "gen_ai.operation.name") or "SPAN",
        otlp_kind=span.kind,
        project_id=_first(combined, "epoch.project_id", "project_id", "neatlogs.workflow.project_id")
        or "unassigned",
        workflow=_first(combined, "epoch.workflow", "workflow", "neatlogs.workflow_name",
                        "neatlogs.workflow.name"),
        session_id=_first(combined, "session.id", "neatlogs.session_id", "neatlogs.session.id",
                          "session_id", "gen_ai.conversation.id"),
        start_time=_time(start_us),
        end_time=_time(end_us),
        duration_ms=(span.end_time_unix_nano - span.start_time_unix_nano) / 1_000_000,
        status="recorded_error" if span.status.code == 2 else "no_recorded_error",
        status_code=span.status.code,
        status_message=span.status.message,
        tool=_first(combined, "tool.name", "mcp.tool.name", "gen_ai.tool.name", "epoch.tool"),
        model=_first(combined, "llm.model_name", "gen_ai.request.model", "gen_ai.response.model"),
        has_input=has_input,
        has_output=has_output,
        input=input_value,
        output=output_value,
        attributes=local,
        resource_attributes=resource_values,
        scope={"name": scope.scope.name, "version": scope.scope.version,
               "attributes": attributes(scope.scope.attributes)},
        events=[{"name": event.name, "time_unix_nano": str(event.time_unix_nano),
                 "attributes": attributes(event.attributes)} for event in span.events],
        links=[{"trace_id": link.trace_id.hex(), "span_id": link.span_id.hex(),
                "attributes": attributes(link.attributes)} for link in span.links],
        start_time_unix_nano=str(span.start_time_unix_nano),
        end_time_unix_nano=str(span.end_time_unix_nano),
        source_ref=f"/api/telemetry/traces/{trace_id}/spans/{span_id}",
        warnings=warnings,
    ).model_dump(mode="json")
    return record, start_us, end_us


class TraceStore:
    def __init__(self, path):
        self.path = path
        self.ready = False
        self.warning = None
        self._lock = threading.Lock()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS trace_index_state (
                id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL,
                cursor INTEGER NOT NULL DEFAULT 0)""")
            db.execute("INSERT OR IGNORE INTO trace_index_state VALUES(1,?,0)", (SCHEMA_VERSION,))
            if db.execute("SELECT version FROM trace_index_state WHERE id=1").fetchone()[0] != SCHEMA_VERSION:
                raise TraceError("index_version", "Unsupported trace index version.", 503)
            db.execute("""CREATE TABLE IF NOT EXISTS trace_spans (
                identity TEXT PRIMARY KEY, trace_id TEXT NOT NULL, span_id TEXT NOT NULL,
                parent_span_id TEXT, project_id TEXT NOT NULL, workflow TEXT, session_id TEXT,
                start_us INTEGER NOT NULL, end_us INTEGER NOT NULL, is_error INTEGER NOT NULL,
                summary_json TEXT NOT NULL, record_json TEXT NOT NULL)""")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS trace_span_ids ON trace_spans(trace_id,span_id)")
            db.execute("CREATE INDEX IF NOT EXISTS trace_span_time ON trace_spans(start_us,trace_id)")
            for field in ("project_id", "workflow", "session_id"):
                db.execute(f"CREATE INDEX IF NOT EXISTS trace_span_{field} ON trace_spans({field},trace_id)")
            db.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS trace_span_fts USING fts5(
                identity UNINDEXED, name, tool, model, input_text, output_text, error_text)""")
            db.execute("""CREATE TABLE IF NOT EXISTS trace_index_failures (
                identity TEXT PRIMARY KEY, code TEXT NOT NULL)""")
        self.ready = True

    def project_batch(self, stop=None):
        if not self.ready or not self._lock.acquire(blocking=False):
            return
        try:
            with closing(self._connect()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                cursor = db.execute("SELECT cursor FROM trace_index_state WHERE id=1").fetchone()[0]
                rows = db.execute("SELECT rowid AS sequence,identity,local_source FROM spans "
                                  "WHERE rowid>? ORDER BY rowid LIMIT ?", (cursor, BATCH_SIZE)).fetchall()
                for row in rows:
                    if stop is not None and stop.is_set():
                        break
                    if row["local_source"] is not None:
                        try:
                            record, start_us, end_us = _normalize(row["local_source"])
                            summary = {key: record[key] for key in TraceSpanSummary.model_fields}
                            summary["name"] = summary["name"][:300]
                            encoded, summary_json = _json(record), _json(summary)
                            search = [record["name"], record["tool"] or "", record["model"] or "",
                                      _json(record["input"]), _json(record["output"]),
                                      record["status_message"] + " " + _json(record["events"])]
                        except Exception:
                            db.execute("INSERT OR REPLACE INTO trace_index_failures VALUES(?,?)",
                                       (row["identity"], "normalization_failed"))
                        else:
                            db.execute("INSERT OR REPLACE INTO trace_spans VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                       (row["identity"], record["trace_id"], record["span_id"],
                                        record["parent_span_id"], record["project_id"], record["workflow"],
                                        record["session_id"], start_us, end_us,
                                        int(record["status_code"] == 2), summary_json, encoded))
                            db.execute("DELETE FROM trace_span_fts WHERE identity=?", (row["identity"],))
                            db.execute("INSERT INTO trace_span_fts VALUES(?,?,?,?,?,?,?)",
                                       (row["identity"], *(value[:SEARCH_FIELD_LIMIT] for value in search)))
                            db.execute("DELETE FROM trace_index_failures WHERE identity=?", (row["identity"],))
                    db.execute("UPDATE trace_index_state SET cursor=? WHERE id=1", (row["sequence"],))
            self.warning = None
        except Exception:
            self.warning = "Trace indexing paused after a storage error; original sources are retained."
        finally:
            self._lock.release()

    def runtime_info(self):
        result = {"ready": self.ready, "indexed_spans": None, "pending_spans": None,
                  "failed_spans": None, "source_unavailable_spans": None, "warnings": []}
        if self.ready:
            try:
                with closing(self._connect()) as db:
                    result["indexed_spans"] = db.execute("SELECT count(*) FROM trace_spans").fetchone()[0]
                    result["failed_spans"] = db.execute("SELECT count(*) FROM trace_index_failures").fetchone()[0]
                    result["source_unavailable_spans"] = db.execute(
                        "SELECT count(*) FROM spans WHERE local_source IS NULL").fetchone()[0]
                    result["pending_spans"] = db.execute("SELECT count(*) FROM spans WHERE local_source IS NOT NULL "
                        "AND rowid>(SELECT cursor FROM trace_index_state WHERE id=1)").fetchone()[0]
            except sqlite3.Error:
                result["ready"] = False
                result["warnings"].append("Trace index status could not be read; original collection is separate.")
        if result["pending_spans"]:
            result["warnings"].append("Indexing is in progress; search results are incomplete.")
        if result["failed_spans"]:
            result["warnings"].append("Some sources could not be indexed; inspect original spans using their IDs.")
        if result["source_unavailable_spans"]:
            result["warnings"].append("Historical structural events without original OTLP are excluded from this explorer.")
        if self.warning:
            result["warnings"].append(self.warning)
        if not self.ready:
            result["warnings"].append("The trace index is unavailable; original collection is separate.")
        return result

    def _require_ready(self):
        if not self.ready:
            raise TraceError("index_unavailable", "The trace index is unavailable.", 503)

    @staticmethod
    def _ids(trace_id, span_id=None):
        if not re.fullmatch(r"[a-f0-9]{32}", trace_id) or (
            span_id is not None and not re.fullmatch(r"[a-f0-9]{16}", span_id)
        ):
            raise TraceError("trace_not_found", "Trace or span not found.", 404)

    @staticmethod
    def _summary(db, trace_id):
        row = db.execute("""SELECT count(*) AS total, min(start_us) AS start_us,
            max(end_us) AS end_us, sum(is_error) AS errors,
            sum(parent_span_id IS NULL) AS roots,
            sum(parent_span_id IS NOT NULL AND NOT EXISTS(
                SELECT 1 FROM trace_spans p WHERE p.trace_id=s.trace_id
                AND p.span_id=s.parent_span_id)) AS missing
            FROM trace_spans s WHERE trace_id=?""", (trace_id,)).fetchone()
        if not row["total"]:
            raise TraceError("trace_not_found", "Trace not found in the index.", 404)
        first = db.execute("SELECT summary_json FROM trace_spans WHERE trace_id=? "
                           "ORDER BY parent_span_id IS NOT NULL,start_us,span_id LIMIT 1", (trace_id,)).fetchone()
        def distinct(field):
            return [r[0] for r in db.execute(f"SELECT DISTINCT {field} FROM trace_spans "
                    f"WHERE trace_id=? AND {field} IS NOT NULL ORDER BY {field}", (trace_id,))]
        projects = distinct("project_id")
        if len(projects) > 1 and "unassigned" in projects:
            projects.remove("unassigned")
        return {"trace_id": trace_id, "name": json.loads(first[0])["name"],
                "project_ids": projects, "workflows": distinct("workflow"),
                "session_ids": distinct("session_id"), "start_time": _time(row["start_us"]),
                "end_time": _time(row["end_us"]), "duration_ms": (row["end_us"] - row["start_us"]) / 1000,
                "span_count": row["total"], "error_count": row["errors"],
                "missing_parent_count": row["missing"], "root_count": row["roots"],
                "status": "recorded_error" if row["errors"] else "no_recorded_error"}

    def list_traces(self, *, project_id=None, workflow=None, session_id=None, q=None,
                    started_after=None, started_before=None, limit=50, offset=0):
        self._require_ready()
        clauses, params = [], []
        for field, value in (("project_id", project_id), ("workflow", workflow), ("session_id", session_id)):
            if value:
                clauses.append(f"EXISTS(SELECT 1 FROM trace_spans f WHERE f.trace_id=t.trace_id AND f.{field}=?)")
                params.append(value)
        for op, value in ((">=", started_after), ("<=", started_before)):
            if value is not None:
                clauses.append(f"t.start_us {op} ?")
                params.append(int(value.timestamp() * 1_000_000))
        if q:
            words = re.findall(r"\w+", q, flags=re.UNICODE)[:24]
            if words:
                query = " AND ".join('"' + word.replace('"', '""') + '"' for word in words)
                clauses.append("(t.trace_id=? OR EXISTS(SELECT 1 FROM trace_spans f "
                               "JOIN trace_span_fts x ON x.identity=f.identity WHERE f.trace_id=t.trace_id "
                               "AND trace_span_fts MATCH ?) OR EXISTS(SELECT 1 FROM trace_spans f "
                               "WHERE f.trace_id=t.trace_id AND f.span_id=?))")
                params.extend((q, query, q))
            else:
                clauses.append("0")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cte = "WITH t AS (SELECT trace_id,min(start_us) AS start_us FROM trace_spans GROUP BY trace_id) "
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            total = db.execute(cte + "SELECT count(*) FROM t" + where, params).fetchone()[0]
            rows = db.execute(cte + "SELECT trace_id FROM t" + where +
                              " ORDER BY start_us DESC,trace_id LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
            items = [self._summary(db, row[0]) for row in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset,
                "warnings": self.runtime_info()["warnings"]}

    def get_trace(self, trace_id, *, limit=200, offset=0):
        self._require_ready()
        self._ids(trace_id)
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            summary = self._summary(db, trace_id)
            rows = db.execute("""SELECT summary_json, parent_span_id IS NOT NULL AND NOT EXISTS(
                SELECT 1 FROM trace_spans p WHERE p.trace_id=s.trace_id AND p.span_id=s.parent_span_id)
                AS parent_missing FROM trace_spans s WHERE trace_id=?
                ORDER BY start_us,span_id LIMIT ? OFFSET ?""", (trace_id, limit, offset)).fetchall()
            spans = [{**json.loads(row["summary_json"]), "parent_missing": bool(row["parent_missing"])} for row in rows]
        warnings = self.runtime_info()["warnings"]
        if summary["missing_parent_count"]:
            warnings.append("Some parent spans have not been received or indexed.")
        if summary["root_count"] != 1:
            warnings.append("The recorded hierarchy does not contain exactly one root span.")
        if summary["span_count"] > len(spans):
            warnings.append("This is one page of spans; parents may be on another page.")
        return {"trace": summary, "spans": spans, "total": summary["span_count"],
                "limit": limit, "offset": offset, "warnings": warnings}

    def get_span(self, trace_id, span_id):
        self._require_ready()
        self._ids(trace_id, span_id)
        with closing(self._connect()) as db:
            row = db.execute("SELECT record_json FROM trace_spans WHERE trace_id=? AND span_id=?",
                             (trace_id, span_id)).fetchone()
            if not row:
                raise TraceError("trace_not_found", "Span not found in the index.", 404)
            record = json.loads(row[0])
            parent = record["parent_span_id"]
            record["parent_missing"] = bool(parent and not db.execute(
                "SELECT 1 FROM trace_spans WHERE trace_id=? AND span_id=?", (trace_id, parent)).fetchone())
        if record["parent_missing"]:
            record["warnings"].append("The parent span has not been received or indexed.")
        return record
