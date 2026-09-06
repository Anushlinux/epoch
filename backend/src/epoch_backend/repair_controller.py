"""Evidence-triggered generation, isolated verification and trusted publication."""

import copy
import difflib
import inspect
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from epoch_backend.candidate_runner import RUNNER_VERSION, CandidateError, digest, inspect_runner
from epoch_backend.environment_store import EnvironmentStore, stamp
from epoch_backend.operation_budget import BudgetExceeded
from epoch_backend.repair_contracts import RepairProposal
from epoch_backend.repair_verification import (
    clone_sandbox,
    component_proofs,
    isolation_proof,
    run_verification,
)
from epoch_backend.sandbox import Sandbox, SandboxError
from epoch_backend.sandbox_adapters import ChecklistPayload, serialize_checklist

DIAGNOSIS_INSTRUCTIONS = """You are Epoch's OpenAI debugger for one authorized Python adapter.
Inspect the actual failure event, submitted arguments, serializer source and trusted
service contract. Diagnose from these observations, not a fixture/scenario label.
Return one structured response. If the evidence does not support a serializer fix,
return unsupported and an empty source. Otherwise return the complete corrected
Python module in source, targeted only at checklist_serializer.py. It must define
serialize_checklist(ticket_id, title, items, *, legacy=False) and return the real
service payload. Retain valid caller values and behavior on healthy inputs. This
function has no service/database, filesystem, network, credential or publication
authority. It must not hardcode example IDs/items, fabricate business effects, edit
tests or bypass the contract. Cite actual supplied event UUIDs and disclose uncertainty.
You may use the Python standard library; third-party packages are not installed.
Your source is executed only inside an isolated container and is subject to external
trusted tests. Earlier rejected candidates and their checks are evidence to improve
the next proposal. Do not return Markdown fences around the Python module.
"""


def supported_error(events: list[dict]) -> dict | None:
    for event in reversed(events):
        payload = event.get("payload", {})
        if (
            event.get("type") == "tool.error"
            and payload.get("tool_name") in {"checklists.create", "checklists.update"}
            and payload.get("error", {}).get("code") == "adapter_contract_error"
        ):
            return event
    return None


def protected_identity():
    directory = Path(__file__).parent
    return {
        name: sha256((directory / name).read_bytes()).hexdigest()
        for name in (
            "trusted_checks.py",
            "sandbox.py",
            "sandbox_adapters.py",
            "tool_registry.py",
            "candidate_runner.py",
            "repair_verification.py",
            "hermes_bridge.py",
        )
    }


