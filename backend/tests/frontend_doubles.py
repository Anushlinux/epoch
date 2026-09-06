"""Deterministic browser providers ONLY; real storage, orchestration and evaluators.

No generated source is executed. These doubles are never production imports.
Task marker [needs-input] asks for clarification; [reject-repair] rejects both
candidates. Ordinary repairs reject candidate one and accept candidate two.
"""

import json
import re

from test_supervision import ModelHarness, ready_plan

from epoch_backend import (
    candidate_runner,
    debugger_bridge,
    execution_api,
    hermes_bridge,
    repair_controller,
    supervisor,
)
from epoch_backend.sandbox import Sandbox
from epoch_backend.tool_registry import ToolRegistry

IMAGE = "sha256:" + "a" * 64
SOURCE = (
    "def serialize_checklist(ticket_id, title, items, *, legacy=False):\n"
    '    return {"ticket_id": ticket_id, "title": title, "items": items}\n'
)
REJECTED_SOURCE = "# browser-test-rejected-candidate\n" + SOURCE


def _delay(cancelled, seconds):
    if cancelled.wait(seconds):
        return False
    return True


class BrowserSession:
    """Explicit executor double with real business tool calls and stable identity."""

    def __init__(self, request, on_event, cancelled, before_model_request=None):
        self.request = request
        self.on_event = on_event
        self.cancelled = cancelled
        self.before_model_request = before_model_request
        self.passes = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def account_verification_pause(self, seconds):
        assert seconds >= 0

    def run(self, instruction, max_turns, timeout_seconds):
        assert 1 <= max_turns <= 20 and 1 <= timeout_seconds <= 600
        if self.before_model_request:
            self.before_model_request()
        self.passes += 1
        self.on_event(
            {
                "type": "executor.message",
                "data": {"content": "Browser test executor started.", "test_double": True},
            }
        )
        if not _delay(self.cancelled, 0.8):
            return {"success": False, "final_response": "Browser test executor cancelled."}
        args = self.request["mcp_args"]
        sandbox = Sandbox(
            args[args.index("--database") + 1],
            self.request["task_id"],
            self.request["run_id"],
        )
        ToolRegistry(sandbox).discover_tools()
        ModelHarness.perform(
            sandbox,
            self.on_event,
            omit="do not send any QA message this pass" in instruction,
        )
        baseline = {key: "browser-test-double-stable-identity" for key in supervisor.BASELINE_KEYS}
        baseline.update(
            implementation_unchanged=True,
            user_settings_unchanged=True,
            system_prompt_unchanged=True,
            system_prompt_static_unchanged=True,
            discovery_unchanged=True,
            test_double=True,
        )
        return {
            "success": True,
            "final_response": "Browser test executor finished; no actual model invocation.",
            "baseline": baseline,
            # Completeness within this explicit harness is distinct from live acceptance.
            "missing_evidence": [],
            "test_double": "Browser providers; no actual Hermes, Luna or Docker.",
            "turns_used": 1,
            "session_turns_used": self.passes,
            "history_retained": True,
            "api_calls": 1,
            "segment": self.passes,
        }


class BrowserDebugger:
    def __init__(self):
        self.reject_repair = False

    def complete(self, request, on_event, cancelled):
        payload = request["input"]
        on_event(
            {"type": "debugger.started", "data": {"model": "gpt-5.6-luna", "test_double": True}}
        )
        if not _delay(cancelled, 0.2):
            return {"success": False, "error": {"code": "cancelled", "message": "Cancelled."}}
        if "signature" in payload and "evidence" in payload:
            output = {
                "answer": (
                    "Explicit browser test analysis: the saved checklist error "
                    "is linked to this incident."
                ),
                "evidence_ids": [item["id"] for item in payload["evidence"][:2]],
                "hypotheses": ["Test analysis only; no live Luna request occurred."],
                "missing_evidence": [],
            }
        elif "observed_failure" in payload:
            bad = self.reject_repair or not payload["rejected_attempts"]
            output = {
                "outcome": "repair",
                "diagnosis": "Browser test diagnosis: checklist items were stringified.",
                "evidence_ids": [payload["observed_failure"]["id"]],
                "target": "checklist_serializer.py",
                "source": REJECTED_SOURCE if bad else SOURCE,
                "uncertainty": "Explicit browser fixture; not an actual generated repair.",
            }
        elif "trusted_verification" in payload:
            blocked = bool(payload["tool_errors"])
            output = {
                "action": "environment_defect" if blocked else "continue",
                "reason": "Observed tool defect." if blocked else "The QA checkpoint is unmet.",
                "instruction": "Complete the missing QA notice using existing objects.",
                "questions": [],
            }
        else:
            text = payload["current_input"]
            self.reject_repair = "[reject-repair]" in payload["original_request"]
            output = ready_plan()
            if payload["required_workflow"].get("require_qa_owner"):
                output["checkpoints"].append(
                    {"kind": "qa_owner", "description": "Identify QA owner.", "source_quote": ""}
                )
            if "[needs-input]" in text:
                output.update(
                    outcome="needs_input",
                    summary="Please specify the additional release requirement.",
                    questions=["Which checklist item should be added?"],
                )
            else:
                items = re.findall(r"[Aa]dd checklist item ['\"]([^'\"]+)['\"]", text)
                phrases = re.findall(r"[Ii]nclude ['\"]([^'\"]+)['\"] in the QA message", text)
                if "Security review approved" in text:
                    items.append("Security review approved")
                if "Deployment starts at 10:00 UTC" in text:
                    phrases.append("Deployment starts at 10:00 UTC")
                for field, values in (
                    ("additional_checklist_items", items),
                    ("required_message_phrases", phrases),
                ):
                    output[field] = [
                        {"value": value, "source_quote": value} for value in dict.fromkeys(values)
                    ]
                if payload["trigger"] != "initial":
                    output["classification"] = "new_preference"
        on_event(
            {"type": "debugger.completed", "data": {"model": "gpt-5.6-luna", "test_double": True}}
        )
        return {
            "success": True,
            "output": output,
            "model": "gpt-5.6-luna",
            "provider": "browser-test-double",
            "usage": {},
            "baseline": {"response_model": "gpt-5.6-luna", "test_double": True},
            "missing_evidence": ["No actual debugger inference."],
            "error": None,
        }


def inspect_runner(*_, **__):
    return {
        "available": True,
        "image_id": IMAGE,
        "runner_version": "browser-test-double",
        "test_double": True,
    }


def run_candidate(self, source, arguments, **kwargs):
    """Data mapping only. Never eval/exec/import the supplied source."""
    data = {key: value for key, value in arguments.items() if key != "legacy"}
    if source.startswith("# browser-test-rejected-candidate"):
        data["items"] = json.dumps(data["items"])
    return data


def install(set_attribute=setattr):
    """Install only in the dedicated browser server or a restoring pytest fixture."""
    debugger = BrowserDebugger()
    set_attribute(hermes_bridge, "Session", BrowserSession)
    set_attribute(
        hermes_bridge, "detect_installation", lambda: {"available": True, "test_double": True}
    )
    set_attribute(
        debugger_bridge, "detect_debugger", lambda: {"available": True, "test_double": True}
    )
    set_attribute(debugger_bridge, "complete", debugger.complete)
    set_attribute(candidate_runner.CandidateRunner, "run", run_candidate)
    set_attribute(repair_controller, "inspect_runner", inspect_runner)
    set_attribute(execution_api, "inspect_runner", inspect_runner)
    set_attribute(
        repair_controller,
        "isolation_proof",
        lambda *_: {"kind": "isolation", "passed": True, "test_double": True},
    )
    return debugger
