"""Conversation-scoped immutable assets, calls, requests and dynamic PDF discovery."""

import base64
import inspect
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from epoch_backend.candidate_runner import CandidateError
from epoch_backend.environment_store import EnvironmentStore, stamp
from epoch_backend.pdf_baseline import render_pdf
from epoch_backend.pdf_contracts import (
    CapabilityRequest,
    CreatePdf,
    MergePdf,
    NoArguments,
    ReadAsset,
    DocumentQuery,
    verify_document,
    verify_merge,
)
from epoch_backend.pdf_runtime import PdfPreflightError, PdfRuntime, image_identity, sha
from epoch_backend.repair_surfaces import artifacts
from epoch_backend.storage import RequestConflict


class PdfSandbox:
    def __init__(self, path, task_id, run_id):
        self.path, self.task_id, self.run_id = Path(path), str(task_id), str(run_id)
        self.root = self.path.parent
        self.cancelled = None

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self, project_id, data_dir, image=""):
        self.root.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);"
                " CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY,record "
                "TEXT); CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY"
                " KEY AUTOINCREMENT,record TEXT); CREATE TABLE IF NOT EXISTS "
                "requests(key TEXT PRIMARY KEY,digest TEXT,result TEXT);"
            )
            if not db.execute("SELECT 1 FROM meta WHERE key='context'").fetchone():
                value = {
                    "project_id": project_id,
                    "data_dir": str(data_dir),
                    "image_override": image,
                    "operation_id": None,
                    "manifest": {
                        "version_id": "builtin",
                        "artifacts": {},
                        "bundle_sha256": sha(b"{}"),
                    },
                }
                db.execute("INSERT INTO meta VALUES('context',?)", (json.dumps(value),))
        return self

    def metadata(self):
        with closing(self.connect()) as db:
            value = json.loads(
                db.execute("SELECT value FROM meta WHERE key='context'").fetchone()[0]
            )
        return value

    def pin_context(self, policy, operation_id):
        with closing(self.connect()) as db, db:
            meta = json.loads(db.execute("SELECT value FROM meta WHERE key='context'").fetchone()[0])
            meta.update(context_policy=policy, operation_id=str(operation_id))
            db.execute("UPDATE meta SET value=? WHERE key='context'", (json.dumps(meta),))

    def versions(self):
        store = EnvironmentStore(Path(self.metadata()["data_dir"]) / "pdf" / "environments.sqlite3")
        store.initialize()
        return store

    def pin(self, operation_id, manifest=None):
        meta = self.metadata()
        meta.update(
            operation_id=str(operation_id),
            manifest=manifest or self.versions().manifest(meta["project_id"]),
        )
        with closing(self.connect()) as db, db:
            db.execute("UPDATE meta SET value=? WHERE key='context'", (json.dumps(meta),))

    def runtime(self):
        meta = self.metadata()
        return PdfRuntime(image_identity(meta["data_dir"], meta["image_override"]), self.cancelled)

    def record_event(self, kind, payload):
        meta = self.metadata()
        event = {
            "id": str(uuid4()),
            "type": kind,
            "emitted_at": stamp(),
            "payload": payload,
            "chat_id": self.task_id,
            "operation_id": meta["operation_id"],
            "environment_version": meta["manifest"]["version_id"],
        }
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO events(record) VALUES(?)", (json.dumps(event),))
        return event

    def events(self):
        with closing(self.connect()) as db:
            return [
                json.loads(r[0]) for r in db.execute("SELECT record FROM events ORDER BY sequence")
            ]

    def assets(self):
        with closing(self.connect()) as db:
            return [
                json.loads(r[0]) for r in db.execute("SELECT record FROM assets ORDER BY rowid")
            ]

    def asset(self, identity):
        with closing(self.connect()) as db:
            row = db.execute("SELECT record FROM assets WHERE id=?", (str(identity),)).fetchone()
        if not row:
            raise CandidateError("asset_not_found", "Asset is not accessible in this conversation.")
        return json.loads(row[0])

    def raw(self, asset):
        value = (self.root / "blobs" / asset["sha256"]).read_bytes()
        if sha(value) != asset["sha256"]:
            raise CandidateError("artifact_changed", "Stored file no longer matches its digest.")
        return value

    def put(self, name, raw, kind="pdf", **extra):
        digest = sha(raw)
        folder = self.root / "blobs"
        folder.mkdir(exist_ok=True)
        target = folder / digest
        try:
            with target.open("xb") as out:
                out.write(raw)
        except FileExistsError:
            if sha(target.read_bytes()) != digest:
                raise CandidateError(
                    "artifact_changed", "Stored blob failed integrity validation."
                ) from None
        meta = self.metadata()
        record = {
            "id": str(uuid4()),
            "name": name,
            "kind": kind,
            "sha256": digest,
            "size": len(raw),
            "chat_id": self.task_id,
            "project_id": meta["project_id"],
            "operation_id": meta["operation_id"],
            "environment_version": meta["manifest"]["version_id"],
            "created_at": stamp(),
            **extra,
        }
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO assets VALUES(?,?)", (record["id"], json.dumps(record)))
        return record

    def request(self, key, arguments, execute):
        digest = sha(json.dumps(arguments, sort_keys=True))
        with closing(self.connect()) as db:
            row = db.execute("SELECT digest,result FROM requests WHERE key=?", (key,)).fetchone()
        if row:
            if row[0] != digest:
                raise RequestConflict()
            if row[1] is None:
                raise CandidateError(
                    "request_unresolved",
                    "An earlier attempt may have effects; inspect it before continuing.",
                )
            return json.loads(row[1])
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO requests VALUES(?,?,NULL)", (key, digest))
        try:
            result = execute()
        except Exception as exc:
            result = {
                "ok": False,
                "error": {
                    "code": getattr(exc, "code", type(exc).__name__),
                    "message": str(exc)[:1000],
                },
            }
            if key.startswith("upload:") and isinstance(exc, PdfPreflightError):
                result["error"].update(
                    retryable=True, retry_mode="new_request", stage="preflight"
                )
            if getattr(exc, "container_name", None):
                result["error"]["container_name"] = exc.container_name
                result["error"]["docker_endpoint"] = exc.docker_endpoint
        with closing(self.connect()) as db, db:
            db.execute("UPDATE requests SET result=? WHERE key=?", (json.dumps(result), key))
        return result

    def seed(self, pack):
        from epoch_backend.pdf_fixtures import PACK_FILES, brief, source_pdf

        if pack not in PACK_FILES:
            raise CandidateError("invalid_pack", "Unknown bundled PDF pack.")

        def create():
            doc = brief(pack)
            values = [
                self.put(doc["title"], json.dumps(doc).encode(), "brief", document=doc, pack=pack)
            ]
            runtime = self.runtime()
            for name, title, content in PACK_FILES[pack]:
                raw = source_pdf(runtime, name, title, content)
                info = runtime.inspect(raw)
                values.append(
                    self.put(name, raw, inspection=info, page_count=info["page_count"], pack=pack)
                )
            return {"ok": True, "assets": values}

        return self.request("seed:" + pack, {"pack": pack}, create)

    def upload(self, name, raw, request_id):
        if len(raw) > 10 * 1024 * 1024 or not raw:
            raise CandidateError("upload_limit", "Upload a PDF of at most 10 MiB.")
        if (
            not name.lower().endswith(".pdf")
            or "/" in name
            or "\\" in name
            or len(name) > 124
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
        ):
            raise CandidateError(
                "invalid_filename", "Use a PDF filename without directory components."
            )

        def create():
            try:
                runtime = self.runtime()
            except CandidateError as exc:
                # Image configuration is read before inspection or asset persistence.
                raise PdfPreflightError(exc.code, str(exc)) from exc
            info = runtime.inspect(raw)
            return {
                "ok": True,
                "asset": self.put(name, raw, inspection=info, page_count=info["page_count"]),
            }

        return self.request("upload:" + str(request_id), {"name": name, "sha256": sha(raw)}, create)

    def reconcile_upload(self, request_id, *, confirm_same_engine=False):
        """Check an unresolved inspection without removing containers or old receipts."""
        from epoch_backend.candidate_runner import _docker

        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT digest,result FROM requests WHERE key=?",
                ("upload:" + str(request_id),),
            ).fetchone()
        if not row or row[1] is None:
            raise CandidateError(
                "request_unresolved", "This upload has no completed failure receipt to reconcile."
            )
        result = json.loads(row[1])
        error = result.get("error", {})
        if result.get("ok") is not False or error.get("code") != "cleanup_unresolved":
            raise CandidateError(
                "upload_retry_ineligible", "Only an upload with unconfirmed cleanup can use this check."
            )
        legacy = not bool(error.get("docker_endpoint"))
        if legacy and not confirm_same_engine:
            raise CandidateError(
                "upload_engine_confirmation_required",
                "This older upload did not record its Docker endpoint. Confirm that Docker "
                "Desktop uses the same local engine and context as the failed upload before "
                "checking cleanup.",
            )
        endpoint = self.runtime().preflight()
        if error.get("docker_endpoint") and error["docker_endpoint"] != endpoint:
            raise CandidateError(
                "cleanup_unresolved",
                "The failed upload used a different Docker endpoint. Restore that local context "
                "before checking cleanup; the saved failure remains unchanged.",
            )
        try:
            found = _docker([
                "--host", endpoint, "ps", "--all", "--filter", "label=epoch.pdf=true",
                "--format", "{{.Names}}",
            ])
        except CandidateError as exc:
            raise CandidateError(
                "cleanup_unresolved", "Docker container cleanup could not be checked. "
                "Wait for Docker Desktop to become ready, then try the check again."
            ) from exc
        if found.returncode:
            raise CandidateError(
                "cleanup_unresolved", "Docker container cleanup could not be checked. "
                "The failed upload remains blocked."
            )
        if found.stdout.strip():
            raise CandidateError(
                "cleanup_unresolved",
                "Epoch PDF containers still exist on the selected local Docker engine. "
                "Inspect and resolve them in Docker Desktop before retrying. "
                "This check does not remove containers.",
            )
        # Upload inspection precedes put(), so a cleanup exception cannot have committed
        # an asset. Never apply this recovery rule to seed/render/merge request receipts.
        evidence = self.record_event("pdf.upload_retry_checked", {
            "request_id": str(request_id), "request_digest": row[0],
            "docker_endpoint": endpoint, "epoch_pdf_containers": 0,
            "legacy_endpoint_unrecorded": legacy,
            "same_engine_confirmed_by_user": legacy and confirm_same_engine,
            "safe_to_retry": True, "retry_mode": "new_request",
        })
        return {
            "ok": True, "chat_id": self.task_id, "request_id": str(request_id),
            "safe_to_retry": True, "retry_mode": "new_request",
            "checked_at": evidence["emitted_at"], "recovery_id": evidence["id"],
        }

    def merge_inputs(self, identities):
        if not 2 <= len(identities) <= 5:
            raise CandidateError("merge_input_limit", "Select two to five PDFs.")
        assets = [self.asset(i) for i in identities]
        if (
            any(a["kind"] != "pdf" for a in assets)
            or sum(a["size"] for a in assets) > 20 * 1024 * 1024
            or sum(a["page_count"] for a in assets) > 100
        ):
            raise CandidateError(
                "merge_input_limit",
                "Merge inputs must be PDFs totaling at most 20 MiB and 100 pages.",
            )
        return assets

    def source(self, target):
        installed = artifacts(self.metadata()["manifest"])
        item = installed.get("pdf_renderer.py" if target == "render_pdf" else "pdf_merge.py")
        if item:
            return item["source"], item["image_id"], item["origin_version"]
        if target == "render_pdf":
            return inspect.getsource(render_pdf), self.runtime().image, "builtin"
        raise CandidateError("tool_not_found", "PDF merge is not installed.")

    def snapshot(self):
        meta = self.metadata()
        try:
            image = self.runtime().image
            readiness = {"available": True, "image_id": image, "execution_verified": False}
        except CandidateError as exc:
            readiness = {"available": False, "reason": str(exc)}
        active = self.versions().active_id(meta["project_id"])
        events = self.events()
        attempts = [e for e in events if e["type"] == "pdf.candidate_attempt"]
        installed = artifacts(self.versions().manifest(meta["project_id"]))
        actions = []
        for event in reversed(events):
            target = (
                "repair_tool"
                if event["type"] == "pdf.render_failed"
                else "create_tool"
                if event["type"] == "pdf.capability_requested"
                else None
            )
            if not target or any(a["action"] == target for a in actions):
                continue
            exhausted = sum(e["payload"].get("evidence_id") == event["id"] for e in attempts) >= 2
            stale = event["environment_version"] != active
            exists = target == "create_tool" and "pdf_merge.py" in installed
            actions.append(
                {
                    "action": target,
                    "evidence_id": event["id"],
                    "expected_version": active,
                    "eligible": not exhausted
                    and not stale
                    and not exists
                    and readiness["available"],
                    "reason": "Attempt limit reached"
                    if exhausted
                    else "Environment changed; run the task again"
                    if stale
                    else "Merge tool is already installed"
                    if exists
                    else readiness.get("reason", "Captured evidence supports this action"),
                }
            )
        return {
            "environment": "pdf_workshop",
            "local": True,
            "active_version": active,
            "pinned_version": meta["manifest"]["version_id"],
            "assets": self.assets(),
            "tools": PdfRegistry(self).definitions(),
            "actions": actions,
            "runtime": readiness,
            "events": events[-150:],
            "versions": self.versions().inspect(meta["project_id"]),
        }


