"""Deterministic, scoped context selection. Originals and explicit reads survive."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


RULES = {"deduplicate", "prefer_current_approved", "match_topic"}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def stamp():
    return datetime.now(UTC).isoformat()


def source_catalog(sandbox, environment):
    meta = sandbox.metadata()
    values = sandbox.assets() if environment == "pdf_workshop" else sandbox.snapshot()["runbooks"]
    return [{"id": str(v["id"]), "name": v.get("name", v["id"]),
             "sha256": v.get("sha256") or digest({k: v.get(k) for k in ("document_id", "version", "is_current", "content")}),
             "size": v.get("size", len(encoded(v))),
             "kind": v.get("kind", "runbook"), "project_id": meta["project_id"]}
            for v in values if v.get("project_id") == meta["project_id"]]


def select_sources(sources, rules, labels, *, purpose="current", version=None, topic=None,
                   reviewed_exclusions=()):
    """Rules affect whole retrieval candidates, never clauses/sections of a document."""
    decisions = {s["id"]: {"source_id": s["id"], "sha256": s["sha256"],
                           "retained": True, "reason": "retained"} for s in sources}
    warnings = []
    metadata = {s["id"]: labels.get(s["id"], {}) if labels.get(s["id"], {}).get("sha256") == s["sha256"] else {}
                for s in sources}
    if any(label.get("inherited_metadata_conflict") for label in metadata.values()):
        warnings.append("Conflicting inherited source annotations were retained; an explicit source review is required.")

    def exclude(source, reason, replacement=None):
        if metadata[source["id"]].get("inherited_metadata_conflict"):
            return
        if metadata[source["id"]].get("protected"):
            warnings.append("Protected sources were retained regardless of selection rules.")
            return
        decisions[source["id"]].update(retained=False, reason=reason, replacement_id=replacement)

    # Explicit history/all/version requests bypass current/topic/dedup policies.
    # This is selection, never an authorization expansion; candidates are already scoped.
    if purpose != "current" or version:
        for item in decisions.values():
            item["reason"] = "historical_or_explicit_version_preserved"
        return {"retained_ids": list(decisions), "decisions": list(decisions.values()),
                "warnings": ["Current-context policies were bypassed for an all/historical/versioned request."]}
    if "match_topic" in rules and topic:
        for source in sources:
            topics = metadata[source["id"]].get("topics", [])
            if topics and topic.casefold() not in {v.casefold() for v in topics}:
                exclude(source, "different_declared_topic")
            elif not topics:
                warnings.append("Sources without topic metadata were retained.")
    if "prefer_current_approved" in rules:
        families = {}
        for source in sources:
            label = metadata[source["id"]]
            if label.get("family") and decisions[source["id"]]["retained"]:
                families.setdefault(label["family"], []).append(source)
            elif not label.get("family"):
                warnings.append("Sources without version-family metadata were retained.")
        for family in families.values():
            approved = [s for s in family if metadata[s["id"]].get("approved")
                        and metadata[s["id"]].get("status") == "current"]
            if len(approved) == 1:
                for source in family:
                    if metadata[source["id"]].get("status") == "superseded":
                        exclude(source, "superseded_by_approved_current", approved[0]["id"])
            else:
                warnings.append("Missing or conflicting current approvals: all versions retained.")
    if "deduplicate" in rules:
        seen = {}
        for source in sources:
            if not decisions[source["id"]]["retained"]:
                continue
            label = metadata[source["id"]]
            # Different authority/version metadata or source kinds are not equivalent.
            key = digest([source["sha256"], source["kind"], label])
            if key in seen:
                exclude(source, "identical_content_and_metadata", seen[key])
            else:
                seen[key] = source["id"]
    apply_reviewed_exclusions(sources, decisions, metadata, reviewed_exclusions, warnings)
    retained = [s["id"] for s in sources if decisions[s["id"]]["retained"]]
    if sources and not retained:
        warnings.append("The policy would remove every source; selection was refused and all retained.")
        for item in decisions.values():
            item.update(retained=True, reason="empty_context_prevented", replacement_id=None)
        retained = [s["id"] for s in sources]
    return {"retained_ids": retained, "decisions": list(decisions.values()),
            "warnings": sorted(set(warnings))}


def apply_reviewed_exclusions(sources, decisions, metadata, proposals, warnings):
    """Apply reviewed document relationships to exact content in the current scope.

    Source IDs can change on upload into a later conversation. Content hash and kind
    bind the user's review across those conversations; no name/version heuristic does.
    The replacement must remain present after both legacy and specific selections.
    """
    if not proposals:
        return
    by_content = {}
    for source in sources:
        by_content.setdefault((source["sha256"], source["kind"]), []).append(source)
    candidates = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            warnings.append("An invalid reviewed document relationship was ignored.")
            continue
        keys = ("source_sha256", "source_kind", "replacement_sha256", "replacement_kind", "source_id", "replacement_id")
        if any(not isinstance(proposal.get(key), str) or not proposal[key] for key in keys):
            warnings.append("An incomplete reviewed document relationship was ignored.")
            continue
        source_key = (proposal["source_sha256"], proposal["source_kind"])
        replacement_key = (proposal["replacement_sha256"], proposal["replacement_kind"])
        reason = proposal.get("reason")
        if (reason not in {"superseded", "duplicate"} or source_key[1] != replacement_key[1]
                or proposal["source_id"] == proposal["replacement_id"]
                or (reason == "duplicate") != (source_key == replacement_key)):
            warnings.append("A reviewed document relationship conflicts with its content identities; sources were retained.")
            continue
        candidates.append((proposal, source_key, replacement_key))
    # A future conversation may use different IDs for identical content. Detect
    # ambiguous replacements and chains using content identities before excluding.
    relationships = {}
    for _, source_key, replacement_key in candidates:
        relationships.setdefault(source_key, set()).add(replacement_key)
    incoming = {replacement_key for _, source_key, replacement_key in candidates if source_key != replacement_key}
    blocked = {source_key for source_key, replacements in relationships.items() if len(replacements) > 1}
    for _, source_key, replacement_key in candidates:
        if source_key != replacement_key and (replacement_key in relationships or source_key in incoming):
            blocked.update((source_key, replacement_key))

    def protected(source):
        label = metadata[source["id"]]
        return (label.get("inherited_metadata_conflict") or label.get("protected")
                or (label.get("approved") and label.get("status") == "current"))

    def agrees(source, replacement, reason):
        old, new = metadata[source["id"]], metadata[replacement["id"]]
        if old.get("inherited_metadata_conflict") or new.get("inherited_metadata_conflict") or new.get("status") == "superseded":
            return False
        if old.get("family") and new.get("family") and old["family"] != new["family"]:
            return False
        if reason == "duplicate" and old and new:
            # The same bytes may have different reviewed authority or topic labels.
            # A duplicate-content suggestion must not resolve that disagreement.
            return all(old.get(key) == new.get(key) for key in ("family", "version", "status", "approved", "topics"))
        return True

    for proposal, source_key, replacement_key in candidates:
        if source_key in blocked:
            warnings.append("Conflicting or chained reviewed replacements were retained for a new source review.")
            continue
        targets = [item for item in by_content.get(source_key, []) if decisions[item["id"]]["retained"]]
        if not targets:
            continue
        replacements = [item for item in by_content.get(replacement_key, [])
                        if decisions[item["id"]]["retained"] and metadata[item["id"]].get("status") != "superseded"
                        and not metadata[item["id"]].get("inherited_metadata_conflict")]
        if not replacements:
            warnings.append("A reviewed replacement is missing, changed or no longer retained; its source was kept.")
            continue
        # Prefer the reviewed identity when present. Later uploads fall back to a
        # deterministic matching copy, prioritizing explicitly retained authority.
        replacements.sort(key=lambda item: (item["id"] != proposal["replacement_id"], not protected(item), item["id"]))
        for source in targets:
            if source_key == replacement_key and source["id"] == replacements[0]["id"]:
                # Duplicate relationships keep one stable copy even when later
                # uploads assign every file a new source ID.
                continue
            if protected(source):
                warnings.append("Protected, explicitly approved current or ambiguously annotated documents were retained.")
                continue
            replacement = next((item for item in replacements if item["id"] != source["id"]
                                and decisions[item["id"]]["retained"] and agrees(source, item, proposal["reason"])), None)
            if not replacement:
                warnings.append("A compatible retained replacement is unavailable; the document was kept.")
                continue
            decisions[source["id"]].update(retained=False, reason=f"reviewed_{proposal['reason']}",
                replacement_id=replacement["id"], proposal_id=proposal.get("id"),
                analysis_id=proposal.get("analysis_id"), review_id=proposal.get("review_id"),
                reviewed_source_id=proposal["source_id"], reviewed_replacement_id=proposal["replacement_id"],
                explanation=proposal.get("explanation", ""))


def source_labels(sources, labels, chat_id):
    """Reuse unambiguous source metadata by content hash within the same scope."""
    result = {}
    known = {}
    for chat_labels in labels.values():
        for label in chat_labels.values():
            known.setdefault(label["sha256"], {})[digest(label)] = label
    for source in sources:
        direct = labels.get(str(chat_id), {}).get(source["id"])
        matches = known.get(source["sha256"], {})
        if direct and direct["sha256"] == source["sha256"]:
            result[source["id"]] = direct
        elif len(matches) == 1:
            result[source["id"]] = next(iter(matches.values()))
        elif len(matches) > 1:
            # Conflicting authority from prior conversations is not the same as
            # absent metadata. Keep this marker local to the snapshot/pin; never
            # silently choose, overwrite or persist one user's annotation.
            result[source["id"]] = {"sha256": source["sha256"], "inherited_metadata_conflict": True}
    return result


class ContextPolicyStore:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "context-policies.sqlite3"

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self):
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS context_scopes (
                  scope TEXT PRIMARY KEY, revision INTEGER NOT NULL, active_id TEXT, labels TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS noise_records (
                  id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, kind TEXT NOT NULL,
                  created_at TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS noise_history ON noise_records(chat_id,kind,created_at);
                CREATE TABLE IF NOT EXISTS context_decisions (
                  id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, operation_id TEXT,
                  created_at TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS context_decision_history ON context_decisions(chat_id,created_at);
            """)

    @staticmethod
    def scope(project, environment):
        return encoded([project, environment])

    def state(self, project, environment, db=None):
        if db is None:
            with closing(self.connect()) as connection:
                return self.state(project, environment, connection)
        row = db.execute("SELECT * FROM context_scopes WHERE scope=?", (self.scope(project, environment),)).fetchone()
        return {"revision": row["revision"], "active_id": row["active_id"], "labels": json.loads(row["labels"])} if row else {
            "revision": 0, "active_id": None, "labels": {}}

    def write_state(self, project, environment, value, db):
        db.execute("INSERT INTO context_scopes VALUES(?,?,?,?) ON CONFLICT(scope) DO UPDATE SET "
                   "revision=excluded.revision,active_id=excluded.active_id,labels=excluded.labels",
                   (self.scope(project, environment), value["revision"], value["active_id"], encoded(value["labels"])))

    def put(self, record, db=None):
        if db is None:
            with closing(self.connect()) as connection, connection:
                return self.put(record, connection)
        db.execute("INSERT INTO noise_records VALUES(?,?,?,?,?)", (record["id"], record["chat_id"],
                   record["kind"], record["created_at"], encoded(record)))
        return record

    def get(self, record_id, db=None):
        if db is None:
            with closing(self.connect()) as connection:
                return self.get(record_id, connection)
        row = db.execute("SELECT body FROM noise_records WHERE id=?", (str(record_id),)).fetchone()
        return json.loads(row[0]) if row else None

    def pin(self, chat):
        with closing(self.connect()) as db:
            db.execute("BEGIN")
            state = self.state(chat.project_id, chat.environment, db)
            policy = self.get(state["active_id"], db) if state["active_id"] else None
            return {"database": str(self.path.resolve()), "project": chat.project_id,
                    "environment": chat.environment, "revision": state["revision"],
                    "policy_id": state["active_id"], "rules": policy["rules"] if policy else [],
                    "source_exclusions": policy.get("source_exclusions", []) if policy else [],
                    "labels": state["labels"].get(str(chat.id), {})}


