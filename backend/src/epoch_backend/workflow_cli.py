"""Developer sandbox commands and explicit actual-Hermes release execution."""

import json
import time
from uuid import UUID, uuid4

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.config import Settings
from epoch_backend.contracts import TaskCreate
from epoch_backend.execution import TERMINAL, ExecutionService
from epoch_backend.execution_contracts import ReleaseRunRequest
from epoch_backend.sandbox import Sandbox, SandboxError
from epoch_backend.storage import SQLiteStore
from epoch_backend.supervision_contracts import FeedbackRequest
from epoch_backend.tool_registry import ToolRegistry

SCENARIOS = ["control", "broken_checklist", "missing_lookup", "outdated_context"]


def add_commands(subparsers):
    subparsers.add_parser("hermes-info", help="Inspect the existing Hermes installation safely")
    subparsers.add_parser("debugger-info", help="Inspect the configured OpenAI debugger route")
    subparsers.add_parser("repair-info", help="Inspect the local Linux container repair runner")
    for name in ("environment", "rollback-environment"):
        command = subparsers.add_parser(name)
        command.add_argument("--project", default="demo")
        if name == "rollback-environment":
            command.add_argument("--expected-version", type=UUID, required=True)
            command.add_argument("--request-id", type=UUID, required=True)
    sandbox = subparsers.add_parser("sandbox", help="Operate explicitly labelled local simulations")
    actions = sandbox.add_subparsers(dest="action", required=True)
    initialize = actions.add_parser("init")
    initialize.add_argument("--scenario", choices=SCENARIOS, default="control")
    initialize.add_argument("--project", default="demo")
    initialize.add_argument("--release", default="1.0")
    for action in ["discover", "describe", "invoke", "state", "events", "check", "reset"]:
        command = actions.add_parser(action)
        command.add_argument("sandbox_id", type=UUID)
        if action in {"describe", "invoke"}:
            command.add_argument("tool")
        if action == "invoke":
            command.add_argument(
                "--arguments", required=True, help="JSON object matching tool schema"
            )
    run = subparsers.add_parser("run-release", help="Execute a release template with actual Hermes")
    run.add_argument(
        "--message", default="Prepare this release, its checklist and the QA notification."
    )
    run.add_argument("--project", default="demo")
    run.add_argument("--release", default="1.0")
    run.add_argument("--scenario", choices=SCENARIOS, default="control")
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--max-turns", type=int, default=20)
    run.add_argument("--supervised", action="store_true", help="Enable the OpenAI debugger")
    run.add_argument(
        "--repair", action="store_true", help="Enable supervised generated checklist repair"
    )
    run.add_argument(
        "--demo-omit-notification",
        action="store_true",
        help="Demonstrate supervised recovery of an initially omitted QA notification",
    )
    for name in ("feedback", "clarify"):
        command = subparsers.add_parser(name, help="Submit explicit input to a supervised run")
        command.add_argument("run_id", type=UUID)
        command.add_argument("--message", required=True)
        command.add_argument("--expected-revision", type=UUID, required=True)
        command.add_argument("--request-id", type=UUID, help="Reuse this ID for an identical retry")
        command.add_argument("--max-turns", type=int, default=20)
        command.add_argument("--timeout", type=int, default=600)


def handle_command(args, settings: Settings) -> int:
    if args.command == "repair-info":
        from epoch_backend.candidate_runner import inspect_runner

        result = inspect_runner(settings.repair_image)
        print(json.dumps(result, indent=2))
        return 0 if result["available"] else 1
    if args.command in {"hermes-info", "debugger-info"}:
        result = (
            debugger_bridge.detect_debugger()
            if args.command == "debugger-info"
            else hermes_bridge.detect_installation()
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("available") else 1
    if args.command == "sandbox":
        sandbox_id = uuid4() if args.action == "init" else args.sandbox_id
        path = settings.data_dir / "sandboxes" / str(sandbox_id) / "sandbox.sqlite3"
        sandbox = Sandbox(path, task_id=str(sandbox_id), run_id=str(sandbox_id))
        if args.action != "init" and not path.is_file():
            raise SandboxError("not_found", "Sandbox does not exist.")
        if args.action == "init":
            sandbox.initialize(
                scenario=args.scenario, project_id=args.project, release=args.release
            )
            result = {"sandbox_id": str(sandbox_id), "simulation_only": True}
        elif args.action == "reset":
            metadata = sandbox.metadata()
            sandbox.reset(
                scenario=metadata["scenario"],
                project_id=metadata["project_id"],
                release=metadata["release"],
                grants=metadata["grants"],
            )
            result = {"sandbox_id": str(sandbox_id), "reset": True}
        elif args.action == "state":
            result = sandbox.snapshot()
        elif args.action == "events":
            result = sandbox.events()
        elif args.action == "check":
            result = sandbox.evaluate()
        else:
            registry = ToolRegistry(sandbox)
            if args.action == "discover":
                result = registry.discover_tools()
            elif args.action == "describe":
                result = registry.describe_tool(args.tool)
            else:
                arguments = json.loads(args.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("--arguments must contain a JSON object")
                result = registry.invoke_tool(args.tool, arguments)
        print(json.dumps(result, indent=2))
        if isinstance(result, dict) and (
            result.get("ok") is False or result.get("passed") is False
        ):
            return 1
        return 0

    tasks = SQLiteStore(settings.database_path)
    tasks.initialize()
    service = ExecutionService(settings, tasks)
    service.initialize()
    record = None
    try:
        if args.command in {"environment", "rollback-environment"}:
            result = (
                service.environments.inspect(args.project)
                if args.command == "environment"
                else service.rollback(args.project, str(args.expected_version), args.request_id)
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command in {"feedback", "clarify"}:
            feedback = FeedbackRequest(
                client_request_id=args.request_id or uuid4(),
                expected_revision_id=args.expected_revision,
                message=args.message,
                max_turns=args.max_turns,
                timeout_seconds=args.timeout,
            )
            record, _ = service.feedback(
                args.run_id, feedback, clarification=args.command == "clarify"
            )
        else:
            request = ReleaseRunRequest(
                client_request_id=uuid4(),
                workflow="release",
                release=args.release,
                scenario=args.scenario,
                max_turns=args.max_turns,
                timeout_seconds=args.timeout,
                supervised=args.supervised or args.repair,
                repair_enabled=args.repair,
                demo_omit_notification=args.demo_omit_notification,
            )
            task, _ = tasks.create_task(
                TaskCreate(client_request_id=uuid4(), message=args.message, project_id=args.project)
            )
            record, _ = service.start(task.id, request)
        while (record := service.get(record.id)).status not in TERMINAL:
            time.sleep(0.2)
        print(record.model_dump_json(indent=2))
        return 0 if record.status == "completed" else 1
    except KeyboardInterrupt:
        if record is not None:
            service.cancel(record.id)
        return 130
    finally:
        service.close()
