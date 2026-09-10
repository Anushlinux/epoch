"""Trace inspection and explicitly submitted local questions over the HTTP API."""

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4


def add_trace_arguments(subparsers):
    listing = subparsers.add_parser("traces", help="Search locally stored traces")
    for name in ("project-id", "workflow", "session-id", "q", "started-after", "started-before"):
        listing.add_argument("--" + name)
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)
    detail = subparsers.add_parser("trace", help="Inspect a trace or one span")
    detail.add_argument("trace_id")
    detail.add_argument("--span-id")
    detail.add_argument("--raw", action="store_true", help="Read original OTLP; requires --span-id")
    detail.add_argument("--limit", type=int, default=200)
    detail.add_argument("--offset", type=int, default=0)
    ask = subparsers.add_parser("ask-trace", help="Ask local Ollama about one trace")
    ask.add_argument("trace_id")
    ask.add_argument("question")
    ask.add_argument("--span-id", help="Prioritize this span and its context")
    ask.add_argument("--request-id", help="Reuse the original UUID after an uncertain submission")
    history = subparsers.add_parser("trace-questions", help="Read saved questions without calling a model")
    history.add_argument("trace_id")
    history.add_argument("--question-id")
    history.add_argument("--limit", type=int, default=5)
    history.add_argument("--offset", type=int, default=0)
    subparsers.add_parser("trace-model-info", help="Read local model configuration; no Ollama request")
    noise = subparsers.add_parser("noise", help="Inspect noise findings or explicitly submit a context-policy action")
    noise.add_argument("chat_id")
    noise.add_argument("action", choices=["workspace", "record", "analyze", "metadata", "draft", "preview", "validate", "activate", "rollback"])
    noise.add_argument("--record-id")
    noise.add_argument("--policy-id")
    noise.add_argument("--json-file", type=Path, help="Exact request JSON, including client_request_id; preserve for safe retries")


def handle_trace_command(args, settings):
    payload = None
    if args.command == "noise":
        path = "/api/chats/" + quote(args.chat_id, safe="") + "/noise"
        if args.action == "record":
            if not args.record_id:
                raise ValueError("--record-id is required")
            path += "/records/" + quote(args.record_id, safe="")
        elif args.action != "workspace":
            if not args.json_file or args.json_file.stat().st_size > 100000:
                raise ValueError("Supply --json-file with a request of at most 100 KB")
            payload = json.loads(args.json_file.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict) or not payload.get("client_request_id"):
                raise ValueError("The request must include its client_request_id")
            if args.action in {"preview", "validate", "activate"}:
                if not args.policy_id:
                    raise ValueError("--policy-id is required")
                path += "/policies/" + quote(args.policy_id, safe="") + {"preview": "/previews", "validate": "/validations", "activate": "/activate"}[args.action]
            else:
                path += {"analyze": "/analyses", "metadata": "/sources/metadata", "draft": "/policies", "rollback": "/rollback"}[args.action]
    elif args.command == "trace-model-info":
        path = "/api/trace-questions/runtime"
    elif args.command in {"ask-trace", "trace-questions"}:
        path = "/api/traces/" + quote(args.trace_id, safe="") + "/questions"
        if args.command == "ask-trace":
            request_id = args.request_id or str(uuid4())
            print(f"Question request ID: {request_id}", file=sys.stderr)
            payload = {"client_request_id": request_id, "question": args.question, "span_id": args.span_id}
        elif args.question_id:
            path += "/" + quote(args.question_id, safe="")
        else:
            path += "?" + urlencode({"limit": args.limit, "offset": args.offset})
    elif args.command == "traces":
        params = {key: getattr(args, key) for key in (
            "project_id", "workflow", "session_id", "q", "started_after", "started_before", "limit", "offset"
        ) if getattr(args, key) is not None}
        path = "/api/traces?" + urlencode(params)
    else:
        path = "/api/traces/" + quote(args.trace_id, safe="")
        if args.raw and not args.span_id:
            raise ValueError("--raw requires --span-id")
        if args.span_id:
            path += "/spans/" + quote(args.span_id, safe="")
            if args.raw:
                path = path.replace("/api/traces/", "/api/telemetry/traces/", 1)
        else:
            path += "?" + urlencode({"limit": args.limit, "offset": args.offset})
    host = "[::1]" if settings.host == "::1" else settings.host
    request = Request(f"http://{host}:{settings.port}{path}",
                      data=json.dumps(payload).encode("utf-8") if payload else None,
                      headers={"Content-Type": "application/json"} if payload else {})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=15) as response:
            print(json.dumps(json.load(response), indent=2, ensure_ascii=True))
            return 0
    except HTTPError as exc:
        print(exc.read(8192).decode("utf-8", errors="replace"))
    except (URLError, TimeoutError):
        print("Local trace API unavailable. Start epoch-backend --env-file .env serve for the complete workspace.")
    return 1
