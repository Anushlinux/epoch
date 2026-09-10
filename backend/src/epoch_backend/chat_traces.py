"""Neatlogs observation of the public chat bridge; no executor instrumentation patches."""

import json
import time


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=str)


def _recorded_tool_error(result):
    """Use explicit tool/MCP error fields, never a guess based on prose."""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except (ValueError, RecursionError):
            return False
    if not isinstance(result, dict):
        return False
    if (result.get("isError") is True or result.get("success") is False
            or result.get("ok") is False or result.get("status") == "error"
            or bool(result.get("error"))):
        return True
    # MCP text results can contain Epoch's structured tool response.
    content = result.get("content")
    return isinstance(content, list) and any(
        isinstance(item, dict) and item.get("type") == "text"
        and _recorded_tool_error(item.get("text")) for item in content
    )


class ChatTraceCapture:
    """Capture failures are visible but never fail/retry the Hermes operation."""

    def __init__(self, telemetry, chat, operation):
        self.telemetry, self.chat, self.operation = telemetry, chat, operation
        self.client = self.root = self.tracer = None
        self.tools = {}
        self.stored = set()
        self.attributes = {}

    def warn(self, message):
        if message not in self.operation.trace_warnings:
            self.operation.trace_warnings.append(message)

    def start(self):
        operation = self.operation
        operation.trace_capture = "unavailable"
        if not self.telemetry.local_capture_ready:
            self.warn("Local trace capture is disabled or unavailable; this message still runs.")
            return
        try:
            from neatlogs import Client
            from opentelemetry.context import Context
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            # No process-global provider, framework patching, log capture or network export.
            self.client = Client(
                api_key="", workflow_name="Hermes chat", disable_export=True,
                capture_logs=False, uploads_enabled=False, endpoint="http://127.0.0.1",
            )
            self.client.tracer_provider.add_span_processor(
                SimpleSpanProcessor(_LocalExporter(self))
            )
            self.tracer = self.client.get_tracer("epoch.chat.hermes")
            self.attributes = {
                "epoch.project_id": self.chat.project_id,
                "epoch.workflow": "Hermes chat",
                "session.id": str(self.chat.id),
                "epoch.chat_id": str(self.chat.id),
                "epoch.chat_operation_id": str(operation.id),
                "epoch.chat_environment": self.chat.environment,
                "epoch.capture.source": "hermes_public_callbacks",
                "epoch.context.policy_id": operation.context_policy_id or "none",
                "epoch.context.policy_revision": operation.context_policy_revision or 0,
                "epoch.context.preview_id": str(operation.context_preview_id or ""),
            }
            message = next(m for m in self.chat.messages if m.operation_id == operation.id)
            self.root = self.tracer.start_span(
                f"Hermes: {message.content[:120]}", context=Context(),
                start_time=int(operation.created_at.timestamp() * 1_000_000_000),
                attributes={
                    **self.attributes,
                    "openinference.span.kind": "WORKFLOW",
                    "input.value": _json({"message": message.content, "visible_history": [
                        {"role": m.role, "content": m.content}
                        for m in self.chat.messages if m.id != message.id and m.agent != "debugger"
                    ]}),
                    # Explicitly absent until finish; prevent SDK root I/O inference.
                    "output.value": "null",
                    "epoch.capture.warning": (
                        "Captured at Epoch's public Hermes callbacks. Model request events and "
                        "reported model identity are included; private prompts, reasoning, "
                        "token usage and individual model responses are not exposed. "
                        "Tool times measure callback observation, not server execution time."
                    ),
                },
            )
            context = self.root.get_span_context()
            operation.trace_id = f"{context.trace_id:032x}"
            operation.trace_span_id = f"{context.span_id:016x}"
            operation.trace_capture = "recording"
        except Exception as exc:
            self.warn(f"Neatlogs capture could not start ({type(exc).__name__}).")

    def event(self, event):
        if self.root is None:
            return
        try:
            from opentelemetry.trace import Status, StatusCode, set_span_in_context

            kind, data = str(event.get("type", "executor.event")), event.get("data", {})
            now = time.time_ns()
            call_id = str(data.get("tool_call_id", ""))
            if kind == "executor.tool_started" and call_id and call_id not in self.tools:
                self.tools[call_id] = self.tracer.start_span(
                    str(data.get("name") or "Hermes tool"),
                    context=set_span_in_context(self.root), start_time=now,
                    attributes={**self.attributes, "openinference.span.kind": "TOOL",
                                "tool.name": str(data.get("name") or "Unknown tool"),
                                "gen_ai.tool.call.id": call_id,
                                "input.value": _json(data.get("arguments"))},
                )
            elif kind == "executor.tool_completed" and call_id in self.tools:
                span = self.tools.pop(call_id)
                span.set_attribute("output.value", _json(data.get("result")))
                span.set_attribute("epoch.tool.completion_observed", True)
                if _recorded_tool_error(data.get("result")):
                    span.set_status(Status(StatusCode.ERROR, "Tool reported a structured error"))
                span.end(end_time=now)
            else:
                # Preserve public events that cannot be paired, without inventing spans.
                self.root.add_event(kind, {"event.payload": _json(data)}, timestamp=now)
                if kind in {"executor.tool_started", "executor.tool_completed"}:
                    self.warn("Some tool callbacks could not be paired; inspect root events.")
            if kind in {"executor.started", "executor.session_ready"}:
                for key, attribute in (("model", "gen_ai.request.model"),
                                       ("provider", "gen_ai.provider.name")):
                    if data.get(key):
                        self.root.set_attribute(attribute, str(data[key]))
            if kind == "executor.error":
                self.root.set_status(Status(StatusCode.ERROR, str(data.get("message", kind))))
        except Exception as exc:
            self.warn(f"A public event could not be traced ({type(exc).__name__}).")

    def finish(self, response):
        try:
            from opentelemetry.trace import Status, StatusCode

            now = time.time_ns()
            for span in self.tools.values():
                span.set_attribute("epoch.tool.completion_observed", False)
                span.set_attribute("epoch.capture.warning", "Tool completion was not observed.")
                span.end(end_time=now)
                self.warn("A tool did not report completion; its result is unavailable.")
            self.tools.clear()
            if self.root is not None:
                self.root.set_attribute("output.value", _json({
                    "response": response, "operation_status": self.operation.status,
                    "error": self.operation.error,
                }))
                self.root.set_attribute("epoch.operation.status", self.operation.status)
                if self.operation.status != "completed" or self.operation.error:
                    self.root.set_status(Status(StatusCode.ERROR, self.operation.status))
                if self.operation.trace_warnings:
                    self.root.add_event("epoch.capture.incomplete", {
                        "warnings": _json(self.operation.trace_warnings),
                    }, timestamp=now)
                self.root.end(end_time=now)
        except Exception as exc:
            self.warn(f"Trace finalization failed ({type(exc).__name__}).")
        finally:
            if self.client is not None:
                try:
                    if not self.client.shutdown(timeout_millis=1000):
                        self.warn("Neatlogs shutdown did not finish; trace evidence may be incomplete.")
                except Exception as exc:
                    self.warn(f"Neatlogs shutdown failed ({type(exc).__name__}).")
            if self.operation.trace_id:
                root_stored = self.operation.trace_span_id in self.stored
                self.operation.trace_capture = (
                    "stored" if root_stored and not self.operation.trace_warnings else "incomplete"
                )
                if not root_stored:
                    self.warn("The root span was not confirmed in local storage.")


class _LocalExporter:
    """SDK exporter protocol. Trusted in-process ingestion; no HTTP/token/cloud hop."""

    def __init__(self, capture):
        self.capture = capture

    def export(self, spans):
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
        from opentelemetry.sdk.trace.export import SpanExportResult

        try:
            for span in spans:
                self.capture.telemetry.ingest_local(encode_spans([span]).SerializeToString())
                self.capture.stored.add(f"{span.context.span_id:016x}")
            return SpanExportResult.SUCCESS
        except Exception as exc:
            reason = getattr(exc, "code", type(exc).__name__)
            self.capture.warn(f"A span could not be stored locally ({reason}).")
            return SpanExportResult.FAILURE

    def shutdown(self):
        pass
