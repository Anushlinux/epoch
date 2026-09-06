"""Read-only export of real saved repair evidence, including unsuccessful runs."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from export_run_evidence import capture

from epoch_backend.environment_store import EnvironmentStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    experiments = []
    for directory in args.data_dir:
        cases = capture(directory)
        projects = sorted(
            {
                case["run"]["supervision"]["operations"][0]["repairs"][0]["project"]
                for case in cases
                if case["run"].get("supervision")
                and case["run"]["supervision"]["operations"][0].get("repairs")
            }
        )
        environments = EnvironmentStore(directory / "environments.sqlite3")
        experiments.append(
            {
                "label": directory.name,
                "cases": cases,
                "environments": [environments.inspect(project) for project in projects],
                "acceptance": [
                    json.loads(p.read_text(encoding="utf-8"))
                    for p in sorted(directory.glob("acceptance-*.json"))
                ],
            }
        )
    document = {
        "captured_at": datetime.now(UTC).isoformat(),
        "description": "Actual saved Luna/Hermes repair evidence; business effects are simulated.",
        "contains_private_reasoning": False,
        "experiments": experiments,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {sum(len(e['cases']) for e in experiments)} actual runs.")


if __name__ == "__main__":
    main()
