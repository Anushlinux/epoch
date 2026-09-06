"""Isolated customer CSV simulation with an executable adapter defect and trusted checks.

This environment has no release tools or network access. Only the host repair
controller can install a verified, declarative mapping; business tools cannot.
"""

import csv
import hashlib
import io
import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from epoch_backend.sandbox import SandboxError

SAMPLE_CSV = (
    "name,email\nAsha,asha@example.test\nRavi,ravi@example.test\nMeera,meera@example.test\n"
)
SAMPLE_PROMPT = (
    "Import the supplied customer CSV into the simulated customer service. "
    "Preserve each customer's name and email, create exactly three customers without "
    "duplicates, and confirm the saved customers by listing them."
)
EXPECTED_CUSTOMERS = (
    {"name": "Asha", "email": "asha@example.test"},
    {"name": "Ravi", "email": "ravi@example.test"},
    {"name": "Meera", "email": "meera@example.test"},
)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _criteria():
    return {
        "evaluator_version": "customer-csv-v1",
        "source_id": "builtin-customer-csv-v1",
        "source_sha256": hashlib.sha256(SAMPLE_CSV.encode()).hexdigest(),
        "original_request": SAMPLE_PROMPT,
        "expected_customers": [dict(item) for item in EXPECTED_CUSTOMERS],
        "requirements": [
            "Save exactly the three supplied customers with their original names and emails.",
            "Do not create duplicate customers or partial writes after a rejected import.",
        ],
    }


def _parse_csv(csv_text):
    if not isinstance(csv_text, str) or not 1 <= len(csv_text) <= 12000:
        raise SandboxError("invalid_csv", "CSV must contain 1 to 12000 characters.")
    try:
        rows = list(csv.reader(io.StringIO(csv_text, newline=""), strict=True))
    except csv.Error as exc:
        raise SandboxError("invalid_csv", "CSV quoting is invalid.") from exc
    if not rows or rows[0] != ["name", "email"]:
        raise SandboxError("invalid_csv", "CSV header must be exactly name,email.")
    if not 1 <= len(rows) - 1 <= 50:
        raise SandboxError("invalid_csv", "CSV must contain between 1 and 50 customer rows.")
    parsed = []
    for index, row in enumerate(rows[1:], start=2):
        if len(row) != 2 or any(not value.strip() or value != value.strip() for value in row):
            raise SandboxError("invalid_csv", f"Row {index} requires a name and email.")
        name, email = row
        if (
            len(name) > 200
            or len(email) > 254
            or not re.fullmatch(r"[^\s@,]+@[^\s@,]+\.[^\s@,]+", email)
        ):
            raise SandboxError("invalid_csv", f"Row {index} has an invalid name or email.")
        parsed.append({"name": name, "email": email})
    return parsed


def _adapter(rows, mode, repair=None):
    """The intentional defect is a real field mapping, not a prerecorded error."""
    name_field = repair["mapping"]["name_field"] if repair else "name"
    email_field = (
        repair["mapping"]["email_field"]
        if repair
        else "emailAddress"
        if mode == "broken"
        else "email"
    )
    return [{name_field: row["name"], email_field: row["email"]} for row in rows]


def _service_validate(rows):
    for index, row in enumerate(rows, start=1):
        if "email" not in row:
            return {"code": "missing_email", "message": f"Customer {index}: email is required."}
        if set(row) != {"name", "email"}:
            return {"code": "invalid_customer_schema", "message": "Unexpected customer fields."}
    return None


