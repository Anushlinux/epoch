"""Execute generated serializers only in a restricted Linux Docker container.

No host mounts or credentials enter the container. The parent trusts only a bounded
JSON payload, which the business service validates independently. Container exit
and stdout never constitute a passing verification result.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from uuid import uuid4

DEFAULT_IMAGE = (
    "python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
)
RUNNER_VERSION = "docker-serializer-v1"
MAX_SOURCE_BYTES = 20_000
MAX_OUTPUT_BYTES = 65_536
BOOTSTRAP = """import json, sys, resource
resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
payload = json.load(sys.stdin)
namespace = {"__name__": "epoch_candidate"}
exec(compile(payload["source"], "checklist_serializer.py", "exec"), namespace)
result = namespace["serialize_checklist"](**payload["arguments"])
print(json.dumps(result, allow_nan=False))
"""


class CandidateError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def _environment():
    # Docker's existing local context is read by its CLI; do not forward provider
    # tokens or allow environment variables to redirect the daemon remotely.
    names = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in names}


def _docker(arguments: list[str], *, timeout: float = 10) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["docker", *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_environment(),
            timeout=timeout,
            check=False,
            **_options(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CandidateError(
            "runner_unavailable", "Local Docker command did not complete."
        ) from exc


def inspect_runner(image: str = DEFAULT_IMAGE, *, timeout: float = 30) -> dict:
    result = {"available": False, "image": image, "runner_version": RUNNER_VERSION}
    if not re.fullmatch(r"[A-Za-z0-9._/:-]+@sha256:[a-f0-9]{64}", image):
        return {**result, "error": "A digest-pinned image is required."}
    if shutil.which("docker") is None:
        return {**result, "error": "Install and start Linux Docker; no host execution fallback."}
    deadline = time.monotonic() + timeout

    def bounded(arguments):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CandidateError("runner_unavailable", "Runner inspection deadline reached.")
        return _docker(arguments, timeout=min(10, remaining))

    try:
        context = bounded(["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"])
        if context.returncode or not context.stdout.strip().startswith(("npipe://", "unix://")):
            raise CandidateError("runner_unavailable", "A local Docker daemon is required.")
        info = bounded(["info", "--format", "{{json .}}"])
        metadata = json.loads(info.stdout) if info.returncode == 0 else {}
        if metadata.get("OSType") != "linux":
            raise CandidateError("runner_unavailable", "Start Docker with its Linux engine.")
        if not any("seccomp" in str(item) for item in metadata.get("SecurityOptions", [])):
            raise CandidateError("runner_unavailable", "Docker default seccomp must be enabled.")
        found = bounded(["image", "inspect", image, "--format", "{{.Id}}"])
        if found.returncode or not re.fullmatch(r"sha256:[a-f0-9]{64}", found.stdout.strip()):
            raise CandidateError(
                "runner_unavailable", "Pull the configured pinned image during setup."
            )
        return {
            **result,
            "available": True,
            "image_id": found.stdout.strip(),
            "engine_version": metadata.get("ServerVersion"),
            "local_daemon": True,
        }
    except (CandidateError, ValueError) as exc:
        return {**result, "error": str(exc)}


class CandidateRunner:
    def __init__(self, image_id: str):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
            raise CandidateError("invalid_image", "Runner requires an immutable local image ID.")
        self.image_id = image_id

    def run(
        self,
        source: str,
        arguments: dict,
        *,
        timeout: float = 12,
        cancelled: threading.Event | None = None,
    ) -> dict:
        if not isinstance(source, str) or not 0 < len(source.encode()) <= MAX_SOURCE_BYTES:
            raise CandidateError("invalid_candidate", "Candidate source exceeds its allowed size.")
        payload = json.dumps({"source": source, "arguments": arguments}, allow_nan=False).encode()
        if len(payload) > 100_000:
            raise CandidateError("invalid_candidate", "Candidate input exceeds its allowed size.")
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or timeout <= 0
            or (cancelled and cancelled.is_set())
        ):
            raise CandidateError("cancelled", "Candidate execution was not started.")
        deadline = time.monotonic() + min(timeout, 20)
        name = f"epoch-candidate-{uuid4().hex}"
        process = None
        reader = None
        writer = None
        attempted = False
        context = _docker(
            ["context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            timeout=max(0.1, deadline - time.monotonic()),
        )
        endpoint = context.stdout.strip()
        if context.returncode or not endpoint.startswith(("npipe://", "unix://")):
            raise CandidateError("runner_unavailable", "A local Docker daemon is required.")

        def local_docker(arguments, **kwargs):
            return _docker(["--host", endpoint, *arguments], **kwargs)

        try:
            attempted = True
            creation = local_docker(
                [
                    "create",
                    "--pull=never",
                    "--name",
                    name,
                    "--label",
                    "epoch.candidate=true",
                    "--network=none",
                    "--read-only",
                    "--user=65534:65534",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true",
                    "--memory=128m",
                    "--memory-swap=128m",
                    "--cpus=0.5",
                    "--pids-limit=16",
                    "--ulimit=nofile=64:64",
                    "--ulimit=fsize=65536:65536",
                    "--tmpfs=/tmp:rw,noexec,nosuid,size=16777216",
                    "--log-driver=none",
                    "--workdir=/tmp",
                    "--interactive",
                    "--entrypoint=/usr/bin/timeout",
                    self.image_id,
                    "--signal=KILL",
                    "5",
                    "python",
                    "-I",
                    "-S",
                    "-c",
                    BOOTSTRAP,
                ],
                timeout=max(0.1, deadline - time.monotonic()),
            )
            if creation.returncode:
                raise CandidateError("runner_unavailable", "Restricted container creation failed.")
            inspection = local_docker(
                ["inspect", name], timeout=max(0.1, deadline - time.monotonic())
            )
            config = json.loads(inspection.stdout)[0]
            host = config["HostConfig"]
            if not (
                host["ReadonlyRootfs"]
                and host["NetworkMode"] == "none"
                and not host["Privileged"]
                and host["CapDrop"] == ["ALL"]
                and config["Config"]["User"] == "65534:65534"
                and host["Memory"] == 134217728
                and host["MemorySwap"] == 134217728
                and host["PidsLimit"] == 16
                and not host.get("Binds")
                and not any(mount.get("Type") == "bind" for mount in config.get("Mounts", []))
                and "no-new-privileges:true" in host["SecurityOpt"]
                and config["Image"] == self.image_id
            ):
                raise CandidateError(
                    "isolation_unverified", "Container restrictions differ from policy."
                )
            output = queue.Queue(maxsize=20)
            stop_reader = threading.Event()

            def read_output():
                while not stop_reader.is_set():
                    data = process.stdout.read(4096)
                    while not stop_reader.is_set():
                        try:
                            output.put(data, timeout=0.05)
                            break
                        except queue.Full:
                            continue
                    if not data:
                        break

            process = subprocess.Popen(
                ["docker", "--host", endpoint, "start", "--attach", "--interactive", name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=_environment(),
                **_options(),
            )
            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()

            def write_input():
                try:
                    process.stdin.write(payload)
                    process.stdin.close()
                except OSError:
                    pass

            writer = threading.Thread(target=write_input, daemon=True)
            writer.start()
            chunks = bytearray()
            while True:
                if (cancelled and cancelled.is_set()) or time.monotonic() >= deadline:
                    raise CandidateError(
                        "candidate_timeout", "Candidate stopped at its external limit."
                    )
                try:
                    data = output.get(timeout=0.05)
                except queue.Empty:
                    continue
                if not data:
                    break
                chunks.extend(data)
                if len(chunks) > MAX_OUTPUT_BYTES:
                    raise CandidateError(
                        "candidate_output_limit", "Candidate output limit exceeded."
                    )
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
            final = local_docker(
                ["inspect", "--format", "{{.State.ExitCode}}", name],
                timeout=max(0.1, deadline - time.monotonic()),
            )
            if process.returncode or final.returncode or final.stdout.strip() != "0":
                raise CandidateError(
                    "candidate_failed", "Candidate exited without a valid payload."
                )
            value = json.loads(chunks)
            if not isinstance(value, dict):
                raise ValueError("object required")
            return value
        except (OSError, ValueError, subprocess.TimeoutExpired, IndexError, KeyError) as exc:
            raise CandidateError(
                "candidate_failed", "Candidate did not return one valid JSON object."
            ) from exc
        finally:
            cleanup_error = None
            try:
                if attempted:
                    cleanup = local_docker(["rm", "--force", name])
                    if cleanup.returncode and "No such container" not in cleanup.stderr:
                        cleanup_error = CandidateError(
                            "cleanup_unresolved", "Restricted container cleanup failed."
                        )
            except CandidateError as exc:
                cleanup_error = CandidateError("cleanup_unresolved", str(exc))
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=5)
                    stop_reader.set()
                    if reader:
                        reader.join(timeout=2)
                    if writer:
                        writer.join(timeout=2)
                    if process.stdout:
                        process.stdout.close()
            if cleanup_error:
                raise cleanup_error
