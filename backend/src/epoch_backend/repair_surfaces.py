"""Host-owned artifact boundaries; generated functions execute only in Docker."""

import copy
import json

from epoch_backend.candidate_runner import CandidateError, CandidateRunner, digest

SERIALIZER = "checklist_serializer.py"
LOOKUP = "qa_lookup.py"
CONTEXT = "runbook_selector.py"
LOOKUP_NAME = "directory.lookup_qa_owner"
ENTRYPOINTS = {SERIALIZER: "serialize_checklist", LOOKUP: "lookup_owner", CONTEXT: "select_runbook"}
LOOKUP_INPUT = {
    "type": "object",
    "properties": {"project_id": {"type": "string", "minLength": 1, "maxLength": 100}},
    "required": ["project_id"],
    "additionalProperties": False,
}
LOOKUP_OUTPUT = {
    "type": "object",
    "properties": {
        "status": {"enum": ["found", "missing", "ambiguous"]},
        "project_id": {"type": "string"},
        "owner": {"anyOf": [{"type": "object"}, {"type": "null"}]},
    },
    "required": ["status", "project_id", "owner"],
    "additionalProperties": False,
}


def bundle_hash(artifacts):
    return digest(json.dumps(artifacts, sort_keys=True, separators=(",", ":")))


def artifacts(manifest):
    if "artifacts" in manifest:
        values = copy.deepcopy(manifest["artifacts"])
        if manifest.get("bundle_sha256") != bundle_hash(values):
            raise CandidateError("artifact_changed", "Environment bundle digest mismatch.")
    elif manifest.get("source"):
        values = {
            manifest.get("target", SERIALIZER): {
                key: manifest[key]
                for key in ("source", "artifact_sha256", "image_id", "runner_version")
            }
        }
    else:
        values = {}
    for target, artifact in values.items():
        if target not in ENTRYPOINTS or digest(artifact["source"]) != artifact["artifact_sha256"]:
            raise CandidateError("artifact_changed", "Unknown or changed environment artifact.")
        if target == LOOKUP:
            validate_lookup_contract(artifact.get("tool_contract"))
    return values


def normalize_tool_contract(value):
    if value is None:
        raise CandidateError("invalid_tool_contract", "A generated lookup contract is required.")
    try:
        data = value.model_dump()
        contract = {
            "name": data["name"],
            "description": data["description"],
            "input_schema": json.loads(data["input_schema_json"]),
            "output_schema": json.loads(data["output_schema_json"]),
        }
    except (ValueError, KeyError, AttributeError) as exc:
        raise CandidateError("invalid_tool_contract", "Generated schema JSON is invalid.") from exc
    validate_lookup_contract(contract)
    return contract


def validate_lookup_contract(contract):
    if (
        not isinstance(contract, dict)
        or contract.get("name") != LOOKUP_NAME
        or contract.get("input_schema") != LOOKUP_INPUT
        or contract.get("output_schema") != LOOKUP_OUTPUT
        or not isinstance(contract.get("description"), str)
        or not 1 <= len(contract["description"].strip()) <= 1500
        or set(contract) != {"name", "description", "input_schema", "output_schema"}
    ):
        raise CandidateError(
            "invalid_tool_contract", "Generated lookup contract exceeds its authorized interface."
        )


def invoke(artifact, target, arguments, *, cancelled=None, timeout=12):
    if digest(artifact["source"]) != artifact["artifact_sha256"]:
        raise CandidateError("artifact_changed", "Executable source digest mismatch.")
    return CandidateRunner(artifact["image_id"]).run(
        artifact["source"],
        arguments,
        entrypoint=ENTRYPOINTS[target],
        cancelled=cancelled,
        timeout=timeout,
    )


def lookup_result(result, records, project):
    """Validate returned identity/ambiguity against granted data; never fill in an answer."""
    from jsonschema import validate

    validate(instance=result, schema=LOOKUP_OUTPUT)
    matches = [r for r in records if r.get("project_id") == project and r.get("role") == "QA owner"]
    expected = "missing" if not matches else "found" if len(matches) == 1 else "ambiguous"
    if (
        result["project_id"] != project
        or result["status"] != expected
        or (expected != "found" and result["owner"] is not None)
        or (expected == "found" and result["owner"] != matches[0])
    ):
        raise CandidateError(
            "invalid_lookup_result", "Lookup fabricated or misclassified directory evidence."
        )
    return result


