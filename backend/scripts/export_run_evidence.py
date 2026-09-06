"""Export saved real run evidence; this command never invokes a model or changes outcomes."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from epoch_backend.execution_store import ExecutionStore
from epoch_backend.sandbox import Sandbox

BASELINE_FIELDS = (
    "implementation_commit",
    "implementation_sha256",
    "model_configuration_sha256",
    "system_prompt_initial_sha256",
    "system_prompt_sha256",
    "system_prompt_static_sha256",
    "discovery_sha256",
    "bridge_sha256",
    "evaluator_sha256",
    "permission_grants_sha256",
    "criteria_sha256",
    "brief_sha256",
)


def capture(data_dir: Path) -> list[dict]:
    records = ExecutionStore(data_dir / "executions.sqlite3").list()
    result = []
    for record in records:
        sandbox = Sandbox(
            data_dir / "runs" / str(record.id) / "sandbox.sqlite3",
            str(record.task_id),
            str(record.id),
        )
        result.append(
            {
                "run": record.model_dump(mode="json"),
                "state": sandbox.snapshot(),
                "events": sandbox.events(),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = [case for directory in args.data_dir for case in capture(directory)]
    if not cases:
        parser.error("No saved runs found")
    comparisons = {
        name: {
            "present_in_all_runs": all(case["run"]["baseline"].get(name) for case in cases),
            "equal": len({case["run"]["baseline"].get(name) for case in cases}) == 1,
        }
        for name in BASELINE_FIELDS
    }
    document = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(),
        "description": "Saved actual executor evidence with local simulated business effects.",
        "contains_private_reasoning": False,
        "cases": cases,
        "baseline_comparison": comparisons,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Exported {len(cases)} saved runs to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