class CsvSandbox:
    def __init__(self, path: Path, task_id: str, run_id: str):
        self.path = Path(path)
        self.task_id, self.run_id = str(task_id), str(run_id)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def _metadata(self, db):
        try:
            row = db.execute("SELECT record_json FROM csv_metadata WHERE id=1").fetchone()
        except sqlite3.OperationalError as exc:
            raise SandboxError(
                "sandbox_not_initialized", "Initialize the CSV environment first."
            ) from exc
        if row is None:
            raise SandboxError("sandbox_not_initialized", "Initialize the CSV environment first.")
        value = json.loads(row[0])
        if value["task_id"] != self.task_id or value["run_id"] != self.run_id:
            raise SandboxError(
                "sandbox_identity_mismatch", "CSV environment belongs to another task/run."
            )
        return value

    def metadata(self):
        with closing(self._connect()) as db:
            return self._metadata(db)

    def _event(self, db, event_type, payload):
        cursor = db.execute("INSERT INTO csv_events(record_json) VALUES ('{}')")
        event = {
            "id": str(uuid4()),
            "sequence": cursor.lastrowid,
            "type": event_type,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "emitted_at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        db.execute(
            "UPDATE csv_events SET record_json=? WHERE sequence=?", (_json(event), cursor.lastrowid)
        )
        return event

    def record_event(self, event_type, payload):
        with closing(self._connect()) as db, db:
            self._metadata(db)
            return self._event(db, event_type, payload)

    def events(self, after=0):
        if type(after) is not int or after < 0:
            raise SandboxError("invalid_arguments", "Event sequence must be nonnegative.")
        with closing(self._connect()) as db:
            self._metadata(db)
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT record_json FROM csv_events WHERE sequence>? ORDER BY sequence",
                    (after,),
                )
            ]

    def initialize(self, project_id="demo", adapter_mode="broken"):
        if adapter_mode not in {"broken", "healthy"}:
            raise SandboxError("invalid_adapter_mode", "Adapter mode must be broken or healthy.")
        if not isinstance(project_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", project_id
        ):
            raise SandboxError("invalid_project", "Project must be a simple slug.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 101):
                raise SandboxError("unsupported_schema", "This is not a CSV environment database.")
            if version == 0:
                if db.execute(
                    "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                ).fetchone():
                    raise SandboxError("invalid_database", "Refusing an unrelated database.")
                db.execute(
                    "CREATE TABLE csv_metadata(id INTEGER PRIMARY KEY, record_json TEXT NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE csv_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "record_json TEXT NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE csv_customers(email_key TEXT PRIMARY KEY, "
                    "record_json TEXT NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE csv_imports(id TEXT PRIMARY KEY, "
                    "request_key TEXT UNIQUE NOT NULL, "
                    "csv_text TEXT NOT NULL, record_json TEXT NOT NULL)"
                )
                metadata = {
                    "environment": "csv_import",
                    "project_id": project_id,
                    "simulated": True,
                    "adapter_mode": adapter_mode,
                    "task_id": self.task_id,
                    "run_id": self.run_id,
                    "source_csv": SAMPLE_CSV,
                    "criteria": _criteria(),
                }
                db.execute("INSERT INTO csv_metadata VALUES(1,?)", (_json(metadata),))
                db.execute("PRAGMA user_version=101")
                self._event(
                    db,
                    "sandbox.initialized",
                    {"environment": "csv_import", "adapter_mode": adapter_mode},
                )
                self._event(
                    db,
                    "context.source",
                    {"source_id": "builtin-customer-csv-v1", "csv_text": SAMPLE_CSV},
                )
                self._event(db, "criteria.recorded", {"trusted": True, **_criteria()})
            metadata = self._metadata(db)
            if metadata["project_id"] != project_id or metadata["adapter_mode"] != adapter_mode:
                raise SandboxError(
                    "sandbox_configuration_mismatch", "Existing CSV mode and project cannot change."
                )
            return metadata

    def read_sample(self):
        metadata = self.metadata()
        return {
            "simulated": True,
            "source_id": "builtin-customer-csv-v1",
            "csv_text": metadata["source_csv"],
        }

    def select_repair(self, repair):
        """Host-only selection at an idle boundary, never an executor tool."""
        from epoch_backend.csv_repair import CsvMapping

        if repair is not None:
            CsvMapping.model_validate(repair["mapping"])
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(db)
            if metadata.get("repair") == repair:
                return
            if metadata["adapter_mode"] != "broken":
                raise SandboxError("repair_scope", "Healthy controls cannot select repairs.")
            metadata["repair"] = repair
            db.execute("UPDATE csv_metadata SET record_json=? WHERE id=1", (_json(metadata),))
            self._event(db, "environment.repair_selected", {"repair": repair})

    def list_customers(self):
        with closing(self._connect()) as db:
            self._metadata(db)
            return [
                json.loads(row[0])
                for row in db.execute("SELECT record_json FROM csv_customers ORDER BY email_key")
            ]

    def get_import_status(self, import_id):
        with closing(self._connect()) as db:
            self._metadata(db)
            row = db.execute(
                "SELECT record_json FROM csv_imports WHERE id=?", (str(import_id),)
            ).fetchone()
        if row is None:
            raise SandboxError(
                "import_not_found", "No import with that ID exists in this environment."
            )
        return json.loads(row[0])

    def import_customers(self, csv_text, idempotency_key):
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key.strip()) <= 200:
            raise SandboxError("invalid_arguments", "A nonblank idempotency key is required.")
        if not isinstance(csv_text, str) or not 1 <= len(csv_text) <= 12000:
            raise SandboxError("invalid_csv", "CSV must contain 1 to 12000 characters.")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(db)
            previous = db.execute(
                "SELECT csv_text,record_json FROM csv_imports WHERE request_key=?",
                (idempotency_key,),
            ).fetchone()
            if previous:
                if previous["csv_text"] != csv_text:
                    raise SandboxError(
                        "idempotency_conflict",
                        "This key was already used for different CSV content.",
                    )
                self._event(
                    db,
                    "tool.import_reused",
                    {"import_id": json.loads(previous["record_json"])["id"]},
                )
                return json.loads(previous["record_json"])
            identity = str(uuid4())
            before = db.execute("SELECT COUNT(*) FROM csv_customers").fetchone()[0]
            self._event(
                db,
                "tool.import_input",
                {"import_id": identity, "csv_text": csv_text, "idempotency_key": idempotency_key},
            )
            error_stage = "csv_validation"
            try:
                parsed = _parse_csv(csv_text)
                wire = _adapter(parsed, metadata["adapter_mode"], metadata.get("repair"))
                self._event(db, "tool.adapter_output", {"import_id": identity, "customers": wire})
                error_stage = "service"
                error = _service_validate(wire)
            except SandboxError as exc:
                wire = []
                error = {"code": exc.code, "message": exc.message}
            inserted = 0
            if error is None:
                # Validate the full batch first. A rejected row cannot leave partial customers.
                for customer in wire:
                    key = customer["email"].casefold()
                    if not db.execute(
                        "SELECT 1 FROM csv_customers WHERE email_key=?", (key,)
                    ).fetchone():
                        record = {"id": str(uuid4()), "simulated": True, **customer}
                        db.execute("INSERT INTO csv_customers VALUES(?,?)", (key, _json(record)))
                        inserted += 1
            result = {
                "id": identity,
                "simulated": True,
                "status": "rejected" if error else "completed",
                "created_count": inserted,
                "customer_count_before": before,
                "customer_count_after": before + inserted,
                "input_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
                "error": error,
                "environment_version": metadata.get("repair", {}).get("version", "customer-csv-v1")
                if metadata.get("repair")
                else "customer-csv-v1",
            }
            db.execute(
                "INSERT INTO csv_imports VALUES(?,?,?,?)",
                (identity, idempotency_key, csv_text, _json(result)),
            )
            self._event(
                db,
                f"tool.{error_stage}_error" if error else "tool.service_result",
                {**result, "outgoing_customers": wire, "expected_fields": ["name", "email"]},
            )
            self._event(
                db, "state.observed", {"import_id": identity, "customer_count": before + inserted}
            )
            return result

    def snapshot(self):
        with closing(self._connect()) as db, db:
            db.execute("BEGIN")
            metadata = self._metadata(db)
            customers = [
                json.loads(row[0])
                for row in db.execute("SELECT record_json FROM csv_customers ORDER BY email_key")
            ]
            imports = [
                json.loads(row[0])
                for row in db.execute("SELECT record_json FROM csv_imports ORDER BY rowid")
            ]
            events = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT record_json FROM csv_events ORDER BY sequence DESC LIMIT 30"
                )
            ][::-1]
            event_count = db.execute("SELECT COUNT(*) FROM csv_events").fetchone()[0]
        actual = sorted((item["name"], item["email"]) for item in customers)
        expected = sorted(
            (item["name"], item["email"]) for item in metadata["criteria"]["expected_customers"]
        )
        checks = [
            {
                "name": "source_customers_saved",
                "passed": actual == expected,
                "expected_count": 3,
                "actual_count": len(customers),
            },
            {
                "name": "no_duplicate_emails",
                "passed": len({item["email"].casefold() for item in customers}) == len(customers),
            },
            {
                "name": "rejected_imports_atomic",
                "passed": all(
                    item["created_count"] == 0
                    and item["customer_count_before"] == item["customer_count_after"]
                    for item in imports
                    if item["status"] == "rejected"
                ),
            },
        ]
        return {
            "simulated": True,
            "environment": "csv_import",
            "adapter_mode": metadata["adapter_mode"],
            "repair": metadata.get("repair"),
            "customers": customers,
            "imports": imports[-20:],
            "imports_total": len(imports),
            "sample_csv": metadata["source_csv"],
            "expected_count": 3,
            "events": events,
            "events_total": event_count,
            "criteria": metadata["criteria"],
            "verification": {
                "evaluator_version": "customer-csv-v1",
                "passed": all(item["passed"] for item in checks),
                "checks": checks,
            },
        }


