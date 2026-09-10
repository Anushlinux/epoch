"""Executed Python tools with a deliberately incorrect choice; no model or live refund.

Run explicitly after starting the local collector. This example was authored but
not executed during the Phase 1/2 delivery, at the user's request.
"""

import argparse
import json
import os
from contextlib import contextmanager
from urllib.parse import urlsplit
from uuid import uuid4

import neatlogs


def local_endpoint(value):
    url = urlsplit(value)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}):
        raise argparse.ArgumentTypeError("Use a loopback HTTP origin, such as http://127.0.0.1:8000")
    _ = url.port
    return value.rstrip("/")


@contextmanager
def captured(name, kind, project_id, inputs, *, session_id=None):
    with neatlogs.trace(name, kind=kind, session_id=session_id) as span:
        span.set_attribute("epoch.project_id", project_id)
        span.set_attribute("input.value", json.dumps(inputs))
        if kind == "TOOL":
            span.set_attribute("tool.name", name)
        yield span


def list_invoices(project_id):
    with captured("list_invoices", "TOOL", project_id, {"customer_id": "customer-demo"}) as span:
        invoices = [{"invoice_id": "INV-41", "amount": 25}, {"invoice_id": "INV-42", "amount": 40}]
        span.set_attribute("output.value", json.dumps(invoices))
        return invoices


def select_invoice(project_id, invoices, requested_id):
    with captured("select_invoice", "TOOL", project_id,
                  {"requested_invoice_id": requested_id, "invoices": invoices}) as span:
        # Seeded implementation defect: the function ignores the requested ID.
        selected = invoices[0]
        span.set_attribute("output.value", json.dumps(selected))
        return selected


def refund_invoice(project_id, invoice):
    with captured("refund_invoice", "TOOL", project_id, invoice) as span:
        result = {"invoice_id": invoice["invoice_id"], "status": "simulated_refund_recorded"}
        span.set_attribute("output.value", json.dumps(result))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", type=local_endpoint, default="http://127.0.0.1:8000")
    parser.add_argument("--project-id", default="trace-demo")
    parser.add_argument("--invoice-id", choices=["INV-41", "INV-42"], default="INV-42")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()
    token = os.environ.get("EPOCH_TELEMETRY_TOKEN", "").strip()
    if not token:
        parser.error("Set EPOCH_TELEMETRY_TOKEN to the same local token as the collector process.")
    session_id = args.session_id or str(uuid4())
    neatlogs.init(api_key=token, endpoint=args.endpoint, workflow_name="invoice-refund-example",
                  capture_logs=False, uploads_enabled=False)
    try:
        with captured("Refund invoice", "WORKFLOW", args.project_id,
                      {"request": f"Refund invoice {args.invoice_id}."}, session_id=session_id) as span:
            invoices = list_invoices(args.project_id)
            invoice = select_invoice(args.project_id, invoices, args.invoice_id)
            result = refund_invoice(args.project_id, invoice)
            span.set_attribute("output.value", json.dumps(result))
            context = span.get_span_context()
            trace_id = f"{context.trace_id:032x}"
        print(json.dumps({"trace_id": trace_id, "session_id": session_id, "result": result,
                          "note": "Synthetic data and simulated refund; inspect collector storage to confirm delivery."}, indent=2))
    finally:
        try:
            neatlogs.flush()
        finally:
            neatlogs.shutdown()


if __name__ == "__main__":
    main()
