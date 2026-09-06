"""Host-controlled CSV mapping repair; candidates are data, never executable code."""

import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from pydantic import StringConstraints

from epoch_backend import hermes_bridge
from epoch_backend.contracts import Contract
from epoch_backend.csv_sandbox import SAMPLE_CSV, CsvSandbox, _adapter, _parse_csv
from epoch_backend.incident_contracts import IncidentAnswer

Column = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,39}$")]
BASELINE_KEYS = (
    "implementation_sha256",
    "model_configuration_sha256",
    "discovery_sha256",
    "system_prompt_static_sha256",
    "user_settings_sha256",
    "bridge_sha256",
)


class CsvMapping(Contract):
    name_field: Column
    email_field: Column


class CsvAnswer(IncidentAnswer):
    repair: CsvMapping | None


def executor_request(sandbox, brief, history, work_dir):
    return {
        "task_id": sandbox.task_id,
        "run_id": sandbox.run_id,
        "brief": brief,
        "visible_history": history,
        "work_dir": str(work_dir),
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
            "--environment",
            "csv_import",
        ],
        "timeout_seconds": 300,
        "max_turns": 20,
    }


class CsvRepairs:
    def __init__(self, data_dir):
        self.root = Path(data_dir) / "csv-repairs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "versions.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS versions (id TEXT PRIMARY KEY, record TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS active (project TEXT PRIMARY KEY, id TEXT)")

    def save(self, record):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "INSERT INTO versions VALUES (?,?) ON CONFLICT(id) "
                "DO UPDATE SET record=excluded.record",
                (record["version"], json.dumps(record, sort_keys=True)),
            )

    def active(self, project):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute(
                "SELECT record FROM versions JOIN active ON versions.id=active.id WHERE project=?",
                (project,),
            ).fetchone()
        if not row:
            return None
        value = json.loads(row[0])
        if value["status"] != "published" or value["project"] != project:
            raise ValueError("Invalid published CSV repair")
        mapping = CsvMapping.model_validate(value["mapping"]).model_dump()
        if (
            hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()
            != value["sha256"]
        ):
            raise ValueError("CSV repair artifact hash mismatch")
        return {"version": value["version"], "mapping": mapping, "sha256": value["sha256"]}

    def rollback(self, project):
        """Host maintenance only, under the execution lock at an idle boundary."""
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT record FROM versions JOIN active ON versions.id=active.id WHERE project=?",
                (project,),
            ).fetchone()
            if row:
                record = json.loads(row[0])
                previous = record["previous_version"]
                db.execute("DELETE FROM active WHERE project=?", (project,))
                if previous:
                    db.execute("INSERT INTO active VALUES (?,?)", (project, previous))
        return self.active(project)

    def eligible(self, sandbox):
        return self.availability(sandbox).get("failure_id")

    def availability(self, sandbox):
        def blocked(reason):
            return {"supported": True, "eligible": False, "reason": reason, "failure_id": None}

        metadata = sandbox.metadata()
        if metadata["adapter_mode"] != "broken":
            return blocked("The healthy control does not need a repair.")
        if metadata.get("repair"):
            return blocked("A verified mapping is already active. Check the recovery result below.")
        snapshot = sandbox.snapshot()
        if snapshot["customers"]:
            return blocked("Customers are already saved. Review existing effects before repairing.")
        events = sandbox.events()
        failures = [e for e in events if e["type"] == "tool.service_error"]
        if not failures:
            return blocked("Run the sample import first so the debugger has a captured failure.")
        failure = failures[-1]
        if failure["payload"].get("error", {}).get("code") != "missing_email":
            return blocked("This service failure is outside the supported CSV mapping repair.")
        identity = failure["payload"]["id"]
        inputs = [
            e
            for e in events
            if e["type"] == "tool.import_input" and e["payload"]["import_id"] == identity
        ]
        if not inputs or _parse_csv(inputs[-1]["payload"]["csv_text"]) != _parse_csv(SAMPLE_CSV):
            return blocked("This repair requires the supplied sample customers, unchanged.")
        attempts = sum(
            e["type"] == "csv.repair_attempt" and e["payload"].get("failure_id") == failure["id"]
            for e in events
        )
        if attempts >= 2:
            return blocked(
                "Both repair attempts for this failure were used. Review their results below."
            )
        return {
            "supported": True,
            "eligible": True,
            "reason": "The first candidate was rejected. One verified retry remains."
            if attempts
            else None,
            "failure_id": failure["id"],
            "attempts_remaining": 2 - attempts,
        }

    def repair_evidence(self, sandbox, failure_id):
        """Bounded source/contract evidence and prior rejected checks, not repair instructions."""
        events = sandbox.events()
        failure = next(e for e in events if e["id"] == failure_id)
        identity = failure["payload"]["id"]
        source = next(
            e
            for e in events
            if e["type"] == "tool.import_input" and e["payload"]["import_id"] == identity
        )
        rejected = [
            e
            for e in events
            if e["type"] == "csv.repair_result" and e["payload"].get("failure_id") == failure_id
        ][-2:]
        return [
            {"id": source["id"], "type": "csv.source", "csv_text": source["payload"]["csv_text"]},
            {
                "id": failure_id,
                "type": "csv.service_contract",
                "required_outgoing_fields": failure["payload"]["expected_fields"],
                "rejected_outgoing_customers": failure["payload"]["outgoing_customers"],
            },
            *[
                {
                    "id": e["id"],
                    "type": "csv.rejected_candidate",
                    "mapping": e["payload"]["mapping"],
                    "checks": [
                        {"name": c["name"], "passed": c["passed"]} for c in e["payload"]["checks"]
                    ],
                    "error": e["payload"].get("error"),
                }
                for e in rejected
            ],
        ]

    def _sandbox(self, path, project, artifact):
        identity = str(uuid4())
        sandbox = CsvSandbox(path, identity, identity)
        sandbox.initialize(project_id=project)
        sandbox.select_repair(artifact)
        return sandbox

    def _component_checks(self, directory, project, artifact):
        sandbox = self._sandbox(directory / "component.sqlite3", project, artifact)
        checks = []
        # Expectations come from fixed host-owned inputs, never from the candidate.
        for label, source in (
            ("original", SAMPLE_CSV),
            ("fresh", 'name,email\n"New, Customer",new@example.test\nZoë,zoe@example.test\n'),
        ):
            rows = _parse_csv(source)
            checks.append(
                {"name": label + "_mapping", "passed": _adapter(rows, "broken", artifact) == rows}
            )
        imported = sandbox.import_customers(SAMPLE_CSV, "component")
        checks.append(
            {"name": "original_state", "passed": sandbox.snapshot()["verification"]["passed"]}
        )
        checks.append(
            {
                "name": "exact_retry",
                "passed": sandbox.import_customers(SAMPLE_CSV, "component") == imported,
            }
        )
        second = sandbox.import_customers(SAMPLE_CSV, "second")
        checks.append({"name": "deduplication", "passed": second["created_count"] == 0})
        before = sandbox.list_customers()
        rejected = sandbox.import_customers(
            "name,email\nValid,v@example.test\nInvalid,\n", "invalid"
        )
        checks.append(
            {
                "name": "invalid_atomic",
                "passed": rejected["status"] == "rejected" and sandbox.list_customers() == before,
            }
        )
        # A healthy control stays independent of the candidate.
        checks.append(
            {
                "name": "healthy_control",
                "passed": _adapter(_parse_csv(SAMPLE_CSV), "healthy") == _parse_csv(SAMPLE_CSV),
            }
        )
        return checks

    def verify_publish(self, sandbox, mapping, failure_id, original, cancel, progress):
        if self.eligible(sandbox) != failure_id:
            raise ValueError("CSV repair attempts exhausted or failure no longer eligible")
        project = sandbox.metadata()["project_id"]
        mapping = CsvMapping.model_validate(mapping).model_dump()
        version = str(uuid4())
        artifact = {
            "version": version,
            "mapping": mapping,
            "sha256": hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest(),
        }
        active = self.active(project)
        record = {
            **artifact,
            "project": project,
            "status": "staged",
            "checks": [],
            "source_chat_id": sandbox.task_id,
            "failure_id": failure_id,
            "previous_version": active["version"] if active else None,
            "original_request": original,
        }
        self.save(record)
        sandbox.record_event("csv.repair_attempt", {"failure_id": failure_id, "version": version})
        directory = self.root / version
        directory.mkdir()
        try:
            if cancel.is_set():
                raise ValueError("Repair cancelled")
            progress("Checking the candidate mapping")
            record["checks"] = self._component_checks(directory, project, artifact)
            self.save(record)
            if not all(check["passed"] for check in record["checks"]):
                raise ValueError("Candidate failed component checks")
            baselines = [e["payload"] for e in sandbox.events() if e["type"] == "executor.baseline"]
            baseline = baselines[-1] if baselines else {}
            if not all(key in baseline for key in BASELINE_KEYS):
                raise ValueError(
                    "Original Hermes baseline is missing; cannot verify fixed executor"
                )
            record["baseline"] = {key: baseline[key] for key in BASELINE_KEYS}
            for label in ("original", "fresh"):
                if cancel.is_set():
                    raise ValueError("Repair cancelled")
                stage = self._sandbox(directory / f"{label}.sqlite3", project, artifact)
                if label == "original":
                    brief, history = original["brief"], original["history"]
                    expected = _parse_csv(SAMPLE_CSV)
                else:
                    source = 'name,email\n"New, Customer",new@example.test\nZoë,zoe@example.test\n'
                    expected = _parse_csv(source)
                    brief = (
                        "Import this CSV into the simulated customer service. Preserve both "
                        "customers exactly, avoid duplicates, and list the saved customers.\n"
                        + source
                    )
                    history = []
                progress(f"Hermes is verifying the {label} task in isolated state")
                result = hermes_bridge.execute(
                    executor_request(stage, brief, history, directory / label / "hermes"),
                    lambda event, target=stage: target.record_event(
                        event.get("type", "executor.event"), event.get("data", {})
                    ),
                    cancel,
                )
                actual = [{"name": c["name"], "email": c["email"]} for c in stage.list_customers()]
                passed = (
                    result.get("success") is True
                    and not cancel.is_set()
                    and sorted(actual, key=lambda c: c["email"])
                    == sorted(expected, key=lambda c: c["email"])
                    and stage.metadata()["repair"] == artifact
                    and stage.metadata()["criteria"] == sandbox.metadata()["criteria"]
                    and all(
                        result.get("baseline", {}).get(key) == baseline[key]
                        for key in BASELINE_KEYS
                    )
                )
                record["checks"].append(
                    {
                        "name": label + "_hermes",
                        "passed": passed,
                        "result": result,
                        "database": str(stage.path),
                    }
                )
                self.save(record)
                if not passed:
                    raise ValueError(f"Hermes {label} verification failed")
            if cancel.is_set() or self.active(project) != active:
                raise ValueError("Repair cancelled or active version changed")
            record["status"] = "published"
            # The exact verified mapping and the active pointer commit together.
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute("UPDATE versions SET record=? WHERE id=?", (json.dumps(record), version))
                db.execute(
                    "INSERT INTO active VALUES (?,?) ON CONFLICT(project) "
                    "DO UPDATE SET id=excluded.id",
                    (project, version),
                )
        except Exception as exc:
            record["status"] = "cancelled" if cancel.is_set() else "rejected"
            record["error"] = str(exc)
            self.save(record)
        sandbox.record_event("csv.repair_result", record)
        return record