def selected_document(result, documents, project, purpose, version):
    if not isinstance(result, dict) or set(result) != {"document_id"}:
        raise CandidateError(
            "invalid_context_result", "Selector must return one existing document ID."
        )
    eligible = [
        d
        for d in documents
        if d["project_id"] == project
        and (d["version"] == version if version else d["is_current"] == (purpose == "current"))
    ]
    if len(eligible) != 1:
        raise CandidateError("context_unresolved", "Applicable guidance is missing or ambiguous.")
    matches = [d for d in eligible if d["id"] == result["document_id"]]
    if len(matches) != 1:
        raise CandidateError(
            "context_unresolved", "Selected guidance is missing, ambiguous or outside scope."
        )
    document = matches[0]
    if version and document["version"] != version:
        raise CandidateError(
            "context_unresolved", "Selector ignored the explicit historical version."
        )
    if not version and purpose == "current" and not document["is_current"]:
        raise CandidateError(
            "context_unresolved", "Selector returned superseded guidance for current work."
        )
    if not version and purpose == "historical" and document["is_current"]:
        raise CandidateError("context_unresolved", "Selector discarded historical guidance.")
    return document


def investigation(target, sandbox, events):
    metadata = sandbox.metadata()
    installed = artifacts(metadata.get("adapter_manifest", {}))
    if target == LOOKUP:
        if "directory.read" not in metadata["grants"] or LOOKUP in installed:
            raise CandidateError(
                "repair_unsupported",
                "Lookup is denied or already installed; absence is not established.",
            )
        return {
            "target": target,
            "editable_source": "",
            "entrypoint": "lookup_owner(records, project_id) -> dict",
            "resource_contract": "Host supplies only granted current-project directory records. Preserve exact record objects; never guess names.",
            "tool_contract": {
                "name": LOOKUP_NAME,
                "description": "Generate an accurate scoped QA-owner lookup description.",
                "input_schema": LOOKUP_INPUT,
                "output_schema": LOOKUP_OUTPUT,
            },
            "scoped_discovery": [
                {"event_id": e["id"], "lookup_absent": True}
                for e in events
                if e["type"] == "tool.discovery"
            ][-1:],
            "directory_schema": {
                "fields": ["id", "project_id", "role", "name", "channel", "url", "simulated"],
                "required_role": "QA owner",
                "simulated": True,
            },
        }
    if target == CONTEXT:
        if "runbooks.read" not in metadata["grants"]:
            raise CandidateError("repair_unsupported", "Runbook access is not granted.")
        return {
            "target": target,
            "editable_source": installed.get(CONTEXT, {}).get("source", ""),
            "entrypoint": "select_runbook(documents, project_id, purpose, version) -> {'document_id': existing id}",
            "resource_contract": "Return the selected document id in the document_id output key, using the unique version-specific id field, not the logical document_id field. Select existing scoped source IDs only. is_current means applicable approved release guidance. Explicit version wins; preserve historical access. Missing/ambiguous scope must raise ValueError, never guess.",
            "supplied_context": [
                {
                    "event_id": e["id"],
                    "source_digest": digest(
                        json.dumps(e["payload"].get("source", {}), sort_keys=True)
                    ),
                    "source_is_current": e["payload"].get("source", {}).get("is_current") is True,
                    "requested_current": e["payload"].get("requested", {}).get("purpose")
                    == "current",
                }
                for e in events
                if e["type"] == "context.supplied"
            ],
            "source_schema": {
                "fields": [
                    "id",
                    "document_id",
                    "project_id",
                    "scope",
                    "version",
                    "is_current",
                    "content",
                    "url",
                    "simulated",
                ],
                "versions": ["v1", "v2"],
                "is_current_is_authoritative": True,
            },
            "observed_destination_disagrees_with_trusted_criteria": True,
            "raw_sources_retained_locally": True,
        }
    return {}


def extended_trigger(events, sandbox):
    """Use actual scoped discovery and supplied-context evidence, not scenario names."""
    metadata = sandbox.metadata()
    installed = artifacts(metadata.get("adapter_manifest", {}))
    checks = [e for e in events if e["type"] == "verification.completed"]
    failed = (
        {c["id"] for c in checks[-1]["payload"].get("checks", []) if not c["passed"]}
        if checks
        else set()
    )
    discoveries = [e for e in events if e["type"] == "tool.discovery"]
    if (
        "qa_owner" in failed
        and metadata.get("require_qa_owner")
        and "directory.read" in metadata["grants"]
        and LOOKUP not in installed
        and discoveries
    ):
        event = discoveries[-1]
        names = {t["name"] for t in event["payload"]["result"]["tools"]}
        if LOOKUP_NAME not in names:
            return {**event, "repair_target": LOOKUP}
    if "qa_notification" not in failed or "runbooks.read" not in metadata["grants"]:
        return None
    wrong = [m for m in sandbox.snapshot()["messages"] if m["channel"] != metadata["qa_channel"]]
    for event in reversed(events):
        if event["type"] != "context.supplied":
            continue
        source = event["payload"].get("source", {})
        requested = event["payload"].get("requested", {})
        if (
            source.get("project_id") == metadata["project_id"]
            and source.get("is_current") is False
            and requested.get("purpose") == "current"
            and not requested.get("version")
            and any(m["channel"] in source.get("content", "") for m in wrong)
        ):
            return {**event, "repair_target": CONTEXT}
    return None
