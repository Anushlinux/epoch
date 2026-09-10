"""Durable, per-run simulated services and administrative inspection.

Only the business operations in the tool registry are executor-callable. Setup,
reset, criteria and evaluation are developer functions, not business tools.
"""

import json
import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from epoch_backend.sandbox_adapters import (
    AdapterContractError,
    serialize_checklist,
    validate_checklist_payload,
)
from epoch_backend.trusted_checks import (
    EVALUATOR_VERSION,
    criteria_from_metadata,
    evaluate_release,
    release_criteria,
)

TOOL_NAMES = (
    "tickets.create",
    "tickets.list",
    "checklists.create",
    "checklists.update",
    "checklists.list",
    "messages.send",
    "messages.update",
    "messages.list",
    "runbooks.read",
    "directory.read",
)
SCENARIOS = ("control", "broken_checklist", "missing_lookup", "outdated_context")


class SandboxError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value: str, name: str, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise SandboxError(
            "invalid_arguments", f"{name} must be nonblank text up to {maximum} characters."
        )
    return value.strip()


class Sandbox:
    def __init__(self, path: Path | str, task_id: str, run_id: str):
        self.path = Path(path)
        self.task_id = _text(str(task_id), "task_id")
        self.run_id = _text(str(run_id), "run_id")

    def _connect(self, *, create: bool = False) -> sqlite3.Connection:
        if not create and not self.path.is_file():
            raise SandboxError("sandbox_not_initialized", "Initialize this sandbox before use.")
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        return connection

    def _metadata(self, connection: sqlite3.Connection) -> dict:
        try:
            row = connection.execute(
                "SELECT record_json FROM sandbox_metadata WHERE id=1"
            ).fetchone()
        except sqlite3.OperationalError as error:
            raise SandboxError(
                "sandbox_not_initialized", "Initialize this sandbox before use."
            ) from error
        if row is None:
            raise SandboxError("sandbox_not_initialized", "Initialize this sandbox before use.")
        value = json.loads(row[0])
        if value["task_id"] != self.task_id or value["run_id"] != self.run_id:
            raise SandboxError(
                "sandbox_identity_mismatch", "Sandbox belongs to a different task/run."
            )
        return value

    def metadata(self) -> dict:
        with closing(self._connect()) as connection:
            return self._metadata(connection)

    def pin_context(self, policy, operation_id):
        with closing(self._connect()) as connection, connection:
            meta = self._metadata(connection)
            meta.update(context_policy=policy, operation_id=str(operation_id))
            connection.execute("UPDATE sandbox_metadata SET record_json=? WHERE id=1", (_json(meta),))

    def select_environment(self, manifest: dict, *, expected_version: str | None = None):
        """Host-only version activation. Executors cannot call this through MCP."""
        from epoch_backend.candidate_runner import RUNNER_VERSION, digest
        from epoch_backend.repair_surfaces import artifacts

        artifacts(manifest)

        if manifest.get("version_id") != "builtin":
            if (
                manifest.get("project") != self.metadata()["project_id"]
                or manifest.get("runner_version") != RUNNER_VERSION
                or digest(manifest.get("source", "")) != manifest.get("artifact_sha256")
            ):
                raise SandboxError(
                    "environment_invalid", "Environment scope or artifact is invalid."
                )
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            previous = metadata.get("adapter_manifest", {}).get("version_id", "builtin")
            if expected_version is not None and expected_version != previous:
                raise SandboxError("version_conflict", "Pinned environment changed unexpectedly.")
            metadata["adapter_manifest"] = manifest
            connection.execute(
                "UPDATE sandbox_metadata SET record_json=? WHERE id=1", (_json(metadata),)
            )
            self._event(
                connection,
                "environment.selected",
                {
                    "previous": previous,
                    "version_id": manifest["version_id"],
                    "artifact_sha256": manifest.get("artifact_sha256"),
                },
            )

    @staticmethod
    def _serialize(metadata, ticket_id, title, items):
        manifest = metadata.get("adapter_manifest", {"version_id": "builtin"})
        args = {
            "ticket_id": ticket_id,
            "title": title,
            "items": items,
            "legacy": metadata["scenario"] == "broken_checklist",
        }
        from epoch_backend.repair_surfaces import SERIALIZER, artifacts, invoke
        from epoch_backend.candidate_runner import CandidateError

        artifact = artifacts(manifest).get(SERIALIZER)
        if artifact is None:
            return serialize_checklist(**args)
        try:
            wire = invoke(artifact, SERIALIZER, args)
        except CandidateError as error:
            raise SandboxError(error.code, error.message) from error
        # Generated code never owns service selection, object identity or grants.
        if wire.get("ticket_id") != ticket_id or wire.get("title") != title:
            raise SandboxError(
                "adapter_scope_violation", "Adapter changed the authorized object identity."
            )
        return wire

    def initialize(
        self,
        scenario: str = "control",
        project_id: str = "demo",
        release: str = "1.0",
        grants: list[str] | None = None,
    ) -> dict:
        return self._setup(scenario, project_id, release, grants, reset=False)

    def reset(
        self,
        scenario: str | None = None,
        project_id: str | None = None,
        release: str | None = None,
        grants: list[str] | None = None,
    ) -> dict:
        """Explicit reset preserves existing setup by default and retains evidence."""
        previous = self.metadata()
        return self._setup(
            previous["scenario"] if scenario is None else scenario,
            previous["project_id"] if project_id is None else project_id,
            previous["release"] if release is None else release,
            previous["grants"] if grants is None else grants,
            reset=True,
        )

    def _setup(self, scenario: str, project_id: str, release: str, grants, *, reset: bool) -> dict:
        if scenario not in SCENARIOS:
            raise SandboxError("invalid_scenario", "Unknown sandbox scenario.")
        project_id = _text(project_id, "project_id", 100)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", project_id):
            raise SandboxError("invalid_arguments", "project_id must be a simple project slug.")
        release = _text(release, "release", 100)
        granted = list(TOOL_NAMES) if grants is None else grants
        if not isinstance(granted, (list, tuple)) or any(
            name not in TOOL_NAMES for name in granted
        ):
            raise SandboxError("invalid_grants", "Grants must contain only known sandbox tools.")
        granted = sorted(set(granted))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect(create=True)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise SandboxError("unsupported_schema", "Unsupported sandbox schema version.")
            if version == 0:
                existing = connection.execute(
                    "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                ).fetchone()
                if existing:
                    raise SandboxError(
                        "invalid_database", "Refusing a nonempty unrelated database."
                    )
                for sql in (
                    "CREATE TABLE sandbox_metadata (id INTEGER PRIMARY KEY, "
                    "record_json TEXT NOT NULL)",
                    "CREATE TABLE sandbox_objects (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, record_json TEXT NOT NULL)",
                    "CREATE TABLE sandbox_receipts (operation TEXT NOT NULL, key TEXT NOT NULL, "
                    "arguments TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(operation,key))",
                    "CREATE TABLE sandbox_events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "id TEXT NOT NULL UNIQUE, record_json TEXT NOT NULL)",
                ):
                    connection.execute(sql)
                connection.execute("PRAGMA user_version=1")
            old = connection.execute(
                "SELECT record_json FROM sandbox_metadata WHERE id=1"
            ).fetchone()
            previous = self._metadata(connection) if old else None
            if previous and not reset:
                settings = {
                    "scenario": scenario,
                    "project_id": project_id,
                    "release": release,
                    "grants": previous["grants"] if grants is None else granted,
                }
                if any(previous[key] != value for key, value in settings.items()):
                    raise SandboxError(
                        "setup_conflict", "Existing setup differs; use explicit reset."
                    )
                return previous
            criteria = release_criteria(project_id, release, scenario)
            metadata = {
                "schema_version": 1,
                "simulated": True,
                "task_id": self.task_id,
                "run_id": self.run_id,
                "scenario": scenario,
                "project_id": project_id,
                "release": release,
                "grants": granted,
                "generation": previous["generation"] + 1 if previous else 1,
                "environment_version": "sandbox-v2",
                "context_rule_version": "runbook-selector-v1",
                "requirements_revisions": [],
                **criteria,
                "criteria_sha256": sha256(_json(criteria).encode()).hexdigest(),
            }
            connection.execute("DELETE FROM sandbox_objects")
            connection.execute("DELETE FROM sandbox_receipts")
            connection.execute(
                "INSERT OR REPLACE INTO sandbox_metadata VALUES (1,?)", (_json(metadata),)
            )
            self._seed(connection, metadata)
            self._event(
                connection,
                "sandbox.reset" if previous else "sandbox.initialized",
                {
                    "simulated": True,
                    "generation": metadata["generation"],
                    "project_id": project_id,
                    "environment_version": metadata["environment_version"],
                },
            )
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
        return metadata

    def revise_requirements(
        self,
        revision_id: str,
        additional_items: list[str],
        required_message_phrases: list[str],
        source_refs: list[dict],
    ) -> dict:
        """Host-only additive intent revision; business tools cannot edit criteria.

        The supervisor validates source authority before calling this method. The
        transaction retains exact criteria, provenance and the original retry result.
        Existing requirements, scope, grants and business objects cannot be removed.
        """
        revision_id = _text(revision_id, "revision_id", 200)

        def bounded_texts(values, name, maximum):
            if not isinstance(values, list) or len(values) > maximum:
                raise SandboxError(
                    "invalid_arguments", f"{name} must contain at most {maximum} strings."
                )
            return list(dict.fromkeys(_text(value, name, 500) for value in values))

        items = bounded_texts(additional_items, "additional_items", 50)
        phrases = bounded_texts(required_message_phrases, "required_message_phrases", 20)
        if (
            not isinstance(source_refs, list)
            or not 1 <= len(source_refs) <= 32
            or any(not isinstance(ref, dict) or not ref for ref in source_refs)
        ):
            raise SandboxError("invalid_arguments", "Supply 1 to 32 nonempty source references.")
        try:
            if any(len(_json(ref)) > 4000 for ref in source_refs):
                raise ValueError("Source reference too large.")
            sources = json.loads(_json(source_refs))
        except (TypeError, ValueError, RecursionError) as error:
            raise SandboxError(
                "invalid_arguments", "Source references must be bounded JSON objects."
            ) from error
        arguments = {
            "additional_items": items,
            "required_message_phrases": phrases,
            "source_refs": sources,
        }
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            receipt = connection.execute(
                "SELECT arguments,result FROM sandbox_receipts WHERE operation=? AND key=?",
                ("requirements.revise", revision_id),
            ).fetchone()
            if receipt:
                if receipt["arguments"] != _json(arguments):
                    raise SandboxError(
                        "revision_conflict", "Revision ID already used with different content."
                    )
                return json.loads(receipt["result"])
            history = metadata.get("requirements_revisions", [])
            if len(history) >= 50:
                raise SandboxError("revision_limit", "This run already has 50 intent revisions.")
            expected_items = list(dict.fromkeys([*metadata["expected_items"], *items]))
            expected_phrases = list(
                dict.fromkeys([*metadata.get("required_message_phrases", []), *phrases])
            )
            if len(expected_items) > 50 or len(expected_phrases) > 20:
                raise SandboxError(
                    "invalid_arguments", "Combined requirements exceed checklist or phrase limits."
                )
            before = criteria_from_metadata(metadata)
            after = {
                **before,
                "expected_items": expected_items,
                "required_message_phrases": expected_phrases,
                "evaluator_version": EVALUATOR_VERSION,
            }
            revision = {
                "revision_id": revision_id,
                **arguments,
                "before_criteria": before,
                "after_criteria": after,
                "before_sha256": metadata["criteria_sha256"],
                "after_sha256": sha256(_json(after).encode()).hexdigest(),
                "created_at": datetime.now(UTC).isoformat(),
            }
            result = {
                **metadata,
                **after,
                "criteria_sha256": revision["after_sha256"],
                "requirements_revisions": [*history, revision],
            }
            connection.execute(
                "UPDATE sandbox_metadata SET record_json=? WHERE id=1", (_json(result),)
            )
            connection.execute(
                "INSERT INTO sandbox_receipts VALUES (?,?,?,?)",
                ("requirements.revise", revision_id, _json(arguments), _json(result)),
            )
            self._event(
                connection,
                "requirements.revised",
                {"generation": metadata["generation"], "simulated": True, **revision},
            )
            return result

    def _seed(self, connection: sqlite3.Connection, metadata: dict) -> None:
        project = metadata["project_id"]
        self._insert_object(
            connection,
            "directory",
            {
                "id": f"directory-{project}-qa",
                "simulated": True,
                "project_id": project,
                "role": "QA owner",
                "name": metadata["qa_owner"],
                "channel": metadata["qa_channel"],
                "url": f"simulated://{self.run_id}/directory/{project}-qa",
            },
        )
        for version, current in (("v1", False), ("v2", True)):
            channel = metadata["qa_channel"] if current else f"#qa-{project}-legacy"
            content = (
                f"Release workflow for project {project}. Create the release ticket, attach a "
                "checklist, and notify QA with the ticket and checklist links. "
                f"Send the release notice to {channel}. Checklist items: "
                + "; ".join(metadata["expected_items"])
                + "."
            )
            if metadata["require_qa_owner"]:
                content += " Identify the current QA owner using the authorized directory record."
            self._insert_object(
                connection,
                "runbooks",
                {
                    "id": f"release-runbook-{project}-{version}",
                    "document_id": f"release-{project}",
                    "simulated": True,
                    "project_id": project,
                    "scope": f"project:{project}",
                    "version": version,
                    "is_current": current,
                    "content": content,
                    "url": f"simulated://{self.run_id}/runbooks/release-{project}/{version}",
                },
            )

    @staticmethod
    def _insert_object(connection: sqlite3.Connection, kind: str, value: dict) -> None:
        connection.execute(
            "INSERT INTO sandbox_objects(id,kind,record_json) VALUES (?,?,?)",
            (value["id"], kind, _json(value)),
        )

    @staticmethod
    def _objects(connection: sqlite3.Connection, kind: str) -> list[dict]:
        return [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT record_json FROM sandbox_objects WHERE kind=? ORDER BY sequence", (kind,)
            ).fetchall()
        ]

    def _event(self, connection: sqlite3.Connection, event_type: str, payload: dict) -> dict:
        event = {
            "id": str(uuid4()),
            "task_id": self.task_id,
            "run_id": self.run_id,
            "type": event_type,
            "payload": payload,
            "emitted_at": datetime.now(UTC).isoformat(),
        }
        cursor = connection.execute(
            "INSERT INTO sandbox_events(id,record_json) VALUES (?,?)", (event["id"], _json(event))
        )
        event["sequence"] = cursor.lastrowid
        connection.execute(
            "UPDATE sandbox_events SET record_json=? WHERE id=?", (_json(event), event["id"])
        )
        return event

    def record_event(self, type: str, payload: dict) -> dict:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._metadata(connection)
            return self._event(connection, type, payload)

    def events(self, after: int = 0) -> list[dict]:
        if not isinstance(after, int) or after < 0:
            raise SandboxError("invalid_arguments", "Event sequence must be nonnegative.")
        with closing(self._connect()) as connection:
            self._metadata(connection)
            return [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT record_json FROM sandbox_events WHERE sequence>? ORDER BY sequence",
                    (after,),
                ).fetchall()
            ]

    def _mutate(self, operation: str, key: str, arguments: dict, create, *, update=False) -> dict:
        key = _text(key, "idempotency_key", 200)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            if operation not in metadata["grants"]:
                raise SandboxError("access_denied", "This run is not permitted to use this tool.")
            receipt = connection.execute(
                "SELECT arguments,result FROM sandbox_receipts WHERE operation=? AND key=?",
                (operation, key),
            ).fetchone()
            if receipt:
                if receipt["arguments"] != _json(arguments):
                    raise SandboxError(
                        "idempotency_conflict", "Key already used with different arguments."
                    )
                return json.loads(receipt["result"])
            kind, result = create(connection, metadata)
            before = None
            if update:
                before = self._existing_object(connection, metadata, kind, result["id"])
                connection.execute(
                    "UPDATE sandbox_objects SET record_json=? WHERE id=? AND kind=?",
                    (_json(result), result["id"], kind),
                )
            else:
                self._insert_object(connection, kind, result)
            connection.execute(
                "INSERT INTO sandbox_receipts VALUES (?,?,?,?)",
                (operation, key, _json(arguments), _json(result)),
            )
            self._event(
                connection,
                "state.changed",
                {
                    "simulated": True,
                    "generation": metadata["generation"],
                    "operation": operation,
                    "object": result,
                    **({"before": before, "after": result} if update else {}),
                },
            )
            return result

    def _existing_object(self, connection, metadata, kind: str, object_id: str) -> dict:
        record = connection.execute(
            "SELECT record_json FROM sandbox_objects WHERE id=? AND kind=?", (object_id, kind)
        ).fetchone()
        if record is not None:
            result = json.loads(record[0])
            if result["project_id"] == metadata["project_id"]:
                return result
        raise SandboxError("not_found", "Object does not exist in this sandbox project.")

    def _new_object(self, kind: str, metadata: dict, fields: dict) -> dict:
        object_id = str(uuid4())
        return {
            "id": object_id,
            "simulated": True,
            "project_id": metadata["project_id"],
            "url": f"simulated://{self.run_id}/{kind}/{object_id}",
            **fields,
        }

    def create_ticket(self, title: str, release: str, idempotency_key: str) -> dict:
        args = {"title": _text(title, "title"), "release": _text(release, "release", 100)}
        return self._mutate(
            "tickets.create",
            idempotency_key,
            args,
            lambda connection, meta: ("tickets", self._new_object("tickets", meta, args)),
        )

    def create_checklist(
        self,
        ticket_id: str,
        title: str,
        items: list[str],
        idempotency_key: str,
    ) -> dict:
        ticket_id, title = _text(ticket_id, "ticket_id"), _text(title, "title")
        if not isinstance(items, list) or not 1 <= len(items) <= 50:
            raise SandboxError("invalid_arguments", "items must contain 1 to 50 strings.")
        items = [_text(item, "item", 500) for item in items]
        args = {"ticket_id": ticket_id, "title": title, "items": items}

        def create(connection, metadata):
            if not any(item["id"] == ticket_id for item in self._objects(connection, "tickets")):
                raise SandboxError("not_found", "Ticket does not exist in this sandbox project.")
            wire = self._serialize(metadata, **args)
            try:
                validated = validate_checklist_payload(wire)
            except AdapterContractError as error:
                raise SandboxError("adapter_contract_error", str(error)) from error
            return "checklists", self._new_object("checklists", metadata, validated)

        return self._mutate("checklists.create", idempotency_key, args, create)

    def update_checklist(self, checklist_id: str, items: list[str], idempotency_key: str) -> dict:
        checklist_id = _text(checklist_id, "checklist_id")
        if not isinstance(items, list) or not 1 <= len(items) <= 50:
            raise SandboxError("invalid_arguments", "items must contain 1 to 50 strings.")
        items = [_text(item, "item", 500) for item in items]
        args = {"checklist_id": checklist_id, "items": items}

        def update(connection, metadata):
            previous = self._existing_object(connection, metadata, "checklists", checklist_id)
            self._existing_object(connection, metadata, "tickets", previous["ticket_id"])
            wire = self._serialize(
                metadata,
                previous["ticket_id"],
                previous["title"],
                items,
            )
            try:
                validated = validate_checklist_payload(wire)
            except AdapterContractError as error:
                raise SandboxError("adapter_contract_error", str(error)) from error
            return "checklists", {**previous, **validated}

        return self._mutate("checklists.update", idempotency_key, args, update, update=True)

    def send_message(self, channel: str, text: str, links: list[str], idempotency_key: str) -> dict:
        channel, text = _text(channel, "channel", 100), _text(text, "text", 8000)
        if not isinstance(links, list) or not 1 <= len(links) <= 20:
            raise SandboxError("invalid_arguments", "links must contain 1 to 20 simulated URLs.")
        links = [_text(link, "link", 500) for link in links]
        args = {"channel": channel, "text": text, "links": links}

        def create(connection, metadata):
            allowed = {
                item["url"]
                for kind in ("tickets", "checklists")
                for item in self._objects(connection, kind)
            }
            if any(link not in allowed for link in links):
                raise SandboxError(
                    "invalid_reference", "Message links must reference objects in this sandbox."
                )
            return "messages", self._new_object("messages", metadata, args)

        return self._mutate("messages.send", idempotency_key, args, create)

    def update_message(
        self, message_id: str, text: str, idempotency_key: str, channel: str | None = None
    ) -> dict:
        message_id, text = _text(message_id, "message_id"), _text(text, "text", 8000)
        args = {"message_id": message_id, "text": text}
        if channel is not None:
            channel = _text(channel, "channel", 100)
            args["channel"] = channel

        def update(connection, metadata):
            if channel is not None and channel != metadata["qa_channel"]:
                raise SandboxError(
                    "access_denied",
                    "Destination correction is limited to this task's authoritative QA channel.",
                )
            previous = self._existing_object(connection, metadata, "messages", message_id)
            allowed = {
                item["url"]
                for kind in ("tickets", "checklists")
                for item in self._objects(connection, kind)
                if item["project_id"] == metadata["project_id"]
            }
            if any(link not in allowed for link in previous["links"]):
                raise SandboxError("invalid_reference", "Message references unresolved objects.")
            return "messages", {**previous, "text": text, "channel": channel or previous["channel"]}

        return self._mutate("messages.update", idempotency_key, args, update, update=True)

    def _list(self, kind: str) -> list[dict]:
        with closing(self._connect()) as connection:
            self._metadata(connection)
            return self._objects(connection, kind)

    def list_tickets(self) -> list[dict]:
        return self._list("tickets")

    def list_checklists(self) -> list[dict]:
        return self._list("checklists")

    def list_messages(self) -> list[dict]:
        return self._list("messages")

    def lookup_qa_owner(self, project_id: str) -> dict:
        from epoch_backend.repair_surfaces import LOOKUP, artifacts, invoke, lookup_result
        from epoch_backend.candidate_runner import CandidateError

        metadata = self.metadata()
        if "directory.read" not in metadata["grants"]:
            raise SandboxError("access_denied", "Directory access is not granted.")
        if _text(project_id, "project_id", 100) != metadata["project_id"]:
            raise SandboxError("access_denied", "Directory lookup is scoped to this project.")
        artifact = artifacts(metadata.get("adapter_manifest", {})).get(LOOKUP)
        if artifact is None:
            raise SandboxError("tool_not_found", "No generated directory adapter is installed.")
        records = [r for r in self._list("directory") if r["project_id"] == project_id]
        try:
            result = invoke(artifact, LOOKUP, {"records": records, "project_id": project_id})
            return lookup_result(result, records, project_id)
        except CandidateError as exc:
            raise SandboxError(exc.code, exc.message) from exc

    def read_runbook(self, purpose: str = "current", version: str | None = None) -> dict:
        if purpose not in ("current", "historical") or version not in (None, "v1", "v2"):
            raise SandboxError(
                "invalid_arguments", "Use current/historical purpose and v1/v2 version."
            )
        with closing(self._connect()) as connection:
            metadata = self._metadata(connection)
            if "runbooks.read" not in metadata["grants"]:
                raise SandboxError("access_denied", "Runbook access is not granted.")
            from epoch_backend.repair_surfaces import CONTEXT, artifacts, invoke, selected_document
            from epoch_backend.candidate_runner import CandidateError

            artifact = artifacts(metadata.get("adapter_manifest", {})).get(CONTEXT)
            if artifact:
                documents = [
                    d
                    for d in self._objects(connection, "runbooks")
                    if d["project_id"] == metadata["project_id"]
                ]
                try:
                    result = invoke(
                        artifact,
                        CONTEXT,
                        {
                            "documents": documents,
                            "project_id": metadata["project_id"],
                            "purpose": purpose,
                            "version": version,
                        },
                    )
                    document = selected_document(
                        result, documents, metadata["project_id"], purpose, version
                    )
                except CandidateError as exc:
                    raise SandboxError(exc.code, exc.message) from exc
                return {
                    **document,
                    "selection_rule_version": artifact.get(
                        "origin_version", artifact["artifact_sha256"]
                    ),
                    "requested_purpose": purpose,
                }
            selected = version or (
                "v1"
                if purpose == "historical" or metadata["scenario"] == "outdated_context"
                else "v2"
            )
            document = next(
                item
                for item in self._objects(connection, "runbooks")
                if item["version"] == selected
            )
            return {
                **document,
                "selection_rule_version": metadata["context_rule_version"],
                "requested_purpose": purpose,
            }

    def _snapshot(self, connection: sqlite3.Connection, metadata: dict) -> dict:
        return {
            "simulated": True,
            "project_id": metadata["project_id"],
            "generation": metadata["generation"],
            **{
                kind: self._objects(connection, kind)
                for kind in ("tickets", "checklists", "messages", "directory", "runbooks")
            },
        }

    def snapshot(self) -> dict:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN")
            return self._snapshot(connection, self._metadata(connection))

    def evaluate(self) -> dict:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = self._metadata(connection)
            snapshot = self._snapshot(connection, metadata)
            events = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT record_json FROM sandbox_events ORDER BY sequence"
                ).fetchall()
            ]
            evidence = [
                event["id"]
                for event in events
                if event["type"] == "state.changed"
                and event["payload"].get("generation") == metadata["generation"]
            ]
            result = evaluate_release(metadata, snapshot, evidence)
            event = self._event(connection, "verification.completed", result)
            return {**result, "evidence_id": event["id"]}
