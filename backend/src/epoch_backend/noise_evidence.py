"""Bounded document evidence for a conversation's recorded noise investigation.

Reading an upload's saved inspection is not an execution of documents.read. The
snapshot keeps that distinction explicit, even when both refer to the same bytes.
"""

import json
from contextlib import closing

from epoch_backend.context_policy import digest, encoded, stamp
from epoch_backend.trace_retrieval import build_snapshot
from epoch_backend.trace_store import TraceError

MAX_CONTEXT_RECORDS = 200
MAX_SOURCE_DOCUMENTS = 16
MAX_DOCUMENT_TEXT = 10_000
MAX_TRACE_TEXT = 2_600
MAX_SNAPSHOT_TEXT = 18_000
OMISSION = "\n[Excerpt: intervening source text omitted]\n"


def _text_excerpt(text, limit, terms):
    """Keep exact, separate source passages; never invent a connecting sentence."""
    if len(text) <= limit:
        return text, False
    if limit < len(OMISSION) + 120:
        return text[:max(0, limit - len(OMISSION))] + OMISSION, True
    available = limit - 2 * len(OMISSION)
    head_size, tail_size = available // 3, available // 3
    middle_size = available - head_size - tail_size
    lower = text.casefold()
    # Version relationships are useful across domains, not tied to a demo fixture.
    relationship_terms = ("supersed", "replaces", "replaced by", "withdrawn", "obsolete")
    hits = [lower.find(term, head_size) for term in relationship_terms]
    hits = [hit for hit in hits if head_size <= hit < len(text) - tail_size]
    if not hits:
        hits = [lower.find(term, head_size) for term in terms]
        hits = [hit for hit in hits if head_size <= hit < len(text) - tail_size]
    start = max(head_size, min(hits) - 120) if hits else head_size
    start = min(start, len(text) - tail_size - middle_size)
    return (text[:head_size] + OMISSION + text[start:start + middle_size]
            + OMISSION + text[-tail_size:]), True


def _plain(value):
    """Unwrap recorded JSON without double-escaping its actual document text."""
    for _ in range(8):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                break
        elif isinstance(value, dict) and value.get("ok") is True and "result" in value:
            value = value["result"]
        else:
            break
    return value


def _source_id(value):
    return str(value.get("asset_id", value.get("id", ""))) if isinstance(value, dict) else ""


def _inspection_text(asset):
    inspection = asset.get("inspection") or {}
    pages = inspection.get("pages") or []
    valid = [page for page in pages if isinstance(page, dict) and isinstance(page.get("text"), str)]
    text = "\n".join(page["text"] for page in valid)
    complete = (bool(text.strip()) and len(valid) == len(pages)
                and inspection.get("page_count") == len(valid)
                and not any(page.get("text_truncated", True) for page in valid))
    return text, complete


def _records(store, chat, operation):
    with closing(store.connect()) as db:
        rows = db.execute(
            "SELECT body FROM context_decisions WHERE chat_id=? AND operation_id=? "
            "ORDER BY created_at,id LIMIT ?",
            (str(chat.id), str(operation.id), MAX_CONTEXT_RECORDS + 1),
        ).fetchall()
    records = [json.loads(row[0]) for row in rows[:MAX_CONTEXT_RECORDS]]
    return records, len(rows) > MAX_CONTEXT_RECORDS


def _trace_items(candidates, root_span_id, terms):
    """Keep the request, errors and actual invocations ahead of tool discovery."""
    ranked = sorted(enumerate(candidates), key=lambda pair: (
        0 if pair[1]["span_id"] == root_span_id else
        1 if pair[1].get("status") == "recorded_error" else
        3 if any(term in pair[1].get("name", "") for term in ("describe_tool", "list_tools")) else 2,
        pair[0],
    ))
    items, used, truncated = [], 0, False
    for _, span in ranked:
        fields, item_cut = {}, False
        for name, limit in (("input", 500), ("output", 650), ("events", 220), ("status_message", 140)):
            value = _plain(span.get(name))
            if value in (None, "", [], {}):
                continue
            text = value if isinstance(value, str) else encoded(value)
            text, cut = _text_excerpt(text, limit, terms)
            fields[name] = {"text": text, "truncated": cut}
            item_cut |= cut
        item = {"span_id": span["span_id"], "parent_span_id": span.get("parent_span_id"),
                "name": span.get("name", "")[:180], "kind": span.get("kind", "")[:80],
                "status": span.get("status"), "tool": span.get("tool"), "fields": fields,
                "source_ref": span.get("source_ref")}
        size = len(encoded(item))
        if used + size <= MAX_TRACE_TEXT:
            items.append(item)
            used += size
            truncated |= item_cut
    return items, truncated


