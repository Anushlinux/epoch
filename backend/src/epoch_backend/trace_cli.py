"""Read-only CLI clients for the running trace collector."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener


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


def handle_trace_command(args, settings):
    if args.command == "traces":
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
    request = Request(f"http://{host}:{settings.port}{path}")
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=15) as response:
            print(json.dumps(json.load(response), indent=2, ensure_ascii=True))
            return 0
    except HTTPError as exc:
        print(exc.read(8192).decode("utf-8", errors="replace"))
    except (URLError, TimeoutError):
        print("Local trace API unavailable. Start epoch-backend serve --profile trace-debugger.")
    return 1
