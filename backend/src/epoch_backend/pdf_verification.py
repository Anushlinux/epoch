"""Trusted PDF cases, isolated replay and executor invariants. Never candidate-editable."""

import base64
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

from epoch_backend import hermes_bridge
from epoch_backend.pdf_contracts import verify_document, verify_merge
from epoch_backend.pdf_fixtures import brief, prompt, source_pdf
from epoch_backend.pdf_runtime import PdfRuntime, sha
from epoch_backend.pdf_sandbox import PdfSandbox

BASELINE_KEYS = (
    "implementation_sha256",
    "model_configuration_sha256",
    "system_prompt_sha256",
    "system_prompt_static_sha256",
    "discovery_sha256",
    "bridge_sha256",
    "user_settings_sha256",
)


def protected_identity():
    return sha(json.dumps(protected_sources(), sort_keys=True))


def protected_sources():
    folder = Path(__file__).parent
    return {
        name: (folder / name).read_text()
        for name in (
            "pdf_verification.py",
            "pdf_contracts.py",
            "pdf_sandbox.py",
            "pdf_fixtures.py",
            "pdf_runtime.py",
            "pdf_chat.py",
            "environment_store.py",
            "repair_surfaces.py",
        )
    }


def invariant_match(baseline, reference):
    return all(baseline.get(k) and baseline[k] == reference.get(k) for k in BASELINE_KEYS) and all(
        baseline.get(k) is True
        for k in (
            "implementation_unchanged",
            "user_settings_unchanged",
            "system_prompt_unchanged",
            "system_prompt_static_unchanged",
            "discovery_unchanged",
        )
    )


def request(sandbox, instruction, work_dir, history=None):
    return {
        "task_id": sandbox.task_id,
        "run_id": sandbox.run_id,
        "brief": instruction,
        "visible_history": history or [],
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
            "pdf_workshop",
        ],
        "max_turns": 20,
        "timeout_seconds": 600,
    }


def clone(sandbox, folder, manifest):
    folder.mkdir(parents=True, exist_ok=False)
    with (
        sqlite3.connect(sandbox.path) as origin,
        sqlite3.connect(folder / "sandbox.sqlite3") as destination,
    ):
        origin.backup(destination)
    if (sandbox.root / "blobs").exists():
        shutil.copytree(sandbox.root / "blobs", folder / "blobs")
    other = PdfSandbox(folder / "sandbox.sqlite3", sandbox.task_id, sandbox.run_id)
    other.pin(uuid4(), manifest)
    return other


def execute_hermes(sandbox, instruction, history, budget, cancelled, progress):
    with budget.verification_stage(
        lambda actor, used: progress(f"Hermes verification: {used} model requests")
    ) as stage:
        req = request(sandbox, instruction, sandbox.root / ("hermes-" + uuid4().hex), history)
        req.update(max_turns=stage.remaining_turns(), timeout_seconds=stage.remaining_seconds())
        with hermes_bridge.Session(
            req,
            lambda e: sandbox.record_event(e.get("type", "executor.event"), e.get("data", {})),
            cancelled,
            before_model_request=lambda: stage.consume("executor"),
        ) as session:
            result = session.run(
                instruction,
                max_turns=stage.remaining_turns(),
                timeout_seconds=stage.remaining_seconds(),
            )
        stage.check()
        sandbox.record_event("executor.result", {"result": result})
        return result


def output_check(sandbox, target, expected):
    new = [
        a
        for a in sandbox.assets()
        if a["operation_id"] == sandbox.metadata()["operation_id"]
        and a.get("tool_name") == ("pdf.create" if target == "render_pdf" else "pdf.merge")
    ]
    valid = []
    for asset in new:
        checked = (
            verify_document({**expected, "title": asset["document"]["title"]}, asset["inspection"])
            if target == "render_pdf"
            else verify_merge(
                [sandbox.asset(i)["inspection"] for i in expected], asset["inspection"]
            )
        )
        sandbox.raw(asset)
        if checked["passed"] and asset["verification"]["passed"]:
            valid.append(asset)
    return {
        "passed": bool(valid),
        "asset_ids": [a["id"] for a in valid],
        "new_outputs": [a["id"] for a in new],
    }