def build_noise_snapshot(traces, store, chat, operation, issue, source_snapshot, sandbox):
    """Build a local, immutable evidence snapshot without tools or model calls."""
    if chat.environment != "pdf_workshop":
        return build_snapshot(traces, operation.trace_id, issue, None)

    summary, candidates, terms = traces.question_candidates(operation.trace_id, issue, None)
    catalog = {str(source["id"]): source for source in source_snapshot.get("sources", [])}
    records, records_omitted = _records(store, chat, operation)
    warnings = list(traces.runtime_info()["warnings"])
    observed = {identity: {"listed": 0, "current_listed": 0, "historical_listed": 0,
                           "read": 0, "read_requested": 0}
                for identity in catalog}
    delivered_reads = {}
    exposed = set()
    unmatched = set()
    invalid_records = 0
    for record in records:
        if (str(record.get("chat_id")) != str(chat.id)
                or str(record.get("operation_id")) != str(operation.id)
                or record.get("delivered_sha256") != digest(record.get("delivered"))):
            invalid_records += 1
            continue
        tool = record.get("tool")
        if tool not in {"documents.list", "documents.read", "documents.inspect"}:
            continue
        source_hashes = {str(source.get("id")): source.get("sha256")
                         for source in record.get("sources", []) if isinstance(source, dict)}
        delivered = _plain(record.get("delivered"))
        rows = delivered if isinstance(delivered, list) else [delivered] if isinstance(delivered, dict) else []
        requested = str(record.get("query", {}).get("asset_id", ""))
        if tool == "documents.read" and requested in observed:
            observed[requested]["read_requested"] += 1
        for row in rows:
            identity = _source_id(row)
            if not identity:
                continue
            current = catalog.get(identity)
            recorded_hash = source_hashes.get(identity)
            if (not current or recorded_hash != current["sha256"]
                    or row.get("sha256", recorded_hash) != recorded_hash):
                unmatched.add(identity)
                continue
            exposed.add(identity)
            evidence = observed[identity]
            evidence["listed"] += int(tool == "documents.list")
            if tool == "documents.list":
                query = record.get("query", {})
                current_query = query.get("purpose", "current") == "current" and not query.get("version")
                evidence["current_listed" if current_query else "historical_listed"] += 1
            evidence["read"] += int(tool == "documents.read")
            if tool == "documents.read" and isinstance(row.get("text"), str) and row["text"].strip():
                candidate = {"text": row["text"], "complete": not row.get("text_truncated", True),
                             "context_decision_id": record["id"]}
                previous = delivered_reads.get(identity)
                if not previous or (candidate["complete"], len(candidate["text"])) > (previous["complete"], len(previous["text"])):
                    delivered_reads[identity] = candidate

    # Upload inspection is cached during ingestion. It is never rerun here.
    assets = {}
    if sandbox.path.exists() and str(sandbox.task_id) == str(chat.id):
        assets = {str(asset["id"]): asset for asset in sandbox.assets()
                  if str(asset.get("chat_id")) == str(chat.id)
                  and asset.get("project_id") == chat.project_id}
    ordered = sorted(catalog, key=lambda identity: (identity not in exposed, identity not in delivered_reads,
                                                   catalog[identity].get("name", ""), identity))
    chosen = ordered[:MAX_SOURCE_DOCUMENTS]
    if len(chosen) < len(ordered):
        warnings.append(f"Only {len(chosen)} of {len(ordered)} source documents fit this investigation; others were not inspected.")

    documents, evidence = [], []
    for identity in chosen:
        source = catalog[identity]
        historical = delivered_reads.get(identity)
        asset = assets.get(identity)
        cached_text, cached_complete = _inspection_text(asset) if asset and asset.get("sha256") == source["sha256"] else ("", False)
        if historical and (historical["complete"] or not cached_text):
            text, complete = historical["text"], historical["complete"]
            provenance = "recorded_delivery"
        else:
            text, complete = cached_text, cached_complete
            provenance = "current_saved_inspection"
        source_ref = {"asset_id": identity, "sha256": source["sha256"], "chat_id": str(chat.id),
                      "provenance": provenance}
        if provenance == "recorded_delivery":
            source_ref["context_decision_id"] = historical["context_decision_id"]
        evidence_id = f"E{len(evidence) + 1}"
        documents.append({"source_id": identity, "sha256": source["sha256"],
                          "name": source["name"], "kind": source["kind"], "text": text,
                          "complete": complete, "evidence_id": evidence_id, "provenance": provenance,
                          "recorded_read": bool(observed[identity]["read"]),
                          "exposed_in_selected_run": identity in exposed})
        labels = source_snapshot.get("labels", {}).get(identity)
        if labels and labels.get("sha256") == source["sha256"]:
            documents[-1]["current_metadata"] = labels
        evidence.append({"id": evidence_id, "span_id": operation.trace_span_id,
                         "name": source["name"], "kind": "source_document", "source_ref": source_ref,
                         "fields": {"document_ref": f"source_documents[{len(documents) - 1}]",
                                    "source_id": identity, "sha256": source["sha256"]}})

    observed_rows = [{"source_id": identity, "listed_count": observed[identity]["listed"],
                      "current_listed_count": observed[identity]["current_listed"],
                      "historical_or_version_listed_count": observed[identity]["historical_listed"],
                      "read_count": observed[identity]["read"], "read_requested_count": observed[identity]["read_requested"]}
                     for identity in chosen]
    evidence.append({"id": f"E{len(evidence) + 1}", "span_id": operation.trace_span_id,
                     "name": "Recorded source exposure", "kind": "context_selection",
                     "source_ref": {"chat_id": str(chat.id), "operation_id": str(operation.id)},
                     "fields": {"sources": observed_rows, "context_record_count": len(records)}})
    trace_items, trace_cut = _trace_items(candidates, operation.trace_span_id, terms)
    for item in trace_items:
        evidence.append({"id": f"E{len(evidence) + 1}", **item})
    represented = {item["span_id"] for item in evidence if item.get("span_id")}
    if records_omitted:
        warnings.append(f"Only the first {MAX_CONTEXT_RECORDS} recorded context decisions were inspected; later reads may be absent.")
    if unmatched:
        warnings.append(f"{len(unmatched)} recorded source identities could not be matched to the current authorized catalog and content hash.")
    if invalid_records:
        warnings.append(f"{invalid_records} context records had inconsistent scope or content digests and were excluded from exposure evidence.")
    if summary["missing_parent_count"]:
        warnings.append("The indexed trace has missing parents; its hierarchy is incomplete.")
    if summary["root_count"] != 1:
        warnings.append("The indexed trace does not contain exactly one root span.")
    if len(represented) < summary["span_count"]:
        warnings.append("Some trace spans were omitted from this snapshot; recorded source exposure is summarized separately.")
    if trace_cut:
        warnings.append("Included trace fields contain bounded excerpts.")
    if any(document["provenance"] == "current_saved_inspection" for document in documents):
        warnings.append("Current saved PDF text supplements the recorded run. Its presence does not establish that Hermes read that text.")
    snapshot = {"trace_id": operation.trace_id, "trace_name": summary["name"][:300],
                "recorded_status": summary["status"], "indexed_span_count": summary["span_count"],
                "included_span_count": len(represented), "focused_span_id": None, "captured_at": stamp(),
                "evidence": evidence, "source_documents": documents, "exposed_source_ids": sorted(exposed),
                "context_record_count": len(records), "context_records_complete": not records_omitted and not invalid_records,
                "warnings": warnings, "retrieval_version": "noise-documents-v1"}
    _fit_documents(snapshot, terms)
    snapshot["warnings"] = list(dict.fromkeys(snapshot["warnings"]))
    snapshot["sha256"] = digest(snapshot)
    if len(encoded(snapshot)) > MAX_SNAPSHOT_TEXT:
        raise TraceError("noise_evidence_limit",
                         "Source identities and metadata exceed the local investigation budget. No analysis or filter was created.", 422)
    return snapshot


