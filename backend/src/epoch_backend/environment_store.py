"""Project-scoped immutable executable versions and transactional publication history."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from epoch_backend.candidate_runner import MAX_SOURCE_BYTES, CandidateError, digest
from epoch_backend.repair_surfaces import LOOKUP, SERIALIZER, artifacts, bundle_hash

BASE_VERSION = "builtin"
REQUIRED_PROOFS = {"component", "isolation", "original_replay", "fresh_release", "regression"}


def stamp():
    return datetime.now(UTC).isoformat()


class EnvironmentStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise CandidateError("unsupported_schema", "Unsupported environment schema.")
            if version == 0:
                if connection.execute(
                    "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
                ).fetchone():
                    raise CandidateError("invalid_database", "Environment database is not empty.")
                connection.execute(
                    "CREATE TABLE versions(id TEXT PRIMARY KEY, "
                    "project TEXT NOT NULL, record TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE active(project TEXT PRIMARY KEY, "
                    "version TEXT NOT NULL, previous TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE repairs(id TEXT PRIMARY KEY, "
                    "project TEXT NOT NULL, record TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE history(sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "project TEXT NOT NULL, record TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE requests(id TEXT PRIMARY KEY, project TEXT NOT NULL, "
                    "expected TEXT NOT NULL, result TEXT NOT NULL)"
                )
                connection.execute("PRAGMA user_version=1")

    def recover_interrupted(self):
        """Called only after acquiring the server lease; never resume publication."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            for row in connection.execute("SELECT id, record FROM versions").fetchall():
                record = json.loads(row[1])
                if record["status"] == "staged":
                    record.update(
                        status="rejected",
                        reason="Server interrupted verification.",
                        finished_at=stamp(),
                    )
                    connection.execute(
                        "UPDATE versions SET record=? WHERE id=?", (json.dumps(record), row[0])
                    )
            for row in connection.execute("SELECT id, record FROM repairs").fetchall():
                record = json.loads(row[1])
                if record["status"] not in {"published", "blocked", "interrupted"}:
                    record.update(
                        status="interrupted",
                        finished_at=stamp(),
                        error={
                            "code": "server_restarted",
                            "message": "Repair interrupted; retained evidence is not approval.",
                        },
                    )
                    for attempt in record.get("attempts", []):
                        if attempt["status"] in {"generating", "verifying"}:
                            attempt["status"] = "interrupted"
                    connection.execute(
                        "UPDATE repairs SET record=? WHERE id=?", (json.dumps(record), row[0])
                    )

    def active_id(self, project: str) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT version FROM active WHERE project=?", (project,)
            ).fetchone()
            return row[0] if row else BASE_VERSION

    def version(self, identity: str, *, project: str | None = None) -> dict:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT record FROM versions WHERE id=?", (identity,)
            ).fetchone()
        if row is None:
            raise CandidateError("version_not_found", "Environment version not found.")
        record = json.loads(row[0])
        if project is not None and record["project"] != project:
            raise CandidateError(
                "scope_mismatch", "Environment version belongs to another project."
            )
        if digest(record["source"]) != record["artifact_sha256"]:
            raise CandidateError("artifact_changed", "Stored executable artifact digest mismatch.")
        if "artifacts" in record:
            artifacts(record)
        return record

    def _shared_lookup(self):
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT v.id FROM active a JOIN versions v ON a.version=v.id ORDER BY v.rowid DESC"
            ).fetchall()
        for row in rows:
            version = self.version(row[0])
            item = artifacts(version).get(LOOKUP)
            if version["status"] == "published" and item and item.get("portable"):
                return item
        return None

    def manifest(self, project: str, identity: str | None = None, *, staged: bool = False):
        identity = identity or self.active_id(project)
        if identity == BASE_VERSION:
            shared = self._shared_lookup()
            values = {LOOKUP: shared} if shared else {}
            return {
                "version_id": BASE_VERSION,
                "artifacts": values,
                "bundle_sha256": bundle_hash(values),
            }
        version = self.version(identity, project=project)
        if version["status"] != "published" and not (staged and version["status"] == "staged"):
            raise CandidateError(
                "version_inactive", "Unverified or rejected artifact cannot execute."
            )
        selected = artifacts(version)
        if LOOKUP not in selected:
            shared = self._shared_lookup()
            if shared:
                selected[LOOKUP] = shared
        return {
            "version_id": identity,
            "project": project,
            "source": version["source"],
            "artifact_sha256": version["artifact_sha256"],
            "image_id": version["image_id"],
            "runner_version": version["runner_version"],
            "target": version.get("target", SERIALIZER),
            "artifacts": selected,
            "bundle_sha256": bundle_hash(selected),
        }

    def stage(
        self,
        project: str,
        source: str,
        *,
        image_id: str,
        runner_version: str,
        parent: str,
        diagnosis: dict,
        diff: str,
        target: str = SERIALIZER,
        tool_contract: dict | None = None,
    ) -> dict:
        if not source.strip() or len(source.encode()) > MAX_SOURCE_BYTES:
            raise CandidateError("invalid_candidate", "Generated source is empty or too large.")
        record = {
            "id": str(uuid4()),
            "project": project,
            "parent": parent,
            "source": source,
            "artifact_sha256": digest(source),
            "image_id": image_id,
            "runner_version": runner_version,
            "status": "staged",
            "created_at": stamp(),
            "diagnosis": diagnosis,
            "diff": diff,
            "proofs": [],
        }
        inherited = artifacts(self.manifest(project, parent))
        inherited[target] = {
            "source": source,
            "artifact_sha256": record["artifact_sha256"],
            "image_id": image_id,
            "runner_version": runner_version,
            "origin_version": record["id"],
            "origin_project": project,
            "tool_contract": tool_contract,
            "portable": target == LOOKUP,
        }
        record.update(target=target, artifacts=inherited, bundle_sha256=bundle_hash(inherited))
        artifacts(record)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO versions VALUES(?,?,?)", (record["id"], project, json.dumps(record))
            )
        return record

    def reject(self, identity: str, proofs: list[dict], reason: str):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT record FROM versions WHERE id=?", (identity,)
            ).fetchone()
            if row is None:
                raise CandidateError("version_not_found", "Environment version not found.")
            record = json.loads(row[0])
            if record["status"] != "staged":
                raise CandidateError("version_conflict", "Only a staged candidate can be rejected.")
            record.update(status="rejected", proofs=proofs, reason=reason, finished_at=stamp())
            connection.execute(
                "UPDATE versions SET record=? WHERE id=?", (json.dumps(record), identity)
            )

    def publish(self, identity: str, proofs: list[dict], *, expected_active: str) -> dict:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT record FROM versions WHERE id=?", (identity,)
            ).fetchone()
            if row is None:
                raise CandidateError("version_not_found", "Candidate not found.")
            record = json.loads(row[0])
            if (
                record["status"] != "staged"
                or digest(record["source"]) != record["artifact_sha256"]
            ):
                raise CandidateError(
                    "publication_denied", "Candidate is not an intact staged artifact."
                )
            required = (REQUIRED_PROOFS - {"fresh_release"} | {"fresh_task"}) if record.get("target", "").startswith("pdf_") else REQUIRED_PROOFS
            if record.get("target", "").startswith("pdf_") and any(
                p.get("bundle_sha256") != record["bundle_sha256"]
                or p.get("image_id") != record["image_id"]
                or not p.get("verifier_sha256") for p in proofs
            ):
                raise CandidateError("publication_denied", "PDF proof does not match the complete verified bundle and runtime.")
            if (
                len(proofs) != len(required)
                or {p.get("kind") for p in proofs} != required
                or any(
                    p.get("passed") is not True
                    or p.get("artifact_sha256") != record["artifact_sha256"]
                    for p in proofs
                )
            ):
                raise CandidateError(
                    "publication_denied",
                    "Every required trusted check must pass for this exact artifact.",
                )
            artifacts(record)
            current = connection.execute(
                "SELECT version FROM active WHERE project=?", (record["project"],)
            ).fetchone()
            active = current[0] if current else BASE_VERSION
            if active != expected_active or record["parent"] != active:
                raise CandidateError(
                    "version_conflict",
                    "Active environment changed; do not publish stale verification.",
                )
            record.update(status="published", proofs=proofs, published_at=stamp())
            connection.execute(
                "UPDATE versions SET record=? WHERE id=?", (json.dumps(record), identity)
            )
            connection.execute(
                "INSERT OR REPLACE INTO active VALUES(?,?,?)", (record["project"], identity, active)
            )
            event = {
                "type": "environment.published",
                "version_id": identity,
                "previous": active,
                "artifact_sha256": record["artifact_sha256"],
                "created_at": stamp(),
            }
            connection.execute(
                "INSERT INTO history(project,record) VALUES(?,?)",
                (record["project"], json.dumps(event)),
            )
            return record

    def rollback(self, project: str, expected: str, request_id: UUID) -> dict:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            retry = connection.execute(
                "SELECT * FROM requests WHERE id=?", (str(request_id),)
            ).fetchone()
            if retry:
                if retry["project"] != project or retry["expected"] != expected:
                    raise CandidateError(
                        "request_conflict", "Rollback request ID has different input."
                    )
                return json.loads(retry["result"])
            row = connection.execute("SELECT * FROM active WHERE project=?", (project,)).fetchone()
            if row is None or row["version"] != expected or expected == BASE_VERSION:
                raise CandidateError(
                    "version_conflict", "Reload the active version before rollback."
                )
            target = row["previous"]
            if target != BASE_VERSION:
                prior = json.loads(
                    connection.execute(
                        "SELECT record FROM versions WHERE id=?", (target,)
                    ).fetchone()[0]
                )
                if (
                    prior["status"] != "published"
                    or digest(prior["source"]) != prior["artifact_sha256"]
                ):
                    raise CandidateError(
                        "artifact_changed", "Rollback target is not an intact published version."
                    )
                previous = prior["parent"]
            else:
                previous = BASE_VERSION
            connection.execute(
                "UPDATE active SET version=?,previous=? WHERE project=?",
                (target, previous, project),
            )
            result = {
                "type": "environment.rolled_back",
                "project": project,
                "previous": expected,
                "version_id": target,
                "created_at": stamp(),
            }
            connection.execute(
                "INSERT INTO history(project,record) VALUES(?,?)", (project, json.dumps(result))
            )
            connection.execute(
                "INSERT INTO requests VALUES(?,?,?,?)",
                (str(request_id), project, expected, json.dumps(result)),
            )
            return result

    def save_repair(self, record: dict):
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO repairs VALUES(?,?,?)",
                (record["id"], record["project"], json.dumps(record)),
            )

    def inspect(self, project: str) -> dict:
        with closing(self._connect()) as connection:

            def rows(table):
                return [
                    json.loads(row[0])
                    for row in connection.execute(
                        f"SELECT record FROM {table} WHERE project=? ORDER BY rowid", (project,)
                    )
                ]

            return {
                "project": project,
                "active_version": self.active_id(project),
                "effective_artifacts": {
                    name: {
                        "origin_version": item.get("origin_version"),
                        "origin_project": item.get("origin_project"),
                        "artifact_sha256": item["artifact_sha256"],
                    }
                    for name, item in artifacts(self.manifest(project)).items()
                },
                "versions": rows("versions"),
                "repairs": rows("repairs"),
                "history": rows("history"),
            }