DEFINITIONS = {
    "documents.list": ("List granted files and source briefs. Context policies can filter current guidance. "
                       "Use purpose=historical/all or a version for historical or explicit-version requests; "
                       "topic selects declared source topics. Explicit document IDs remain readable.", DocumentQuery),
    "documents.read": (
        (
            "Read a source brief, a saved document input or bounded PDF text. "
            "Preserve all supplied sections when asked to create a complete "
            "PDF."
        ),
        ReadAsset,
    ),
    "documents.inspect": (
        "Inspect the host's independent checks and page metadata for an actual saved asset.",
        ReadAsset,
    ),
    "pdf.create": (
        (
            "Create a PDF from complete structured content. Never omit content"
            " to make it fit. Supply title and ordered blocks; "
            "headings/paragraphs use text, bullets use items, tables use "
            "rectangular rows. A saved file does not imply that its "
            "independent checks passed. Reuse keys only for identical retries."
        ),
        CreatePdf,
    ),
    "capabilities.request": (
        (
            "When the requested task requires combining existing PDFs and "
            "discovery shows no merge tool, record the missing pdf.merge "
            "capability with the ordered asset IDs and output name. This does "
            "not execute a merge or start Debugger. Tell the user the "
            "capability is missing."
        ),
        CapabilityRequest,
    ),
}


