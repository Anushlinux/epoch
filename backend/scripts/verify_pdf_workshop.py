"""Bounded real Hermes/Luna PDF acceptance. Preserves every operation and file."""

import argparse
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from epoch_backend.app import create_app
from epoch_backend.config import Settings
from epoch_backend.pdf_fixtures import prompt


def audit_source_briefs(root):
    """Separate fixture-content coverage from the renderer's preservation verdict."""
    from epoch_backend.pdf_contracts import document_parts, normalized
    from epoch_backend.pdf_fixtures import brief

    results = []
    for database in (root / "chats").glob("*/sandbox.sqlite3"):
        with sqlite3.connect(database) as connection:
            for (record,) in connection.execute("SELECT record FROM assets"):
                asset = json.loads(record)
                if asset.get("tool_name") != "pdf.create":
                    continue
                pack = "festival" if "Festival" in asset["document"]["title"] else "retreat"
                text = normalized("".join(document_parts(asset["document"])))
                cursor, missing = 0, []
                for part in document_parts(brief(pack))[1:]:
                    part = normalized(part)
                    index = text.find(part, cursor)
                    if index < 0:
                        missing.append(part)
                    else:
                        cursor = index + len(part)
                results.append(
                    {
                        "asset_id": asset["id"],
                        "pack": pack,
                        "passed": not missing,
                        "missing": missing,
                    }
                )
    assert results and all(result["passed"] for result in results), results
    (root / "source-brief-coverage.json").write_text(json.dumps(results, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--fresh-reuse",
        action="store_true",
        help="Prove saved tool reuse in this new Python process",
    )
    parser.add_argument(
        "--stage", choices=["baseline", "repair", "merge", "reuse", "all"], default="all"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("--live authorizes actual configured model calls")
    root = args.data_dir.resolve()
    report_path = root / "acceptance.json"
    if root.exists() and not args.resume:
        parser.error("Use a new data directory or --resume to retain prior evidence")
    (root / "pdf").mkdir(parents=True, exist_ok=True)
    runtime = Path(__file__).resolve().parents[1] / "data" / "pdf" / "runtime.json"
    if not (root / "pdf" / "runtime.json").exists():
        shutil.copyfile(runtime, root / "pdf" / "runtime.json")
    report = (
        json.loads(report_path.read_text())
        if report_path.exists()
        else {"live": True, "project": "pdf-acceptance", "steps": {}, "operations": []}
    )
    settings = Settings(data_dir=root, telemetry_enabled=False)

    def save():
        report_path.write_text(json.dumps(report, indent=2))

    with TestClient(create_app(settings)) as client:

        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        def post(path, payload):
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

        def create(pack):
            chat = post(
                "/api/chats",
                {
                    "client_request_id": str(uuid4()),
                    "environment": "pdf_workshop",
                    "project_id": report["project"],
                },
            )
            seeded = post(f"/api/chats/{chat['id']}/assets/bundled", {"pack": pack})
            assert seeded["ok"], seeded
            return chat["id"]

        def run(chat, endpoint, payload):
            operation = post(
                f"/api/chats/{chat}/{endpoint}", {"client_request_id": str(uuid4()), **payload}
            )
            identity = operation["id"]
            report["operations"].append(
                {"chat_id": chat, "operation_id": identity, "endpoint": endpoint}
            )
            save()
            last, deadline = None, time.monotonic() + 1850
            while True:
                operation = get(f"/api/chats/{chat}/operations/{identity}")
                if operation["activity"] != last:
                    print(operation["activity"], flush=True)
                    last = operation["activity"]
                if operation["status"] != "running":
                    report["operations"][-1]["result"] = operation
                    save()
                    assert operation["status"] == "completed", operation.get("error")
                    return operation
                if time.monotonic() > deadline:
                    post(f"/api/chats/{chat}/operations/{identity}/cancel", {})
                    raise RuntimeError("Acceptance operation exceeded deadline")
                time.sleep(1)

        def step(name, function):
            if name not in report["steps"]:
                report["steps"][name] = function()
                save()
            return report["steps"][name]

        def baseline():
            chat = create("retreat")
            report["primary_chat"] = chat
            save()
            run(chat, "messages", {"content": prompt("retreat")})
            env = get(f"/api/chats/{chat}/environment")
            failed = [
                a
                for a in env["assets"]
                if a.get("tool_name") == "pdf.create" and not a["verification"]["passed"]
            ]
            assert failed, "No genuine clipped PDF was produced"
            return {"chat_id": chat, "broken_assets": [a["id"] for a in failed]}

        primary = step("baseline", baseline)["chat_id"]
        if args.stage == "baseline":
            return

        def action(kind):
            env = get(f"/api/chats/{primary}/environment")
            selected = next(a for a in env["actions"] if a["action"] == kind and a["eligible"])
            operation = run(
                primary,
                "environment-actions",
                {k: selected[k] for k in ("action", "evidence_id", "expected_version")},
            )
            return {
                "version": operation["analysis"]["published_version"],
                "operation_id": operation["id"],
            }

        step("renderer_repair", lambda: action("repair_tool"))

        def fresh_document():
            chat = create("festival")
            run(chat, "messages", {"content": prompt("festival")})
            env = get(f"/api/chats/{chat}/environment")
            outputs = [a for a in env["assets"] if a.get("tool_name") == "pdf.create"]
            assert outputs and all(a["verification"]["passed"] for a in outputs)
            return {"chat_id": chat, "assets": [a["id"] for a in outputs]}

        step("fresh_document", fresh_document)
        if args.stage == "repair":
            return

        def missing_merge():
            assets = get(f"/api/chats/{primary}/assets")["items"]
            proposal = [
                a
                for a in assets
                if a.get("tool_name") == "pdf.create" and a["verification"]["passed"]
            ][-1]
            message = (
                f"Combine the proposal PDF with asset ID {proposal['id']}, "
                "hotel-brochure.pdf, and venue-map.pdf into one client-pack.pdf, "
                "in that exact order. Preserve all pages."
            )
            run(primary, "messages", {"content": message})
            env = get(f"/api/chats/{primary}/environment")
            assert "pdf.merge" not in {t["name"] for t in env["tools"]}
            assert any(a["action"] == "create_tool" and a["eligible"] for a in env["actions"])
            return {"chat_id": primary, "message": message}

        step("missing_merge", missing_merge)
        step("merge_creation", lambda: action("create_tool"))
        if args.stage == "merge":
            return

    # Close and reopen the actual backend to verify persisted discovery.
    with TestClient(create_app(settings)) as client:

        def reused_merge():
            chat = create("festival")
            run(
                chat,
                "messages",
                {
                    "content": (
                        "Combine event-schedule.pdf, sponsor-brochure.pdf and "
                        "speaker-profiles.pdf into event-pack.pdf, in that order. "
                        "Preserve every page."
                    )
                },
            )
            env = get(f"/api/chats/{chat}/environment")
            outputs = [a for a in env["assets"] if a.get("tool_name") == "pdf.merge"]
            assert outputs and all(a["verification"]["passed"] for a in outputs)
            return {
                "chat_id": chat,
                "assets": [a["id"] for a in outputs],
                "after_restart": True,
                "process_id": os.getpid(),
            }

        step("process_restart_reuse" if args.fresh_reuse else "restart_reuse", reused_merge)

    def rollback_proof():
        # Preserve the working demo. Exercise rollback against an isolated copy of
        # the acceptance project's published history, with fresh scoped assets.
        from epoch_backend.environment_store import EnvironmentStore
        from epoch_backend.pdf_fixtures import brief
        from epoch_backend.pdf_sandbox import PdfRegistry, PdfSandbox

        isolated = root / ("rollback-" + uuid4().hex)
        (isolated / "pdf").mkdir(parents=True)
        shutil.copyfile(root / "pdf/runtime.json", isolated / "pdf/runtime.json")
        with (
            sqlite3.connect(root / "pdf/environments.sqlite3") as source,
            sqlite3.connect(isolated / "pdf/environments.sqlite3") as destination,
        ):
            source.backup(destination)
        store = EnvironmentStore(isolated / "pdf/environments.sqlite3")
        box = PdfSandbox(isolated / "chat/sandbox.sqlite3", str(uuid4()), str(uuid4())).initialize(
            report["project"], isolated
        )
        box.pin(uuid4())
        before = store.active_id(report["project"])
        first_request = uuid4()
        first = store.rollback(report["project"], before, first_request)
        assert store.rollback(report["project"], before, first_request) == first
        box.pin(uuid4())
        registry = PdfRegistry(box)
        catalog = registry.discover_tools()["result"]["tools"]
        assert "pdf.merge" not in {t["name"] for t in catalog}

        def render(key):
            result = registry.invoke_tool(
                "pdf.create",
                {"document": brief("retreat"), "output_name": key + ".pdf", "idempotency_key": key},
            )
            assert result["ok"], result
            return box.assets()[-1]

        repaired = render("retained-repair")
        assert repaired["verification"]["passed"]
        second = store.rollback(report["project"], first["version_id"], uuid4())
        box.pin(uuid4())
        original = render("restored-defect")
        assert second["version_id"] == "builtin" and not original["verification"]["passed"]
        assert store.active_id(report["project"]) == "builtin"
        return {
            "isolated_data_dir": str(isolated),
            "first": first,
            "second": second,
            "catalog_after_first": catalog,
            "repaired_asset": repaired,
            "broken_asset": original,
        }

    step("rollback", rollback_proof)
    report["source_brief_coverage"] = audit_source_briefs(root)
    report["completed"] = True
    save()
    print(f"Acceptance completed: {report_path}", flush=True)


if __name__ == "__main__":
    main()
