"""Container transport only; candidate and trusted inspection are separate processes."""

import base64
import hashlib
import io
import json
import os
import resource
import subprocess
import sys
import tempfile

resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
LIMIT = 25 * 1024 * 1024


def inspect_pdf(raw, preview=None):
    import pdfplumber
    from pypdf import PdfReader

    if not raw.startswith(b"%PDF-"):
        raise ValueError("Not a PDF document")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported")
    root = reader.trailer["/Root"]
    if root.get("/AcroForm") or root.get("/Perms") or root.get("/OpenAction") or root.get("/AA"):
        raise ValueError("Signed, interactive or active PDFs are not supported")
    if root.get("/Names") and any(k in root["/Names"] for k in ("/JavaScript", "/EmbeddedFiles")):
        raise ValueError("PDF scripts and attachments are not supported")
    if not 1 <= len(reader.pages) <= 100:
        raise ValueError("PDF must contain between 1 and 100 pages")
    for page in reader.pages:
        if page.get("/AA"):
            raise ValueError("Interactive PDFs are not supported")
        for ref in page.get("/Annots", []):
            annotation = ref.get_object()
            if annotation.get("/Subtype") in ("/Widget", "/FileAttachment"):
                raise ValueError("Interactive PDFs are not supported")
            action = annotation.get("/A")
            if action and action.get("/S") not in ("/URI", "/GoTo"):
                raise ValueError("Active PDF annotations are not supported")
    pages = []
    with tempfile.TemporaryDirectory() as folder:
        source = os.path.join(folder, "source.pdf")
        with open(source, "wb") as out:
            out.write(raw)
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            indices = [preview - 1] if preview else range(len(pdf.pages))
            for i in indices:
                if not 0 <= i < len(pdf.pages):
                    raise ValueError("Page not found")
                page = pdf.pages[i]
                prefix = os.path.join(folder, "page")
                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(i + 1),
                        "-l",
                        str(i + 1),
                        "-r",
                        "96",
                        "-scale-to",
                        "1600",
                        "-singlefile",
                        "-png",
                        source,
                        prefix,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=15,
                )
                png = open(prefix + ".png", "rb").read()
                if preview:
                    return {"png": base64.b64encode(png).decode()}
                chars = page.chars
                visible = [
                    c
                    for c in chars
                    if c["x0"] >= -0.5
                    and c["x1"] <= page.width + 0.5
                    and c["top"] >= -0.5
                    and c["bottom"] <= page.height + 0.5
                ]
                # Layout text below the page still extracts from many PDF files.
                text = "".join(c["text"] for c in visible)
                pages.append(
                    {
                        "width": page.width,
                        "height": page.height,
                        "rotation": int(reader.pages[i].rotation),
                        "text": text[:200000],
                        "text_truncated": len(text) > 200000,
                        "render_sha256": hashlib.sha256(png).hexdigest(),
                        "outside_chars": len(chars) - len(visible),
                        "small_chars": sum(
                            bool(c["text"].strip()) and c["size"] < 9.5 for c in chars
                        ),
                        "bbox": page.bbox,
                    }
                )
    return {"pages": pages, "page_count": len(pages)}


def main(payload):
    if payload["mode"] in ("inspect", "preview"):
        return inspect_pdf(base64.b64decode(payload["pdf"], validate=True), payload.get("page"))
    if payload["mode"] == "probe":
        import socket

        checks = {
            "nonroot": os.getuid() != 0,
            "credentials_absent": not any(
                k in os.environ for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
            ),
            "host_absent": not any(
                os.path.exists(p) for p in ("/host", "/workspace", "/var/run/docker.sock")
            ),
        }
        try:
            open("/etc/epoch-test", "w").close()
            checks["root_read_only"] = False
        except OSError:
            checks["root_read_only"] = True
        try:
            with socket.create_connection(("1.1.1.1", 443), timeout=0.2):
                checks["network_denied"] = False
        except OSError:
            checks["network_denied"] = True
        return checks
    namespace = {"__name__": "generated_pdf_tool"}
    exec(compile(payload["source"], "candidate.py", "exec"), namespace)
    if payload["entrypoint"] == "render_pdf":
        result = namespace["render_pdf"](payload["document"])
    elif payload["entrypoint"] == "merge_pdfs":
        result = namespace["merge_pdfs"](
            [base64.b64decode(v, validate=True) for v in payload["inputs"]]
        )
    else:
        raise ValueError("Unsupported entrypoint")
    if not isinstance(result, bytes) or not 0 < len(result) <= LIMIT:
        raise ValueError("Tool must return bounded PDF bytes")
    return {"pdf": base64.b64encode(result).decode()}


try:
    request = json.loads(sys.stdin.buffer.read(40 * 1024 * 1024))
    response = {"ok": True, "result": main(request)}
except Exception as exc:
    response = {"ok": False, "error": {"code": type(exc).__name__, "message": str(exc)[:2000]}}
sys.stdout.write(json.dumps(response, allow_nan=False))
