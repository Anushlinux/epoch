"""Incident CLI using the running API, without competing for its execution lease."""

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID


def add_incident_arguments(subparsers):
    listing = subparsers.add_parser("incidents", help="List saved incidents")
    listing.add_argument("--project-id")
    for name in ("incident", "evidence"):
        subparsers.add_parser(name, help="Inspect saved evidence").add_argument("id")
    importing = subparsers.add_parser("import-evidence", help="Import local Slack/support JSON")
    importing.add_argument("file", type=Path)
    importing.add_argument("--request-id", default=None)
    for name in ("analyze-incident", "ask-incident"):
        parser = subparsers.add_parser(name, help="Request one bounded Luna incident analysis")
        parser.add_argument("id")
        parser.add_argument("--request-id", required=True, help="UUID retained for safe retries")
        if name == "ask-incident":
            parser.add_argument("question")
    subparsers.add_parser("telemetry-info", help="Inspect collector/export status")


def handle_incident_command(args, settings):
    command, payload = args.command, None
    if command == "incidents":
        path = "/api/incidents" + (
            "?" + urlencode({"project_id": args.project_id}) if args.project_id else ""
        )
    elif command == "incident":
        path = "/api/incidents/" + args.id
    elif command == "evidence":
        path = "/api/evidence/" + args.id
    elif command == "telemetry-info":
        path = "/api/telemetry/runtime"
    elif command == "import-evidence":
        source = json.loads(args.file.read_text())
        payload = source if isinstance(source, dict) else {"records": source}
        embedded_id = payload.get("client_request_id")
        if args.request_id and embedded_id and str(UUID(args.request_id)) != str(UUID(embedded_id)):
            raise ValueError("--request-id differs from the JSON client_request_id")
        identity = args.request_id or embedded_id
        if not identity:
            raise ValueError("Supply --request-id UUID or include client_request_id in the JSON")
        payload["client_request_id"] = str(UUID(identity))
        path = "/api/evidence/import"
    else:
        path = f"/api/incidents/{args.id}/" + (
            "questions" if command == "ask-incident" else "analyze"
        )
        payload = {"client_request_id": args.request_id}
        if command == "ask-incident":
            payload["question"] = args.question
    if payload:
        payload["client_request_id"] = str(UUID(payload["client_request_id"]))
        print(f"Retained request ID: {payload['client_request_id']}", file=sys.stderr)
    host = "[::1]" if settings.host == "::1" else settings.host
    request = Request(
        f"http://{host}:{settings.port}{path}",
        data=json.dumps(payload).encode() if payload else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=65) as response:
            print(json.dumps(json.load(response), indent=2))
            return 0
    except HTTPError as error:
        print(error.read().decode())
        return 1
    except URLError:
        print(
            "Local Epoch API unavailable. Start epoch-backend serve first; no request was retried."
        )
        return 1
