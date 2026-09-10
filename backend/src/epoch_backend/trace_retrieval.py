"""Deterministic, trace-scoped evidence selection and explicit context limits."""

import hashlib
import json
from datetime import UTC, datetime

MAX_EVIDENCE = 12
MAX_EVIDENCE_BYTES = 12_000


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def excerpt(value, budget, terms):
    text = encoded(value)
    raw = text.encode("utf-8")
    if len(raw) <= budget:
        return {"text": text, "truncated": False}
    # Preserve the beginning and a window around a matching entity when possible.
    head = raw[:budget // 2].decode("utf-8", errors="ignore")
    hits = [text.lower().find(term) for term in terms if text.lower().find(term) >= 0]
    start = max(0, min(hits) - 80) if hits else len(head)
    tail = text[start:].encode("utf-8")[:budget // 2].decode("utf-8", errors="ignore")
    return {"text": head + " … [excerpt] … " + tail, "truncated": True}


def build_snapshot(store, trace_id, question, focus):
    summary, candidates, terms = store.question_candidates(trace_id, question, focus)
    evidence, used = [], 0
    for span in candidates:
        fields = {"input": excerpt(span["input"], 900, terms) if span["has_input"] else None,
                  "output": excerpt(span["output"], 900, terms) if span["has_output"] else None,
                  "attributes": excerpt(span["attributes"], 500, terms),
                  "resource_attributes": excerpt(span["resource_attributes"], 400, terms),
                  "events": excerpt(span["events"], 700, terms),
                  "status_message": excerpt(span["status_message"], 300, terms)}
        item = {"id": f"E{len(evidence) + 1}", "span_id": span["span_id"],
                "parent_span_id": span["parent_span_id"], "name": span["name"][:180],
                "kind": span["kind"][:80], "status": span["status"],
                "tool": (span["tool"] or "")[:180], "model": (span["model"] or "")[:180],
                "project_id": span["project_id"][:180],
                "workflow": (span["workflow"] or "")[:180],
                "session_id": (span["session_id"] or "")[:180],
                "start_time": span["start_time"], "duration_ms": span["duration_ms"],
                "fields": fields, "source_ref": span["source_ref"]}
        size = len(encoded(item).encode("utf-8"))
        if used + size > MAX_EVIDENCE_BYTES:
            continue
        evidence.append(item)
        used += size
        if len(evidence) == MAX_EVIDENCE:
            break
    warnings = store.runtime_info()["warnings"]
    if summary["missing_parent_count"]:
        warnings.append("The indexed trace has missing parents; the hierarchy is incomplete.")
    if summary["root_count"] != 1:
        warnings.append("The indexed trace does not contain exactly one root span.")
    if len(evidence) < summary["span_count"]:
        warnings.append("Only selected spans fit this question's evidence budget; other steps were omitted.")
    if any(field and field["truncated"] for item in evidence for field in item["fields"].values()):
        warnings.append("Some fields are excerpts. Open the span for complete recorded content.")
    if any(item["fields"][key] is None for item in evidence for key in ("input", "output")):
        warnings.append("Some included spans have no captured input or output.")
    snapshot = {"trace_id": trace_id, "trace_name": summary["name"][:300],
                "recorded_status": summary["status"], "indexed_span_count": summary["span_count"],
                "included_span_count": len(evidence), "focused_span_id": focus,
                "captured_at": datetime.now(UTC).isoformat(), "evidence": evidence,
                "warnings": list(dict.fromkeys(warnings)), "retrieval_version": "trace-local-v1"}
    snapshot["sha256"] = hashlib.sha256(encoded(snapshot).encode("utf-8")).hexdigest()
    return snapshot