def record_selection(sandbox, sources, selection, *, tool, delivered=None, query=None):
    pin = sandbox.metadata().get("context_policy")
    if not pin:
        return None
    record = {"id": str(uuid4()), "chat_id": sandbox.task_id,
              "operation_id": sandbox.metadata().get("operation_id"), "created_at": stamp(),
              "policy_id": pin["policy_id"], "policy_revision": pin["revision"], "tool": tool,
              "query": query or {}, "sources": sources, "source_metadata": pin["labels"], "selection": selection,
              "delivered": delivered, "delivered_sha256": digest(delivered)}
    with closing(sqlite3.connect(pin["database"], timeout=10)) as db, db:
        db.execute("INSERT INTO context_decisions VALUES(?,?,?,?,?)", (record["id"], record["chat_id"],
                   record["operation_id"], record["created_at"], encoded(record)))
    reference = {key: record[key] for key in ("id", "policy_id", "policy_revision", "delivered_sha256")}
    reference["selection"] = selection
    sandbox.record_event("context.selection", reference)
    return reference


def runbook_context(sandbox, query, result):
    """Apply only to ordinary chat pins; existing generated repair takes precedence."""
    pin = sandbox.metadata().get("context_policy")
    if not pin:
        return result, None
    from epoch_backend.repair_surfaces import CONTEXT, artifacts
    from epoch_backend.sandbox import SandboxError
    rules = pin["rules"]
    legacy = CONTEXT in artifacts(sandbox.metadata().get("adapter_manifest", {}))
    sources = source_catalog(sandbox, "default")
    full_query = {"purpose": query["purpose"], "version": query.get("version"), "topic": None}
    selected = select_sources(sources, [] if legacy else rules, pin["labels"], **full_query)
    if legacy:
        selected["warnings"].append("The existing generated runbook repair owns selection; the new policy was not applied.")
    elif rules and query["purpose"] == "current" and not query.get("version"):
        retained = selected["retained_ids"]
        if "prefer_current_approved" in rules and len(retained) != 1:
            record_selection(sandbox, sources, selected, tool="runbooks.read", query=full_query)
            raise SandboxError("context_unresolved", "Current runbook authority is missing or ambiguous. Review source metadata; no document was guessed.")
        if len(retained) == 1:
            document = next(d for d in sandbox.snapshot()["runbooks"] if d["id"] == retained[0])
            if not document.get("is_current"):
                raise SandboxError("context_metadata_conflict", "Source annotations conflict with the runbook's authoritative current-version metadata.")
            result = {**document, "selection_rule_version": pin["policy_id"], "requested_purpose": query["purpose"]}
    reference = record_selection(sandbox, sources, selected, tool="runbooks.read", delivered=result, query=full_query)
    return result, reference