class _Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _ImportArguments(_Arguments):
    csv_text: str = Field(min_length=1, max_length=12000)
    idempotency_key: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]


class _StatusArguments(_Arguments):
    import_id: str = Field(min_length=1, max_length=100)


_TOOLS = {
    "customers.read_sample": (
        _Arguments,
        "read_sample",
        "Read the supplied customer CSV source.",
        True,
    ),
    "customers.import": (
        _ImportArguments,
        "import_customers",
        "Import CSV with exactly name,email columns into the simulated customer service. "
        "Reuse a key only for identical retries. Inspect status and saved customers.",
        False,
    ),
    "customers.list": (
        _Arguments,
        "list_customers",
        "List customers actually saved in this environment.",
        True,
    ),
    "customers.get_import_status": (
        _StatusArguments,
        "get_import_status",
        "Inspect a prior import's status, counts and any service error.",
        True,
    ),
}


class CsvRegistry:
    def __init__(self, sandbox: CsvSandbox):
        self.sandbox = sandbox
        sandbox.metadata()

    def _summary(self, name):
        definition = _TOOLS[name]
        repair = self.sandbox.metadata().get("repair")
        description = definition[2]
        if name == "customers.import" and repair:
            mapping = repair["mapping"]
            description += (
                f" Active mapping: CSV name -> service {mapping['name_field']}; "
                f"CSV email -> service {mapping['email_field']}. "
                "Rejected import keys keep their original receipts. "
                "Use a new key to retry an import after an environment repair."
            )
        return {
            "name": name,
            "description": description,
            "read_only": definition[3],
            "version": repair["version"] if repair else "customer-csv-v1",
        }

    def discover_tools(self):
        result = {
            "interface_version": "epoch-tools-v1",
            "simulated": True,
            "project_id": self.sandbox.metadata()["project_id"],
            "tools": [self._summary(name) for name in _TOOLS],
        }
        self.sandbox.record_event("tool.discovery", {"result": result})
        return {"ok": True, "result": result}

    def _error(self, name, code, message):
        error = {"code": code, "message": message}
        self.sandbox.record_event("tool.error", {"tool_name": name, "error": error})
        return {"ok": False, "error": error}

    def describe_tool(self, name):
        if name not in _TOOLS:
            return self._error(name, "tool_not_found", "The requested tool is unavailable.")
        result = {**self._summary(name), "input_schema": _TOOLS[name][0].model_json_schema()}
        self.sandbox.record_event("tool.described", {"tool_name": name, "result": result})
        return {"ok": True, "result": result}

    def invoke_tool(self, name, arguments):
        if not isinstance(name, str) or name not in _TOOLS:
            return self._error(str(name), "tool_not_found", "The requested tool is unavailable.")
        model, operation, _, _ = _TOOLS[name]
        try:
            validated = model.model_validate(arguments)
        except ValidationError:
            return self._error(
                name, "invalid_arguments", "Arguments must match the published schema."
            )
        self.sandbox.record_event(
            "tool.called", {"tool_name": name, "arguments": validated.model_dump()}
        )
        try:
            result = getattr(self.sandbox, operation)(**validated.model_dump())
        except SandboxError as exc:
            return self._error(name, exc.code, exc.message)
        self.sandbox.record_event("tool.result", {"tool_name": name, "result": result})
        return {"ok": True, "result": result}
