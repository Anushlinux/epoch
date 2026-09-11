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

from epoch_backend.candidate_runner import CandidateError, _docker, _environment, _options

RUNNER_VERSION = "pdf-tools-v1"
MAX_WIRE = 40 * 1024 * 1024


class PdfPreflightError(CandidateError):
    """The runtime was rejected before any container could be created."""


def local_engine():
    """Read the selected local engine without creating or starting containers."""
    try:
        context = _docker(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"])
        endpoint = context.stdout.strip()
        if context.returncode or not endpoint.startswith(("unix://", "npipe://")):
            raise PdfPreflightError(
                "pdf_runtime_unavailable", "Select a local Linux Docker context for PDF tools."
            )
        info = _docker(["--host", endpoint, "info", "--format", "{{json .}}"])
        if info.returncode:
            raise PdfPreflightError(
                "pdf_runtime_unavailable",
                "Docker is not ready. Start Docker Desktop, wait for its Linux engine to "
                "finish starting, then retry the upload. No PDF container was created.",
            )
        metadata = json.loads(info.stdout)
        if metadata.get("OSType") != "linux":
            raise PdfPreflightError(
                "pdf_runtime_unavailable", "Switch Docker Desktop to Linux containers, then retry."
            )
        if not any("seccomp" in str(item) for item in metadata.get("SecurityOptions", [])):
            raise PdfPreflightError(
                "pdf_runtime_unavailable", "The local Docker engine must enable default seccomp."
            )
        return endpoint
    except PdfPreflightError:
        raise
    except (CandidateError, ValueError, TypeError, AttributeError) as exc:
        raise PdfPreflightError(
            "pdf_runtime_unavailable",
            "Docker readiness could not be checked. Start Docker Desktop with its Linux "
            "engine, then retry. No PDF container was created.",
        ) from exc


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

    def preflight(self):
        endpoint = local_engine()
        try:
            found = _docker(["--host", endpoint, "image", "inspect", self.image, "--format", "{{.Id}}"])
            if found.returncode or found.stdout.strip() != self.image:
                raise PdfPreflightError(
                    "pdf_runtime_unavailable",
                    "The configured PDF runtime image is missing. Run the PDF runtime setup "
                    "command with Docker running, then retry. No PDF container was created.",
                )
        except PdfPreflightError:
            raise
        except CandidateError as exc:
            raise PdfPreflightError(
                "pdf_runtime_unavailable",
                "The PDF runtime image could not be checked. Wait for Docker to become "
                "ready, then retry. No PDF container was created.",
            ) from exc
        return endpoint

    def run(self, payload, timeout=60):
        wire = json.dumps(payload).encode()
        if len(wire) > MAX_WIRE or self.cancelled.is_set():
            raise CandidateError(
                "pdf_input_limit", "PDF input exceeds limits or operation was cancelled."
            )
        endpoint = self.preflight()
        name = "epoch-pdf-" + uuid4().hex
        proc = None
        attempted = False
        failure = None
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
                **_options(),
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
        except Exception as exc:
            failure = exc
            raise
        finally:
            cleanup_failed = False
            try:
                if attempted:
                    cleanup = _docker(["--host", endpoint, "rm", "--force", name])
                    cleanup_failed = bool(
                        cleanup.returncode and "No such container" not in cleanup.stderr
                    )
            except CandidateError:
                cleanup_failed = True
            finally:
                if proc and proc.poll() is None:
                    try:
                        proc.kill()
                        proc.wait(timeout=5)
                    except (OSError, subprocess.TimeoutExpired):
                        cleanup_failed = True
            if cleanup_failed:
                message = (
                    f"PDF container cleanup could not be confirmed for {name}. Start Docker "
                    "and confirm that this container has been removed before retrying."
                )
                if failure is not None:
                    message += f" Original failure: {str(failure)[:300]}"
                error = CandidateError("cleanup_unresolved", message)
                error.container_name = name
                error.docker_endpoint = endpoint
                raise error from failure

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
