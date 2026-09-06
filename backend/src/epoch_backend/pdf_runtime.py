"""Bounded Docker transport for PDF tools; never executes candidates on the host."""

import base64
import hashlib
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

from epoch_backend.candidate_runner import CandidateError, _docker, _environment

RUNNER_VERSION = "pdf-tools-v1"
MAX_WIRE = 40 * 1024 * 1024


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def image_identity(root, explicit=""):
    if explicit:
        image = explicit
    else:
        path = Path(root) / "pdf" / "runtime.json"
        if not path.is_file():
            raise CandidateError(
                "pdf_runtime_unavailable", "Run the PDF runtime setup command first."
            )
        image = json.loads(path.read_text())["image_id"]
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise CandidateError(
            "pdf_runtime_unavailable", "PDF runtime must use an immutable image ID."
        )
    return image


class PdfRuntime:
    def __init__(self, image, cancelled=None):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            raise CandidateError("invalid_image", "An immutable PDF image ID is required.")
        self.image, self.cancelled = image, cancelled or threading.Event()

    def run(self, payload, timeout=60):
        wire = json.dumps(payload).encode()
        if len(wire) > MAX_WIRE or self.cancelled.is_set():
            raise CandidateError(
                "pdf_input_limit", "PDF input exceeds limits or operation was cancelled."
            )
        context = _docker(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"])
        endpoint = context.stdout.strip()
        if context.returncode or not endpoint.startswith(("unix://", "npipe://")):
            raise CandidateError(
                "pdf_runtime_unavailable", "A local Linux Docker engine is required."
            )
        name = "epoch-pdf-" + uuid4().hex
        proc = None
        attempted = False
        deadline = time.monotonic() + min(60, timeout)

        def command(args):
            return _docker(
                ["--host", endpoint, *args], timeout=max(0.1, min(10, deadline - time.monotonic()))
            )

        try:
            attempted = True
            created = command(
                [
                    "create",
                    "--pull=never",
                    "--name",
                    name,
                    "--label",
                    "epoch.pdf=true",
                    "--network=none",
                    "--read-only",
                    "--user=65534:65534",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
                    "--memory=1g",
                    "--memory-swap=1g",
                    "--cpus=1",
                    "--pids-limit=32",
                    "--ulimit=nofile=128:128",
                    "--ulimit=fsize=41943040:41943040",
                    "--tmpfs=/tmp:rw,noexec,nosuid,size=268435456",
                    "--log-driver=none",
                    "--interactive",
                    self.image,
                ]
            )
            if created.returncode:
                raise CandidateError(
                    "pdf_runtime_unavailable", "PDF image unavailable; run setup and start Docker."
                )
            config = json.loads(command(["inspect", name]).stdout)[0]
            host = config["HostConfig"]
            if not (
                host["ReadonlyRootfs"]
                and host["NetworkMode"] == "none"
                and not host["Privileged"]
                and host["CapDrop"] == ["ALL"]
                and host["Memory"] == 1073741824
                and host["MemorySwap"] == 1073741824
                and host["PidsLimit"] == 32
                and host["NanoCpus"] == 1000000000
                and not host.get("Binds")
                and not any(m["Type"] == "bind" for m in config.get("Mounts", []))
                and config["Config"]["User"] == "65534:65534"
                and "no-new-privileges:true" in host["SecurityOpt"]
                and config["Image"] == self.image
            ):
                raise CandidateError(
                    "isolation_unverified", "PDF container restrictions do not match policy."
                )
            proc = subprocess.Popen(
                ["docker", "--host", endpoint, "start", "-ai", name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=_environment(),
            )
            chunks = bytearray()
            overflow = threading.Event()

            def read():
                while block := proc.stdout.read(65536):
                    if len(chunks) + len(block) > MAX_WIRE:
                        overflow.set()
                        break
                    chunks.extend(block)

            def write():
                try:
                    proc.stdin.write(wire)
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            reader = threading.Thread(target=read, daemon=True)
            writer = threading.Thread(target=write, daemon=True)
            reader.start()
            writer.start()
            while proc.poll() is None:
                if overflow.is_set() or self.cancelled.is_set() or time.monotonic() > deadline:
                    raise CandidateError(
                        "pdf_execution_stopped",
                        "PDF execution exceeded its limits or was cancelled.",
                    )
                time.sleep(0.03)
            reader.join(2)
            writer.join(2)
            if reader.is_alive() or overflow.is_set() or proc.returncode:
                raise CandidateError(
                    "pdf_execution_failed", "PDF worker failed or exceeded its output limit."
                )
            result = json.loads(chunks)
            if not result.get("ok"):
                error = result.get("error", {})
                raise CandidateError("pdf_tool_error", error.get("message", "PDF tool failed"))
            return result["result"]
        finally:
            if attempted:
                cleanup = _docker(["--host", endpoint, "rm", "--force", name])
                if cleanup.returncode and "No such container" not in cleanup.stderr:
                    raise CandidateError(
                        "cleanup_unresolved", "PDF container cleanup could not be confirmed."
                    )
            if proc and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    def execute(self, source, target, **arguments):
        if not 0 < len(source.encode()) <= 20000:
            raise CandidateError("invalid_candidate", "PDF source must be at most 20,000 bytes.")
        value = self.run({"mode": "execute", "source": source, "entrypoint": target, **arguments})
        raw = base64.b64decode(value["pdf"], validate=True)
        if len(raw) > 25 * 1024 * 1024:
            raise CandidateError("pdf_output_limit", "PDF output exceeds 25 MiB.")
        return raw

    def inspect(self, raw):
        return self.run({"mode": "inspect", "pdf": base64.b64encode(raw).decode()})

    def preview(self, raw, page):
        return base64.b64decode(
            self.run({"mode": "preview", "pdf": base64.b64encode(raw).decode(), "page": page})[
                "png"
            ]
        )
