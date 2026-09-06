"""Actual Neatlogs SDK -> loopback Epoch OTLP collector, without cloud or model calls.

Run: uv run python scripts/smoke_neatlogs.py
Uses temporary storage and an ephemeral local ingestion token. No existing data or
credentials are changed. The collector's ordinary normalization boundary is exercised.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import uvicorn
from fastapi import FastAPI

from epoch_backend.telemetry import TelemetryService
from epoch_backend.telemetry_api import telemetry_router


class Sink:
    def __init__(self):
        self.records = {}

    def ingest_evidence(self, records):
        for record in records:
            self.records[record["source_id"]] = record


def main():
    token = secrets.token_urlsafe(24)
    previous = os.environ.get("EPOCH_TELEMETRY_TOKEN")
    os.environ["EPOCH_TELEMETRY_TOKEN"] = token
    with tempfile.TemporaryDirectory(prefix="epoch-neatlogs-smoke-") as directory:
        sink = Sink()
        settings = SimpleNamespace(
            data_dir=Path(directory), telemetry_enabled=True, neatlogs_cloud_enabled=False
        )
        service = TelemetryService(settings, sink)
        if previous is None:
            os.environ.pop("EPOCH_TELEMETRY_TOKEN", None)
        else:
            os.environ["EPOCH_TELEMETRY_TOKEN"] = previous
        service.initialize()
        app = FastAPI()
        app.include_router(telemetry_router(service))
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="off"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.05)
            if not server.started:
                raise RuntimeError("Local collector failed to start")
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("NEATLOGS_", "OTEL_"))
            }
            env["SMOKE_ENDPOINT"] = f"http://127.0.0.1:{port}"
            env["SMOKE_TOKEN"] = token
            script = """
import os
import neatlogs
neatlogs.init(api_key=os.environ["SMOKE_TOKEN"], endpoint=os.environ["SMOKE_ENDPOINT"],
              workflow_name="epoch-sdk-smoke", instrumentations=[],
              register_shutdown_handlers=False, uploads_enabled=False)
with neatlogs.trace("epoch-sdk-smoke", kind="WORKFLOW") as root:
    root.set_attribute("epoch.project_id", "smoke")
    with neatlogs.trace("smoke-checklist", kind="TOOL") as child:
        child.set_attribute("tool.name", "checklist")
        child.set_attribute("epoch.project_id", "smoke")
neatlogs.flush()
neatlogs.shutdown()
"""
            result = subprocess.run(
                [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=40
            )
            if result.returncode:
                raise RuntimeError("Neatlogs SDK child failed: " + result.stderr[-1000:])
            runtime = service.runtime_info()
            names = {record["text"] for record in sink.records.values()}
            if not {"epoch-sdk-smoke", "smoke-checklist"}.issubset(names):
                raise RuntimeError(f"Expected both named SDK spans, received {runtime}")
            print(
                json.dumps(
                    {
                        "result": "passed",
                        "sdk_spans": runtime["stored_spans"],
                        "normalized_evidence": len(sink.records),
                        "cloud_export": "disabled",
                        "model_calls": 0,
                    }
                )
            )
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            listener.close()
            service.close()


if __name__ == "__main__":
    main()
