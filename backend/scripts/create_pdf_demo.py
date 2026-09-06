"""Create a fresh PDF demonstration project through the running local API; no model calls."""

import argparse
import json
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--pack", choices=["retreat", "festival"], default="retreat")
    parser.add_argument("--request-id", type=UUID, default=None)
    args = parser.parse_args()
    origin = urlsplit(args.api)
    if origin.scheme != "http" or origin.hostname not in {"127.0.0.1", "localhost"}:
        parser.error("Use the running local HTTP API")
    identity = args.request_id or uuid4()
    print(f"Request identity (reuse for an uncertain retry): {identity}", flush=True)
    with httpx.Client(base_url=args.api, timeout=120, follow_redirects=False) as client:
        response = client.post(
            "/api/chats",
            json={
                "client_request_id": str(identity),
                "environment": "pdf_workshop",
                "project_id": "pdf-demo-" + str(identity),
            },
        )
        response.raise_for_status()
        chat = response.json()
        response = client.post(f"/api/chats/{chat['id']}/assets/bundled", json={"pack": args.pack})
        response.raise_for_status()
        if not response.json().get("ok"):
            raise RuntimeError(json.dumps(response.json()))
    print(f"Fresh project: {chat['project_id']}")
    print(f"Open http://127.0.0.1:5173/chat?chat={chat['id']}")
    print("Files added. No model was called; existing projects and evidence were preserved.")


if __name__ == "__main__":
    main()
