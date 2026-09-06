"""Protected runtime gates for generated directory and retrieval artifacts.

These gates run when a user requests a repair, never as publication authority
inside generated code. No development acceptance is implied by their presence.
"""

import copy
from pathlib import Path
from tempfile import TemporaryDirectory

from epoch_backend.candidate_runner import CandidateError
from epoch_backend.repair_surfaces import (
    CONTEXT,
    LOOKUP,
    SERIALIZER,
    artifacts,
    bundle_hash,
    invoke,
    lookup_result,
    selected_document,
)
from epoch_backend.repair_verification import component_proofs
from epoch_backend.sandbox import Sandbox


def _execute(artifact, target, arguments, budget, cancelled):
    budget.check()
    return invoke(
        artifact,
        target,
        arguments,
        cancelled=cancelled,
        timeout=min(12, budget.remaining_seconds()),
    )


def _attempt(label, action, *, expect_rejection=False):
    try:
        action()
        return {"case": label, "passed": not expect_rejection}
    except CandidateError as exc:
        if exc.code in {
            "runner_unavailable",
            "cleanup_unresolved",
            "cancelled",
            "isolation_unverified",
        }:
            raise
        return {"case": label, "passed": expect_rejection, "error": exc.code}
    except (ValueError, KeyError, TypeError) as exc:
        return {"case": label, "passed": False, "error": type(exc).__name__}


def lookup_cases(artifact, budget, cancelled):
    owner = {
        "id": "qa-red",
        "project_id": "red",
        "role": "QA owner",
        "name": "Asha",
        "channel": "#qa-red",
        "simulated": True,
        "url": "simulated://verification/red",
    }
    other = {**owner, "id": "qa-blue", "project_id": "blue", "name": "Mateo", "channel": "#qa-blue"}
    cases = [
        ("one_owner", [owner], "red"),
        ("missing_owner", [], "red"),
        ("ambiguous_owner", [owner, {**owner, "id": "qa-red-2", "name": "Another"}], "red"),
        ("unrelated_project", [other], "red"),
        ("different_owner", [owner, other], "blue"),
    ]
    results = []
    for label, records, project in cases:

        def check(records=records, project=project):
            value = _execute(
                artifact, LOOKUP, {"records": records, "project_id": project}, budget, cancelled
            )
            lookup_result(value, records, project)

        results.append(_attempt(label, check))
    return results


def context_cases(artifact, documents, project, budget, cancelled):
    documents = copy.deepcopy(documents)
    results = []
    for purpose, version in [
        ("current", None),
        ("historical", None),
        ("current", "v1"),
        ("historical", "v2"),
    ]:

        def check(purpose=purpose, version=version):
            value = _execute(
                artifact,
                CONTEXT,
                {
                    "documents": documents,
                    "project_id": project,
                    "purpose": purpose,
                    "version": version,
                },
                budget,
                cancelled,
            )
            selected_document(value, documents, project, purpose, version)

        results.append(_attempt(f"{purpose}_{version or 'default'}", check))
    for label, supplied, requested in [
        ("missing_guidance", [], project),
        ("unrelated_scope", documents, "unrelated-verification-project"),
        (
            "ambiguous_current",
            documents + [{**d, "id": d["id"] + "-duplicate"} for d in documents if d["is_current"]],
            project,
        ),
    ]:

        def reject(supplied=supplied, requested=requested):
            _execute(
                artifact,
                CONTEXT,
                {
                    "documents": supplied,
                    "project_id": requested,
                    "purpose": "current",
                    "version": None,
                },
                budget,
                cancelled,
            )

        results.append(_attempt(label, reject, expect_rejection=True))
    return results