def component_cases(version, sandbox, target, captured, cancelled, budget):
    runtime = PdfRuntime(version["image_id"], cancelled)
    results = []
    if target == "render_pdf":
        documents = [
            captured["document"],
            {
                "title": "Short control",
                "blocks": [
                    {"kind": "paragraph", "text": "A short complete paragraph remains readable."}
                ],
            },
            brief("festival"),
            {
                "title": "Boundary variations",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "Long paragraph with complete content and readable text. " * 130,
                    },
                    {
                        "kind": "table",
                        "rows": [["Index", "Description"]]
                        + [
                            [
                                str(i),
                                f"Unique row {i}: preserve punctuation & quotation marks, "
                                "and this complete longer description.",
                            ]
                            for i in range(42)
                        ],
                    },
                    {
                        "kind": "paragraph",
                        "text": "Final condition after the table must remain visible.",
                    },
                ],
            },
        ]
        for i, doc in enumerate(documents):
            budget.overall_check()
            raw = runtime.execute(version["source"], target, document=doc)
            info = runtime.inspect(raw)
            checked = verify_document(doc, info)
            results.append(
                {"case": i, **checked, "pdf_sha256": sha(raw), "page_count": info["page_count"]}
            )
    else:
        assets = sandbox.merge_inputs(captured["asset_ids"])
        original = [sandbox.raw(a) for a in assets]
        varied = [
            source_pdf(
                runtime,
                "event-schedule.pdf",
                "Different order",
                "A new schedule with a different purpose.",
            ),
            source_pdf(runtime, "venue-map.pdf", "Map", "Map"),
        ]
        # Trusted fixture generator creates a static scan and a rotated page of
        # a different size. It never combines PDFs or supplies a merge implementation.
        fixture_source = """def render_pdf(document):
    import io
    from PIL import Image, ImageDraw
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfReader, PdfWriter
    out = io.BytesIO()
    c = Canvas(out, pagesize=(420, 300))
    if document["scan"]:
        image = Image.new("RGB", (600, 360), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 540, 320), outline="black", width=6)
        draw.text((80, 100), "STATIC SCANNED SOURCE", fill="black")
        c.drawImage(ImageReader(image), 20, 20, width=380, height=250)
    else:
        c.setFont("Helvetica", 14)
        c.drawString(30, 150, "Rotated landscape source")
    c.save()
    if document["scan"]:
        return out.getvalue()
    page = PdfReader(io.BytesIO(out.getvalue())).pages[0]
    page.rotate(90)
    writer = PdfWriter()
    writer.add_page(page)
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()
"""
        scanned = runtime.execute(fixture_source, "render_pdf", document={"scan": True})
        rotated = runtime.execute(fixture_source, "render_pdf", document={"scan": False})
        for i, inputs in enumerate(
            [
                original,
                list(reversed(varied)),
                [varied[0], varied[1], varied[0]],
                [scanned, rotated, varied[1], scanned],
            ]
        ):
            budget.overall_check()
            raw = runtime.execute(
                version["source"], target, inputs=[base64.b64encode(v).decode() for v in inputs]
            )
            checked = verify_merge([runtime.inspect(v) for v in inputs], runtime.inspect(raw))
            retained = sandbox.root / "verification" / version["id"] / "component"
            retained.mkdir(parents=True, exist_ok=True)
            (retained / f"merge-{i}.pdf").write_bytes(raw)
            for j, value in enumerate(inputs):
                (retained / f"merge-{i}-input-{j}.pdf").write_bytes(value)
            results.append(
                {
                    "case": i,
                    **checked,
                    "pdf_sha256": sha(raw),
                    "input_hashes": [sha(value) for value in inputs],
                }
            )
        inherited = version["artifacts"].get("pdf_renderer.py")
        if inherited:
            doc = brief("retreat")
            raw = runtime.execute(inherited["source"], "render_pdf", document=doc)
            results.append(
                {"case": "renderer_regression", **verify_document(doc, runtime.inspect(raw))}
            )
    return results


def fresh_sandbox(source, root, manifest, target):
    other = PdfSandbox(root / "sandbox.sqlite3", str(uuid4()), str(uuid4()))
    meta = source.metadata()
    other.initialize(meta["project_id"], meta["data_dir"], meta["image_override"])
    other.pin(uuid4(), manifest)
    seeded = other.seed("festival")
    if not seeded["ok"]:
        raise ValueError(seeded)
    if target == "render_pdf":
        return other, prompt("festival"), brief("festival")
    pdfs = [a for a in other.assets() if a["kind"] == "pdf"]
    ordered = [pdfs[1], pdfs[2], pdfs[0]]
    return (
        other,
        "Combine these PDFs in exactly this order: "
        + ", ".join(a["name"] for a in ordered)
        + ". Create event-pack.pdf, preserving every page.",
        [a["id"] for a in ordered],
    )
