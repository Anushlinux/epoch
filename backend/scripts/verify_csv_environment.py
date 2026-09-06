"""Reproduce CSV tool outcomes without Hermes, Luna or a network connection."""

import argparse
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from epoch_backend.csv_sandbox import SAMPLE_CSV, CsvRegistry, CsvSandbox


def verify():
    results = []
    with tempfile.TemporaryDirectory(prefix="epoch-csv-proof-") as directory:
        for mode in ("broken", "healthy"):
            identity = str(uuid4())
            sandbox = CsvSandbox(Path(directory) / f"{mode}.sqlite3", identity, identity)
            sandbox.initialize(adapter_mode=mode)
            registry = CsvRegistry(sandbox)
            request = {"csv_text": SAMPLE_CSV, "idempotency_key": "sample-import"}
            first = registry.invoke_tool("customers.import", request)
            retry = registry.invoke_tool("customers.import", request)
            assert first["result"]["id"] == retry["result"]["id"]
            state = sandbox.snapshot()
            assert len(state["customers"]) == (0 if mode == "broken" else 3)
            assert state["verification"]["passed"] is (mode == "healthy")
            results.append({"mode": mode, "first_import": first, "exact_retry": retry, **state})
    return {
        "proof": "Actual local simulated tool execution; no model inference",
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"broken_saved": 0, "healthy_saved": 3, "exact_retries_preserved": True}))
