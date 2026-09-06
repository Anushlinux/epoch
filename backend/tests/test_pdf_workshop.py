"""PDF workshop contracts, retirement and actual opt-in Docker behavior."""

import inspect
import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend.app import create_app
from epoch_backend.candidate_runner import CandidateError
from epoch_backend.config import Settings
from epoch_backend.pdf_baseline import render_pdf
from epoch_backend.pdf_contracts import Document, verify_document
from epoch_backend.pdf_fixtures import brief
from epoch_backend.pdf_runtime import PdfRuntime, image_identity
from epoch_backend.pdf_sandbox import PdfRegistry, PdfSandbox


def test_document_contract_and_clipped_text():
    for pack in ("retreat", "festival"):
        Document.model_validate(brief(pack))
    with pytest.raises(ValueError):
        Document.model_validate(
            {"title": "x", "blocks": [{"kind": "table", "rows": [["a"], ["b", "c"]]}]}
        )
    doc = {"title": "Title", "blocks": [{"kind": "paragraph", "text": "Last condition"}]}
    page = {
        "width": 595.276,
        "height": 841.89,
        "text": "Title",
        "small_chars": 0,
        "outside_chars": 13,
        "text_truncated": False,
    }
    assert not verify_document(doc, {"pages": [page]})["passed"]


def test_generated_schema_is_structured_and_cannot_expand_permissions():
    from jsonschema import ValidationError, validate

    from epoch_backend.pdf_contracts import MergePdf, literal_schema

    contract = MergePdf.model_json_schema()
    constraints = literal_schema(contract)
    validate(contract, constraints)
    with pytest.raises(ValidationError):
        validate({**contract, "additionalProperties": True}, constraints)


def test_merge_checks_reject_reordering_appearance_and_page_loss():
    from epoch_backend.pdf_contracts import verify_merge

    page = {"width": 420, "height": 300, "rotation": 0, "text": "", "render_sha256": "scan-one"}
    second = {**page, "rotation": 90, "render_sha256": "scan-two"}
    inputs = [{"pages": [page]}, {"pages": [second]}]
    assert verify_merge(inputs, {"pages": [page, second]})["passed"]
    assert not verify_merge(inputs, {"pages": [second, page]})["passed"]
    assert not verify_merge(inputs, {"pages": [page]})["passed"]
    assert not verify_merge(inputs, {"pages": [page, {**second, "width": 421}]})["passed"]
    assert not verify_merge(inputs, {"pages": [page, {**second, "render_sha256": "changed"}]})[
        "passed"
    ]


def test_asset_blob_tampering_is_detected_without_cross_conversation_access(tmp_path):
    box = PdfSandbox(tmp_path / "a/sandbox.sqlite3", str(uuid4()), str(uuid4())).initialize(
        "demo", tmp_path
    )
    asset = box.put("brief", b"original", kind="brief")
    second = PdfSandbox(tmp_path / "b/sandbox.sqlite3", str(uuid4()), str(uuid4())).initialize(
        "demo", tmp_path
    )
    with pytest.raises(CandidateError):
        second.asset(asset["id"])
    (box.root / "blobs" / asset["sha256"]).write_bytes(b"tampered")
    with pytest.raises(CandidateError, match="digest"):
        box.raw(asset)


def test_merge_admission_limits_and_capability_discovery(tmp_path):
    """Unit metadata fixtures exercise admission; parsing is covered by real Docker cases."""
    box = PdfSandbox(tmp_path / "sandbox.sqlite3", str(uuid4()), str(uuid4())).initialize(
        "demo", tmp_path
    )
    box.pin(uuid4())
    one = box.put("one.pdf", b"unit metadata fixture", page_count=60)
    with pytest.raises(CandidateError, match="pages"):
        box.merge_inputs([one["id"], one["id"]])
    with pytest.raises(CandidateError, match="five"):
        box.merge_inputs([one["id"]] * 6)
    large = box.put("large.pdf", b"x" * (8 * 1024 * 1024), page_count=1)
    with pytest.raises(CandidateError, match="20 MiB"):
        box.merge_inputs([large["id"]] * 3)
    small = box.put("small.pdf", b"small unit metadata fixture", page_count=1)
    registry = PdfRegistry(box)
    args = {
        "asset_ids": [small["id"], small["id"]],
        "output_name": "pack.pdf",
        "idempotency_key": "capability",
        "capability": "pdf.merge",
        "reason": "Combine these PDFs",
    }
    assert not registry.invoke_tool("capabilities.request", args)["ok"]
    registry.discover_tools()
    # A rejected key retains its receipt; a new explicit request has a new identity.
    args["idempotency_key"] = "capability-after-discovery"
    assert registry.invoke_tool("capabilities.request", args)["ok"]