def boundary_cases(version, sandbox, budget):
    """Exercise host access control through ordinary discovery and invocation."""
    from epoch_backend.tool_registry import ToolRegistry
    from epoch_backend.repair_surfaces import LOOKUP_NAME

    metadata = sandbox.metadata()
    with TemporaryDirectory(prefix="repair-boundary-", dir=sandbox.path.parent) as folder:
        denied = Sandbox(Path(folder) / "denied.sqlite3", "boundary", "boundary")
        denied.initialize(project_id=metadata["project_id"], grants=["tickets.list"])
        manifest = {**version, "version_id": version["id"]}
        denied.select_environment(manifest)
        registry = ToolRegistry(denied)
        visible = registry.discover_tools()["result"]["tools"]
        outcomes = [
            {"case": "denied_discovery", "passed": all(t["name"] != LOOKUP_NAME for t in visible)}
        ]
        for name, arguments in [
            (LOOKUP_NAME, {"project_id": metadata["project_id"]}),
            ("runbooks.read", {"purpose": "current"}),
        ]:
            budget.check()
            response = registry.invoke_tool(name, arguments)
            outcomes.append(
                {
                    "case": "denied_" + name,
                    "passed": not response["ok"]
                    and response["error"]["code"] in {"access_denied", "tool_not_found"},
                }
            )
        allowed = Sandbox(Path(folder) / "allowed.sqlite3", "valid-boundary", "valid-boundary")
        allowed.initialize(project_id=metadata["project_id"], grants=metadata["grants"])
        allowed.select_environment(manifest)
        if LOOKUP in artifacts(version):
            registry = ToolRegistry(allowed)
            invalid = registry.invoke_tool(LOOKUP_NAME, {"project_id": []})
            foreign = registry.invoke_tool(LOOKUP_NAME, {"project_id": "outside-this-project"})
            outcomes.extend(
                [
                    {
                        "case": "invalid_lookup_arguments",
                        "passed": invalid.get("error", {}).get("code") == "invalid_arguments",
                    },
                    {
                        "case": "cross_project_denied",
                        "passed": foreign.get("error", {}).get("code") == "access_denied",
                    },
                ]
            )
        return outcomes


def surface_proofs(version, sandbox, budget, cancelled):
    installed = artifacts(version)
    target = version.get("target", SERIALIZER)
    documents = sandbox.snapshot()["runbooks"]
    project = sandbox.metadata()["project_id"]
    serializer_proofs = (
        component_proofs(installed[SERIALIZER], cancelled, budget)
        if SERIALIZER in installed
        else []
    )
    if target == SERIALIZER:
        component = next(p["cases"] for p in serializer_proofs if p["kind"] == "component")
    elif target == LOOKUP:
        component = lookup_cases(installed[LOOKUP], budget, cancelled)
    else:
        component = context_cases(installed[CONTEXT], documents, project, budget, cancelled)
    component.extend(boundary_cases(version, sandbox, budget))
    regression = []
    if serializer_proofs:
        regression.extend(
            p for p in serializer_proofs if target != SERIALIZER or p["kind"] == "regression"
        )
    else:
        from epoch_backend.sandbox_adapters import serialize_checklist, validate_checklist_payload

        expected = {"ticket_id": "healthy", "title": "Healthy path", "items": ["Smoke test"]}
        regression.append(
            {
                "case": "builtin_healthy_serializer",
                "passed": validate_checklist_payload(serialize_checklist(**expected)) == expected,
            }
        )
    if LOOKUP in installed and target != LOOKUP:
        regression.extend(lookup_cases(installed[LOOKUP], budget, cancelled))
    if CONTEXT in installed and target != CONTEXT:
        regression.extend(context_cases(installed[CONTEXT], documents, project, budget, cancelled))
    # Builtin service behavior is exercised in actual original/fresh execution;
    # existing generated artifacts above must independently remain passing.
    return [
        {
            "kind": kind,
            "passed": all(c["passed"] for c in cases),
            "cases": cases,
            "artifact_sha256": version["artifact_sha256"],
            "bundle_sha256": version["bundle_sha256"],
        }
        for kind, cases in [("component", component), ("regression", regression)]
    ]


def verification_manifest(manifest, project):
    """Trusted isolated verification only; does not publish or grant cross-project access."""
    result = copy.deepcopy(manifest)
    result["project"] = project
    result["bundle_sha256"] = bundle_hash(result.get("artifacts", {}))
    return result


def require_artifact_use(proof, target, version_id):
    """Task success must include ordinary use of this exact generated artifact."""
    if target == SERIALIZER:
        names = {"checklists.create", "checklists.update"}
    elif target == LOOKUP:
        names = {"directory.lookup_qa_owner"}
    else:
        names = {"runbooks.read"}
    used = any(
        event["type"] == "tool.result"
        and event["payload"].get("tool_name") in names
        and event["payload"].get("implementation_version") == version_id
        for event in proof.get("events", [])
    )
    if target == LOOKUP:
        used = used and any(
            event["type"] == "tool.discovery"
            and any(
                tool["name"] == "directory.lookup_qa_owner"
                and tool.get("implementation_version") == version_id
                for tool in event["payload"].get("result", {}).get("tools", [])
            )
            for event in proof.get("events", [])
        )
    proof["verified_artifact_used"] = used
    proof["passed"] = bool(proof["passed"] and used)
    return proof
