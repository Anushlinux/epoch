"""Build the local PDF runtime and record its immutable image identity."""

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data"
    )
    parser.add_argument(
        "--record-only",
        action="store_true",
        help="Record the already built local image without rebuilding",
    )
    args = parser.parse_args()
    context = Path(__file__).resolve().parents[1] / "pdf_runtime"
    if not args.record_only:
        subprocess.run(
            ["docker", "build", "-t", "epoch-pdf-workshop:local", str(context)], check=True
        )
    image = subprocess.check_output(
        ["docker", "image", "inspect", "epoch-pdf-workshop:local", "--format", "{{.Id}}"], text=True
    ).strip()
    root = args.data_dir / "pdf"
    root.mkdir(parents=True, exist_ok=True)
    dependencies = subprocess.check_output(
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--entrypoint=/bin/sh",
            image,
            "-c",
            "cat /opt/pdf-dependencies.txt; "
            "dpkg-query -W poppler-utils fonts-dejavu-core; "
            "sha256sum /opt/pdf-worker.py",
        ],
        text=True,
    )
    (root / "runtime.json").write_text(
        json.dumps(
            {
                "image_id": image,
                "runner_version": "pdf-tools-v1",
                "dependencies_and_worker": dependencies,
            },
            indent=2,
        )
    )
    print(f"PDF runtime ready: {image}\nManifest: {root / 'runtime.json'}")


if __name__ == "__main__":
    main()
