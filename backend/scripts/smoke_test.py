"""Exercise the actual CLI/HTTP server and restart against a temporary database."""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx


@contextmanager
def server(data_dir: Path):
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
    env = {key: value for key, value in os.environ.items() if not key.startswith("EPOCH_")}
    env.update(EPOCH_DATA_DIR=str(data_dir), EPOCH_PORT=str(port))
    process = subprocess.Popen(
        [sys.executable, "-m", "epoch_backend", "serve"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False
        ) as client:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Server exited before becoming ready: {process.returncode}")
                try:
                    health = client.get("/api/health")
                    health.raise_for_status()
                    assert health.json()["execution_enabled"] is False
                    break
                except httpx.TransportError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError(
                            "Server did not become ready within 15 seconds"
                        ) from None
                    time.sleep(0.1)
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main() -> None:
    with TemporaryDirectory(prefix="epoch-smoke-") as directory:
        data_dir = Path(directory)
        payload = {"client_request_id": str(uuid4()), "message": "Persist this smoke-test task"}
        with server(data_dir) as client:
            created = client.post("/api/tasks", json=payload)
            assert created.status_code == 201, created.text
            task = created.json()
            assert task["status"] == "pending"
            assert client.post("/api/tasks", json=payload).status_code == 200
            assert client.get("/api/tasks").json()["total"] == 1
        with server(data_dir) as client:
            assert client.get(f"/api/tasks/{task['id']}").json() == task
            assert client.post("/api/tasks", json=payload).status_code == 200
        print("PASS: CLI server health, HTTP intake, idempotency and persisted task after restart.")


if __name__ == "__main__":
    main()