def _fit_documents(snapshot, terms):
    """Share the remaining prompt budget among sources before trimming any text."""
    documents = snapshot["source_documents"]
    originals = [document["text"] for document in documents]
    for document in documents:
        document["text"] = ""
    omitted = 0
    # Large catalogs can consume the budget with identities alone. Omit the least
    # prioritized document before allowing its headers to crowd out every text.
    while len(documents) > 1 and len(encoded(snapshot)) > MAX_SNAPSHOT_TEXT - 2_000:
        removed = documents.pop()
        originals.pop()
        snapshot["evidence"] = [item for item in snapshot["evidence"] if item["id"] != removed["evidence_id"]]
        for item in snapshot["evidence"]:
            if item["kind"] == "context_selection" and "sources" in item["fields"]:
                item["fields"]["sources"] = [row for row in item["fields"]["sources"]
                                             if row["source_id"] != removed["source_id"]]
        omitted += 1
    if omitted:
        snapshot["warnings"].append(f"{omitted} additional source documents were omitted to leave room for readable evidence text.")
    remaining = min(MAX_DOCUMENT_TEXT, max(0, MAX_SNAPSHOT_TEXT - len(encoded(snapshot)) - 600))
    allocations = [0] * len(documents)
    pending = set(range(len(documents)))
    while pending and remaining:
        allowance = max(1, remaining // len(pending))
        for index in sorted(pending):
            added = min(len(originals[index]) - allocations[index], allowance, remaining)
            allocations[index] += added
            remaining -= added
            if allocations[index] == len(originals[index]):
                pending.remove(index)
    for document, original, allocation in zip(documents, originals, allocations):
        if allocation < len(original) and allocation < 120:
            document["text"] = ""
            document["complete"] = False
        else:
            document["text"], cut = _text_excerpt(original, allocation, terms)
            document["complete"] &= not cut
    # JSON escaping also consumes prompt space. Account for it after allocation.
    while len(encoded(snapshot)) > MAX_SNAPSHOT_TEXT - 400 and any(document["text"] for document in documents):
        index = max(range(len(documents)), key=lambda index: len(documents[index]["text"]))
        document = documents[index]
        reduction = max(120, len(encoded(snapshot)) - MAX_SNAPSHOT_TEXT + 400)
        allowance = max(0, len(document["text"]) - reduction)
        document["text"] = _text_excerpt(originals[index], allowance, terms)[0] if allowance >= 120 else ""
        document["complete"] = False
    if any(not document["complete"] for document in documents):
        snapshot["warnings"].append("Some source texts are unavailable or excerpted; complete=false identifies each. Missing text never establishes that a source was not read.")