def repair_environment(
    record,
    sandbox,
    store: EnvironmentStore,
    budget,
    call_debugger,
    emit,
    persist,
    image,
    cancelled,
    event,
) -> dict:
    from epoch_backend.supervisor import executor_instructions

    operation = record.supervision.operations[-1]
    metadata = copy.deepcopy(sandbox.metadata())
    project = metadata["project_id"]
    previous = metadata.get("adapter_manifest", {}).get("version_id", "builtin")
    prior_source = (
        ("import json\n\n" + inspect.getsource(serialize_checklist))
        if previous == "builtin"
        else store.version(previous, project=project)["source"]
    )
    protected = protected_identity()
    before = sandbox.snapshot()
    report = {
        "id": str(uuid4()),
        "project": project,
        "run_id": str(record.id),
        "revision_id": str(operation.id),
        "trigger": event,
        "created_at": stamp(),
        "status": "investigating",
        "previous_version": previous,
        "attempts": [],
        "editable_target": "checklist_serializer.py",
        "source_before": prior_source,
        "source_before_sha256": digest(prior_source),
        "protected_baseline": protected,
        "criteria_sha256": metadata["criteria_sha256"],
        "state_before": before,
        "limits": {
            "max_attempts": 2,
            "overall_max_model_requests": budget.overall_max,
            "stage_max_turns": budget.max_turns,
            "stage_seconds": budget.stage_seconds,
            "overall_seconds": 3 * budget.stage_seconds,
            "cost_unit": "authorized_model_request",
            "guaranteed_usd_cap": None,
        },
    }
    operation.repairs.append(report)

    def save():
        store.save_repair(report)
        persist()

    save()
    emit("repair.triggered", {"repair_id": report["id"], "event": event})
    active_candidate = None
    try:
        budget.check()
        runner = inspect_runner(image, timeout=budget.remaining_seconds())
        report["runner"] = runner
        if not runner["available"]:
            raise CandidateError("runner_unavailable", runner["error"])
        isolation = isolation_proof(runner["image_id"], cancelled, budget)
        report["isolation"] = isolation
        save()
        if not isolation["passed"]:
            raise CandidateError("isolation_unverified", "Actual container boundary probes failed.")
        for number in range(1, 3):
            budget.check()
            attempt = {
                "number": number,
                "status": "generating",
                "created_at": stamp(),
                "proofs": [],
            }
            report["attempts"].append(attempt)
            save()
            evidence = [
                e
                for e in sandbox.events()
                if e["payload"].get("call_id") == event["payload"].get("call_id")
            ]
            proposal = call_debugger(
                "repair",
                DIAGNOSIS_INSTRUCTIONS,
                {
                    "observed_failure": event,
                    "related_events": evidence,
                    "editable_source": prior_source,
                    "service_contract": ChecklistPayload.model_json_schema(),
                    "interface": (
                        "serialize_checklist(ticket_id, title, items, *, legacy=False) -> dict"
                    ),
                    "rejected_attempts": [
                        {
                            "proposal": a.get("proposal"),
                            "proofs": [
                                {
                                    k: p.get(k)
                                    for k in (
                                        "kind",
                                        "passed",
                                        "cases",
                                        "executor_invariants_match",
                                    )
                                }
                                for p in a["proofs"]
                            ],
                        }
                        for a in report["attempts"][:-1]
                    ],
                },
                RepairProposal,
            )
            attempt["proposal"] = proposal.model_dump(mode="json")
            allowed_ids = {event["id"], *(e["id"] for e in evidence)}
            if any(str(identity) not in allowed_ids for identity in proposal.evidence_ids):
                raise CandidateError(
                    "diagnosis_unsourced", "Debugger cited evidence outside this failure."
                )
            if proposal.outcome != "repair":
                raise CandidateError("repair_unsupported", proposal.diagnosis)
            diff = "".join(
                difflib.unified_diff(
                    prior_source.splitlines(True),
                    proposal.source.splitlines(True),
                    fromfile="before/checklist_serializer.py",
                    tofile="after/checklist_serializer.py",
                )
            )
            version = store.stage(
                project,
                proposal.source,
                image_id=runner["image_id"],
                runner_version=RUNNER_VERSION,
                parent=previous,
                diagnosis=attempt["proposal"],
                diff=diff,
            )
            active_candidate = version["id"]
            attempt.update(
                status="verifying",
                candidate_id=version["id"],
                artifact_sha256=version["artifact_sha256"],
                diff=diff,
            )
            save()
            emit("repair.candidate_staged", {"repair_id": report["id"], "candidate": version})
            proofs = attempt["proofs"]
            proofs.append({**isolation, "artifact_sha256": version["artifact_sha256"]})
            proofs.extend(component_proofs(version, cancelled, budget))
            save()
            budget.check()
            if all(p["passed"] for p in proofs):
                folder = sandbox.path.parent / "repair-verification" / version["id"]
                original = clone_sandbox(sandbox, folder / "original" / "sandbox.sqlite3")
                manifest = store.manifest(project, version["id"], staged=True)
                original.select_environment(manifest, expected_version=previous)

                def progress(proof, attempt=attempt):
                    attempt["active_verification"] = copy.deepcopy(proof)
                    save()

                proof = run_verification(
                    "original_replay",
                    original,
                    record.brief.instructions,
                    record.baseline,
                    budget,
                    progress,
                    cancelled,
                )
                proof["artifact_sha256"] = version["artifact_sha256"]
                proofs.append(proof)
                save()
                if proof["passed"]:
                    fresh_id = str(uuid4())
                    fresh = Sandbox(
                        folder / "fresh" / "sandbox.sqlite3", str(record.task_id), fresh_id
                    )
                    fresh.initialize(
                        scenario=metadata["scenario"],
                        project_id=project,
                        release=metadata["release"][:60] + "-verify-" + fresh_id[:6],
                        grants=metadata["grants"],
                    )
                    fresh.revise_requirements(
                        str(uuid4()),
                        [*metadata["expected_items"], "Verify multilingual notes: 安全"],
                        metadata.get("required_message_phrases", []),
                        [{"kind": "trusted_verification", "source": "fresh-release-v1"}],
                    )
                    fresh.select_environment(manifest)
                    plan = operation.plan.model_copy(
                        update={
                            "instructions": (
                                "Prepare the complete release explicitly specified below "
                                "using ordinary scoped tool discovery."
                            )
                        }
                    )
                    instruction = executor_instructions(plan, fresh.metadata())
                    proof = run_verification(
                        "fresh_release",
                        fresh,
                        instruction,
                        record.baseline,
                        budget,
                        progress,
                        cancelled,
                    )
                    proof["artifact_sha256"] = version["artifact_sha256"]
                    proofs.append(proof)
                    save()
            budget.check()
            if (
                protected_identity() != protected
                or sandbox.snapshot() != before
                or sandbox.metadata() != metadata
            ):
                raise CandidateError(
                    "baseline_changed",
                    "Protected code, criteria or original effects changed during verification.",
                )
            if {p["kind"] for p in proofs} == {
                "isolation",
                "component",
                "regression",
                "original_replay",
                "fresh_release",
            } and all(p["passed"] for p in proofs):
                published = store.publish(version["id"], proofs, expected_active=previous)
                active_candidate = None
                # Current Hermes pass has returned; no tool call is in flight.
                try:
                    sandbox.select_environment(store.manifest(project), expected_version=previous)
                except Exception as exc:
                    raise CandidateError(
                        "activation_unresolved",
                        "Verified version published but run activation failed.",
                    ) from exc
                record.environment_version = published["id"]
                attempt.update(status="published", finished_at=stamp())
                report.update(
                    status="published",
                    version_id=published["id"],
                    finished_at=stamp(),
                    overall_requests=budget.overall_used,
                    state_before_activation=before,
                )
                save()
                emit(
                    "environment.published",
                    {
                        "repair_id": report["id"],
                        "version_id": published["id"],
                        "artifact_sha256": published["artifact_sha256"],
                        "previous": previous,
                    },
                )
                return published
            store.reject(version["id"], proofs, "One or more protected verification checks failed.")
            active_candidate = None
            attempt.update(status="rejected", finished_at=stamp())
            emit(
                "repair.candidate_rejected",
                {"repair_id": report["id"], "candidate_id": version["id"]},
            )
            save()
        raise CandidateError(
            "repair_attempt_limit", "Two candidates failed verification; no version was published."
        )
    except (CandidateError, BudgetExceeded, SandboxError) as exc:
        report.update(
            status="blocked", error={"code": exc.code, "message": str(exc)}, finished_at=stamp()
        )
        if active_candidate:
            store.reject(active_candidate, report["attempts"][-1]["proofs"], str(exc))
            report["attempts"][-1]["status"] = "rejected"
        if report["attempts"] and report["attempts"][-1]["status"] == "generating":
            report["attempts"][-1].update(status="blocked", finished_at=stamp())
        save()
        emit("repair.blocked", {"repair_id": report["id"], "error": report["error"]})
        raise
    except Exception as exc:
        report.update(
            status="blocked",
            error={"code": "repair_error", "message": f"Repair stopped ({type(exc).__name__})."},
            finished_at=stamp(),
        )
        if active_candidate:
            store.reject(
                active_candidate, report["attempts"][-1]["proofs"], report["error"]["message"]
            )
        if report["attempts"] and report["attempts"][-1]["status"] in {"generating", "verifying"}:
            report["attempts"][-1].update(
                status="rejected" if active_candidate else "blocked", finished_at=stamp()
            )
        save()
        raise CandidateError("repair_error", report["error"]["message"]) from exc
