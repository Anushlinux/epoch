"""Protected verification programs. Generated artifacts cannot edit these checks."""

import copy
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path

from epoch_backend import hermes_bridge
from epoch_backend.candidate_runner import RUNNER_VERSION, CandidateError, CandidateRunner
from epoch_backend.sandbox import Sandbox
from epoch_backend.sandbox_adapters import validate_checklist_payload
from epoch_backend.supervisor import BASELINE_KEYS


def clone_sandbox(source: Sandbox, target: Path) -> Sandbox:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise CandidateError("verification_conflict", "Verification destination already exists.")
    with closing(sqlite3.connect(source.path)) as origin, closing(sqlite3.connect(target)) as dest:
        origin.backup(dest)
    return Sandbox(target, source.task_id, source.run_id)


def isolation_proof(image_id: str, cancelled: threading.Event, budget=None) -> dict:
    """Actual adversarial probes in the exact production runner; no host mount."""
    source = """import os, socket
def serialize_checklist(**arguments):
    results = {"nonroot": os.getuid() != 0, "credentials_absent": not any(
        name in os.environ for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"))}
    try:
        open("/etc/epoch-forbidden", "w").write("x")
        results["root_write_denied"] = False
    except OSError:
        results["root_write_denied"] = True
    results["host_and_docker_absent"] = not any(os.path.exists(p) for p in (
        "/var/run/docker.sock", "/host", "/workspace", "/run/desktop/mnt/host"))
    s = socket.socket(); s.settimeout(0.2)
    try:
        s.connect(("1.1.1.1", 443)); results["network_denied"] = False
    except OSError:
        results["network_denied"] = True
    finally:
        s.close()
    with open("/proc/self/status") as f:
        status = f.read()
    results["no_new_privileges"] = "NoNewPrivs:\\t1" in status
    results["no_capabilities"] = "CapEff:\\t0000000000000000" in status
    return results
"""
    checks = CandidateRunner(image_id).run(
        source,
        {},
        cancelled=cancelled,
        timeout=min(12, budget.remaining_seconds()) if budget else 12,
    )
    return {
        "kind": "isolation",
        "passed": bool(checks) and all(v is True for v in checks.values()),
        "checks": checks,
        "image_id": image_id,
        "runner_version": RUNNER_VERSION,
    }


def component_proofs(version: dict, cancelled: threading.Event, budget=None) -> list[dict]:
    runner = CandidateRunner(version["image_id"])
    cases = [
        {
            "ticket_id": "t-one",
            "title": "Release checklist 2.4",
            "items": ["Smoke test", "Rollback"],
        },
        {
            "ticket_id": "t-unicode",
            "title": "Release λ / हिन्दी",
            "items": ["安全", 'Quote "x"', "Line\nTwo"],
        },
        {"ticket_id": "t-max", "title": "Maximum list", "items": [f"Check {i}" for i in range(50)]},
    ]
    outcomes = []
    for index, case in enumerate(cases):
        for legacy in (True, False):
            try:
                result = runner.run(
                    version["source"],
                    {**case, "legacy": legacy},
                    cancelled=cancelled,
                    timeout=min(12, budget.remaining_seconds()) if budget else 12,
                )
                value = validate_checklist_payload(result)
                passed = value == case
                error = None
            except (CandidateError, ValueError) as exc:
                if isinstance(exc, CandidateError) and exc.code in {
                    "cleanup_unresolved",
                    "runner_unavailable",
                    "isolation_unverified",
                    "cancelled",
                }:
                    raise
                passed, error = False, str(exc)
            outcomes.append({"case": index, "legacy": legacy, "passed": passed, "error": error})
    return [
        {
            "kind": "component",
            "passed": all(o["passed"] for o in outcomes if o["legacy"]),
            "cases": [o for o in outcomes if o["legacy"]],
            "artifact_sha256": version["artifact_sha256"],
        },
        {
            "kind": "regression",
            "passed": all(o["passed"] for o in outcomes if not o["legacy"]),
            "cases": [o for o in outcomes if not o["legacy"]],
            "artifact_sha256": version["artifact_sha256"],
        },
    ]


def run_verification(
    kind: str,
    sandbox: Sandbox,
    instruction: str,
    reference: dict,
    budget,
    record_progress,
    cancelled: threading.Event,
) -> dict:
    result = {
        "kind": kind,
        "passed": False,
        "turns_used": 0,
        "run_id": sandbox.run_id,
        "database": str(sandbox.path),
        "criteria_before": copy.deepcopy(sandbox.metadata()),
        "state_before": sandbox.snapshot(),
        "instruction": instruction,
    }

    def on_turn(actor, used):
        result["turns_used"] = used
        record_progress(result)

    with budget.verification_stage(on_turn) as stage:
        request = {
            "task_id": sandbox.task_id,
            "run_id": sandbox.run_id,
            "brief": instruction,
            "work_dir": str(sandbox.path.parent / "hermes"),
            "mcp_command": sys.executable,
            "mcp_args": [
                "-m",
                "epoch_backend.mcp_server",
                "--database",
                str(sandbox.path),
                "--task-id",
                sandbox.task_id,
                "--run-id",
                sandbox.run_id,
            ],
            "max_turns": stage.remaining_turns(),
            "timeout_seconds": stage.remaining_seconds(),
        }
        with hermes_bridge.Session(
            request,
            lambda e: sandbox.record_event(e.get("type", "executor.event"), e.get("data", {})),
            cancelled,
            before_model_request=lambda: stage.consume("executor"),
        ) as session:
            outcome = session.run(
                instruction,
                max_turns=stage.remaining_turns(),
                timeout_seconds=stage.remaining_seconds(),
            )
        result["executor"] = outcome
        stage.check()
        verification = sandbox.evaluate()
        result.update(
            verification=verification,
            state_after=sandbox.snapshot(),
            criteria_after=copy.deepcopy(sandbox.metadata()),
        )
        baseline = outcome.get("baseline", {})
        invariants = all(
            baseline.get(key) and baseline.get(key) == reference.get(key) for key in BASELINE_KEYS
        )
        invariants = invariants and all(
            baseline.get(key) is True
            for key in (
                "implementation_unchanged",
                "user_settings_unchanged",
                "system_prompt_unchanged",
                "system_prompt_static_unchanged",
                "discovery_unchanged",
            )
        )
        after = sandbox.snapshot()
        result["effects_unique_and_retained"] = all(
            len(after[key]) == 1
            and all(
                old["id"] in {new["id"] for new in after[key]}
                for old in result["state_before"][key]
            )
            for key in ("tickets", "checklists", "messages")
        )
        result["executor_invariants_match"] = invariants
        result["criteria_unchanged"] = result["criteria_before"] == result["criteria_after"]
        result["passed"] = bool(
            outcome.get("success")
            and outcome.get("history_retained")
            and not outcome.get("missing_evidence")
            and invariants
            and result["criteria_unchanged"]
            and verification["passed"]
            and result["effects_unique_and_retained"]
        )
        result["events"] = sandbox.events()
    record_progress(result)
    return result