def test_csv_retired_without_deleting_records(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path, enable_hermes=False, telemetry_enabled=False))
    ) as client:
        payload = {"client_request_id": str(uuid4()), "environment": "csv_broken"}
        assert client.post("/api/chats", json=payload).status_code == 422
        created = client.post("/api/chats", json={"client_request_id": str(uuid4())}).json()
        service = client.app.state.chats
        old = service.get(created["id"])
        old.environment = "csv_broken"
        service.save(old)
        assert client.get("/api/chats").json()["total"] == 0
        assert client.get("/api/chats/" + created["id"]).status_code == 410
        assert service.get(created["id"]).environment == "csv_broken"
        assert (
            client.post(
                f"/api/chats/{created['id']}/csv-repair", json={"client_request_id": str(uuid4())}
            ).status_code
            == 410
        )


def test_pdf_catalog_missing_merge_and_scope(tmp_path):
    box = PdfSandbox(tmp_path / "chat" / "sandbox.sqlite3", str(uuid4()), str(uuid4()))
    box.initialize("demo", tmp_path)
    box.pin(uuid4())
    registry = PdfRegistry(box)
    assert "pdf.merge" not in {t["name"] for t in registry.discover_tools()["result"]["tools"]}
    assert registry.describe_tool("pdf.merge")["error"]["code"] == "tool_not_found"
    with pytest.raises(CandidateError, match="not accessible"):
        box.asset(uuid4())
    assert not box.snapshot()["runtime"]["available"]


def test_pdf_request_retry_conflict_and_interruption(tmp_path):
    from epoch_backend.storage import RequestConflict

    box = PdfSandbox(tmp_path / "sandbox.sqlite3", str(uuid4()), str(uuid4()))
    box.initialize("demo", tmp_path)
    calls = []

    def execute():
        calls.append(1)
        return {"ok": True, "id": "unchanged"}

    first = box.request("same-key", {"value": 1}, execute)
    assert box.request("same-key", {"value": 1}, execute) == first
    assert calls == [1]
    with pytest.raises(RequestConflict):
        box.request("same-key", {"value": 2}, execute)
    failed = box.request("failed", {}, lambda: (_ for _ in ()).throw(ValueError("failure")))
    assert box.request("failed", {}, execute) == failed
    assert calls == [1]


def test_pdf_proofs_cannot_publish_other_bundle_or_unverified_code(tmp_path):
    from epoch_backend.environment_store import EnvironmentStore

    store = EnvironmentStore(tmp_path / "versions.sqlite3")
    store.initialize()
    version = store.stage(
        "demo",
        "def render_pdf(document): return b'not a PDF'",
        image_id="sha256:" + "a" * 64,
        runner_version="pdf-tools-v1",
        parent="builtin",
        diagnosis={"test_double": True},
        diff="test only",
        target="pdf_renderer.py",
    )
    with pytest.raises(CandidateError, match="proof"):
        store.publish(
            version["id"], [{"kind": "component", "passed": True}], expected_active="builtin"
        )
    assert store.active_id("demo") == "builtin"
    store.recover_interrupted()
    assert store.version(version["id"])["status"] == "rejected"


