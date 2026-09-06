"""Small local setup and server harness."""

import argparse
import sqlite3
import sys
from pathlib import Path

import uvicorn
from pydantic import ValidationError
from pydantic_settings import SettingsError

from epoch_backend.config import Settings
from epoch_backend.execution import ExecutionError
from epoch_backend.sandbox import SandboxError
from epoch_backend.storage import SQLiteStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="epoch-backend", description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Explicit .env configuration file")
    subparsers = parser.add_subparsers(dest="command", required=True)
    # Intake and explicit workflow commands share validated local configuration.
    subparsers.add_parser("check-config", help="Validate settings without creating storage")
    subparsers.add_parser("init-db", help="Initialize durable local task storage")
    subparsers.add_parser("serve", help="Start the local intake and execution API")
    from epoch_backend.workflow_cli import add_commands

    add_commands(subparsers)
    args = parser.parse_args(argv)

    try:
        if args.env_file is not None and not args.env_file.is_file():
            parser.error("--env-file must refer to an existing file")
        settings = Settings(_env_file=args.env_file)
    except ValidationError as exc:
        print("Invalid configuration:", file=sys.stderr)
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"])
            print(f"  {field}: {error['msg']}", file=sys.stderr)
        return 2
    except (SettingsError, OSError, ValueError) as exc:
        print(f"Invalid configuration: {exc}", file=sys.stderr)
        return 2

    if args.command == "check-config":
        print(settings.model_dump_json(indent=2))
        return 0
    try:
        if args.command in {"hermes-info", "sandbox", "run-release"}:
            from epoch_backend.workflow_cli import handle_command

            return handle_command(args, settings)
        if args.command == "init-db":
            SQLiteStore(settings.database_path).initialize()
            print(f"Storage ready: {settings.database_path}")
        else:
            from epoch_backend.app import create_app

            # Preflight makes common storage failures actionable before server startup.
            SQLiteStore(settings.database_path).initialize()
            uvicorn.run(
                create_app(settings),
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level,
            )
    except (OSError, sqlite3.Error) as exc:
        print(f"Storage initialization failed: {exc}", file=sys.stderr)
        return 1
    except (ExecutionError, SandboxError) as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as exc:
        print(f"Command failed: {exc}", file=sys.stderr)
        return 2
    return 0