class PdfRegistry:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def definitions(self):
        values = [
            {
                "name": name,
                "description": value[0],
                "implementation_version": self.sandbox.metadata()["manifest"]["version_id"],
            }
            for name, value in DEFINITIONS.items()
        ]
        merger = artifacts(self.sandbox.metadata()["manifest"]).get("pdf_merge.py")
        if merger:
            values.append(
                {
                    "name": "pdf.merge",
                    "description": merger["tool_contract"]["description"],
                    "implementation_version": merger["origin_version"],
                }
            )
        return values

    def discover_tools(self):
        result = {
            "interface_version": "epoch-tools-v1",
            "project_id": self.sandbox.metadata()["project_id"],
            "local": True,
            "tools": self.definitions(),
        }
        self.sandbox.record_event("tool.discovery", {"result": result})
        return {"ok": True, "result": result}

    def describe_tool(self, name):
        definition = next((t for t in self.definitions() if t["name"] == name), None)
        if not definition:
            return {
                "ok": False,
                "error": {
                    "code": "tool_not_found",
                    "message": "This tool is not present in the permitted catalog.",
                },
            }
        model = MergePdf if name == "pdf.merge" else DEFINITIONS[name][1]
        result = {**definition, "input_schema": model.model_json_schema()}
        self.sandbox.record_event("tool.described", {"result": result})
        return {"ok": True, "result": result}

    def invoke_tool(self, name, arguments):
        sandbox = self.sandbox
        call_id = str(uuid4())
        sandbox.record_event(
            "tool.called", {"call_id": call_id, "tool_name": name, "arguments": arguments}
        )
        try:
            if name not in {t["name"] for t in self.definitions()}:
                raise CandidateError(
                    "tool_not_found", "Tool is not available; discover the permitted catalog."
                )
            model = MergePdf if name == "pdf.merge" else DEFINITIONS[name][1]
            args = model.model_validate(arguments).model_dump(mode="json")

            def execute():
                if name == "documents.list":
                    from epoch_backend.context_policy import select_sources, source_catalog, record_selection
                    pin = sandbox.metadata().get("context_policy", {})
                    sources = source_catalog(sandbox, "pdf_workshop")
                    selected = select_sources(sources, pin.get("rules", []), pin.get("labels", {}), **args)
                    result = [
                            {**{k: a[k] for k in ("id", "name", "kind", "size")},
                             "source_metadata": pin.get("labels", {}).get(a["id"], {}), "sha256": a["sha256"]}
                            for a in sandbox.assets() if a["id"] in selected["retained_ids"]]
                    reference = record_selection(sandbox, sources, selected, tool=name, delivered=result, query=args)
                    return {"ok": True, "result": result, "context_selection": reference}
                if name in {"documents.read", "documents.inspect"}:
                    asset = sandbox.asset(args["asset_id"])
                    sandbox.raw(asset)
                    result = (
                        asset
                        if name == "documents.inspect"
                        else {
                            "asset_id": asset["id"],
                            "document": asset.get("document"),
                            "text": "\n".join(
                                p["text"] for p in asset.get("inspection", {}).get("pages", [])
                            )[:20000],
                            "text_limit": 20000,
                            "text_truncated": sum(
                                len(p["text"]) for p in asset.get("inspection", {}).get("pages", [])
                            )
                            > 20000,
                        }
                    )
                    from epoch_backend.context_policy import record_selection, source_catalog
                    if name == "documents.read":
                        result["source_metadata"] = sandbox.metadata().get("context_policy", {}).get("labels", {}).get(asset["id"], {})
                    sources = [s for s in source_catalog(sandbox, "pdf_workshop") if s["id"] == asset["id"]]
                    selected = {"retained_ids": [asset["id"]], "decisions": [{
                        "source_id": asset["id"], "sha256": asset["sha256"], "retained": True,
                        "reason": "explicit_source_read_preserved"}], "warnings": []}
                    reference = record_selection(sandbox, sources, selected, tool=name, delivered=result, query={"asset_id": asset["id"]})
                    return {"ok": True, "result": result, "context_selection": reference}
                if name == "capabilities.request":
                    if "pdf.merge" in {t["name"] for t in self.definitions()}:
                        raise CandidateError(
                            "capability_present", "Merge is already available; use the tool."
                        )
                    discoveries = [
                        e
                        for e in sandbox.events()
                        if e["type"] == "tool.discovery"
                        and e["operation_id"] == sandbox.metadata()["operation_id"]
                    ]
                    if not discoveries:
                        raise CandidateError(
                            "discovery_required",
                            "Discover the available tools before reporting a missing capability.",
                        )
                    sandbox.merge_inputs(args["asset_ids"])
                    event = sandbox.record_event(
                        "pdf.capability_requested",
                        {
                            "call_id": call_id,
                            "arguments": args,
                            "discovery_id": discoveries[-1]["id"],
                        },
                    )
                    return {
                        "ok": True,
                        "result": {
                            "status": "capability_missing",
                            "evidence_id": event["id"],
                            "message": "PDF merge is absent. Open Debugger and choose Create tool.",
                        },
                    }
                target = "render_pdf" if name == "pdf.create" else "merge_pdfs"
                source, image, version = sandbox.source(target)
                runtime = PdfRuntime(image, sandbox.cancelled)
                inputs = [] if target == "render_pdf" else sandbox.merge_inputs(args["asset_ids"])
                raw = runtime.execute(
                    source,
                    target,
                    **(
                        {"document": args["document"]}
                        if target == "render_pdf"
                        else {"inputs": [base64.b64encode(sandbox.raw(a)).decode() for a in inputs]}
                    ),
                )
                info = runtime.inspect(raw)
                checked = (
                    verify_document(args["document"], info)
                    if target == "render_pdf"
                    else verify_merge([a["inspection"] for a in inputs], info)
                )
                asset = sandbox.put(
                    args["output_name"],
                    raw,
                    inspection=info,
                    page_count=info["page_count"],
                    verification=checked,
                    document=args.get("document"),
                    source_assets=[a["id"] for a in inputs],
                    tool_name=name,
                    implementation_version=version,
                    source_sha256=sha(source),
                    image_id=image,
                    call_id=call_id,
                )
                event = sandbox.record_event(
                    "pdf.render_failed"
                    if target == "render_pdf" and not checked["passed"]
                    else "pdf.output_created",
                    {
                        "call_id": call_id,
                        "tool_name": name,
                        "arguments": args,
                        "asset_id": asset["id"],
                        "verification": checked,
                        "source_sha256": sha(source),
                        "image_id": image,
                    },
                )
                return {
                    "ok": True,
                    "result": {
                        "asset_id": asset["id"],
                        "name": asset["name"],
                        "page_count": asset["page_count"],
                        "verification": checked,
                        "evidence_id": event["id"],
                        "content_url": f"/api/chats/{sandbox.task_id}/assets/{asset['id']}/content",
                    },
                }

            result = (
                sandbox.request(name + ":" + args["idempotency_key"], args, execute)
                if "idempotency_key" in args
                else execute()
            )
        except Exception as exc:
            result = {
                "ok": False,
                "error": {
                    "code": getattr(exc, "code", type(exc).__name__),
                    "message": str(exc)[:1000],
                },
            }
        sandbox.record_event(
            "tool.result", {"call_id": call_id, "tool_name": name, "result": result}
        )
        return result