def test_pdf_http_inputs_and_actions_are_scoped(tmp_path, monkeypatch):
    from epoch_backend import debugger_bridge, hermes_bridge

    monkeypatch.setattr(hermes_bridge, "execute", lambda *_: pytest.fail("Unexpected model call"))
    monkeypatch.setattr(debugger_bridge, "complete", lambda *_: pytest.fail("Unexpected debugger"))
    with TestClient(
        create_app(Settings(data_dir=tmp_path, enable_hermes=False, telemetry_enabled=False))
    ) as client:
        created = client.post(
            "/api/chats", json={"client_request_id": str(uuid4()), "environment": "pdf_workshop"}
        ).json()
        base = f"/api/chats/{created['id']}"
        assert client.get(base + "/assets").json() == {"items": []}
        assert client.get(base + "/environment").json()["actions"] == []
        assert client.get(base + f"/assets/{uuid4()}/content").status_code == 404
        assert (
            client.post(
                base + "/environment-actions",
                json={
                    "client_request_id": str(uuid4()),
                    "action": "create_tool",
                    "expected_version": "builtin",
                    "evidence_id": str(uuid4()),
                },
            ).status_code
            == 503
        )
        assert (
            client.post(
                base + "/assets?name=../secret.pdf&client_request_id=" + str(uuid4()),
                content=b"%PDF-test",
            ).status_code
            == 422
        )


@pytest.mark.skipif(os.getenv("EPOCH_TEST_DOCKER") != "1", reason="Explicit real PDF Docker checks")
def test_real_pdf_rejects_invalid_files_and_limits(tmp_path):
    from pathlib import Path

    runtime = PdfRuntime(image_identity(Path(__file__).resolve().parents[1] / "data"))
    with pytest.raises(CandidateError):
        runtime.inspect(b"not a PDF")
    with pytest.raises(CandidateError):
        runtime.execute("def render_pdf(document): return 'not bytes'", "render_pdf", document={})
    import threading

    cancel = threading.Event()
    cancel.set()
    with pytest.raises(CandidateError):
        PdfRuntime(runtime.image, cancel).run({"mode": "probe"})


@pytest.mark.skipif(os.getenv("EPOCH_TEST_DOCKER") != "1", reason="Explicit real PDF Docker checks")
def test_real_pdf_rejects_encryption_forms_and_signed_flags():
    from pathlib import Path

    runtime = PdfRuntime(image_identity(Path(__file__).resolve().parents[1] / "data"))
    source = """def render_pdf(document):
    import io
    from pypdf import PdfWriter
    from pypdf.generic import NameObject, DictionaryObject, BooleanObject
    writer = PdfWriter()
    writer.add_blank_page(width=595.276, height=841.89)
    if document["mode"] == "encrypted":
        writer.encrypt("password")
    else:
        key = "/AcroForm" if document["mode"] == "form" else "/Perms"
        writer._root_object[NameObject(key)] = DictionaryObject(
            {NameObject("/Present"): BooleanObject(True)}
        )
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
"""
    for mode in ("encrypted", "form", "signed"):
        raw = runtime.execute(source, "render_pdf", document={"mode": mode})
        with pytest.raises(CandidateError):
            runtime.inspect(raw)
    with pytest.raises(CandidateError, match="exceeded its limits"):
        runtime.run(
            {
                "source": "while True: pass",
                "mode": "execute",
                "entrypoint": "render_pdf",
                "document": {},
            },
            timeout=2,
        )


@pytest.mark.skipif(os.getenv("EPOCH_TEST_DOCKER") != "1", reason="Explicit real PDF Docker checks")
def test_real_pdf_clipping_and_runtime(tmp_path):
    from pathlib import Path

    runtime = PdfRuntime(image_identity(Path(__file__).resolve().parents[1] / "data"))
    probe = runtime.run({"mode": "probe"})
    assert all(probe.values()), probe
    doc = brief("retreat")
    raw = runtime.execute(inspect.getsource(render_pdf), "render_pdf", document=doc)
    info = runtime.inspect(raw)
    checks = verify_document(doc, info)
    assert info["page_count"] == 1
    assert info["pages"][0]["outside_chars"] > 0
    assert not checks["passed"]
    (tmp_path / "broken.pdf").write_bytes(raw)
    (tmp_path / "broken.png").write_bytes(runtime.preview(raw, 1))
    (tmp_path / "checks.json").write_text(json.dumps(checks, indent=2))
    short = {
        "title": "Short document",
        "blocks": [{"kind": "paragraph", "text": "This content fits on one page."}],
    }
    assert verify_document(
        short,
        runtime.inspect(
            runtime.execute(inspect.getsource(render_pdf), "render_pdf", document=short)
        ),
    )["passed"]
