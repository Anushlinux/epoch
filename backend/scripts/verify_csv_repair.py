"""Opt-in real Luna/Hermes CSV repair acceptance in a separate data directory."""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from epoch_backend.app import create_app
from epoch_backend.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Authorize actual configured model calls"
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required; this script uses the configured models")
    if args.data_dir.exists():
        parser.error("Use a new data directory to preserve previous evidence")
    settings = Settings(_env_file=None, data_dir=args.data_dir, telemetry_enabled=False)
    report = {"live": True, "data_dir": str(args.data_dir.resolve()), "operations": []}
    with TestClient(create_app(settings)) as client:

        def create():
            response = client.post(
                "/api/chats",
                json={
                    "client_request_id": str(uuid4()),
                    "environment": "csv_broken",
                    "project_id": "csv-repair-acceptance",
                },
            )
            response.raise_for_status()
            return response.json()["id"]

        def run(chat, endpoint, payload):
            response = client.post(
                f"/api/chats/{chat}/{endpoint}",
                json={
                    "client_request_id": str(uuid4()),
                    **payload,
                },
            )
            response.raise_for_status()
            operation_id = response.json()["id"]
            last = None
            while True:
                operation = client.get(f"/api/chats/{chat}/operations/{operation_id}").json()
                if operation["activity"] != last:
                    print(operation["activity"], flush=True)
                    last = operation["activity"]
                if operation["status"] != "running":
                    report["operations"].append(operation)
                    return operation
                time.sleep(1)

        prompt = (
            "Import the three customers from customers.read_sample. Preserve their names and "
            "email addresses, avoid duplicates, and report the number actually saved. "
            "Use customers.list to verify the result."
        )
        chat = create()
        report["chat_id"] = chat
        run(chat, "messages", {"content": prompt})
        report["before"] = client.get(f"/api/chats/{chat}/environment").json()
        if not any(
            i.get("error", {}).get("code") == "missing_email"
            for i in report["before"]["imports"]
            if i.get("error")
        ):
            report["passed"] = False
            report["limitation"] = "Hermes did not reach the supported service failure."
        else:
            outcome = run(
                chat, "csv-repair", {"question": "Investigate and repair this import failure."}
            )
            report["after"] = client.get(f"/api/chats/{chat}/environment").json()
            repair = (outcome.get("analysis") or {}).get("repair_result", {})
            if repair.get("status") == "published":
                later = create()
                report["later_chat_id"] = later
                run(later, "messages", {"content": prompt})
                report["later"] = client.get(f"/api/chats/{later}/environment").json()
            report["passed"] = bool(
                repair.get("status") == "published"
                and report["after"]["verification"]["passed"]
                and report.get("later", {}).get("verification", {}).get("passed")
                and report["before"]["criteria"] == report["after"]["criteria"]
            )
    destination = args.data_dir / "acceptance.json"
    destination.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "evidence": str(destination)}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
