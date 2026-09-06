"""Opt-in actual Linux Docker checks; no provider requests or host candidate exec."""

import inspect
import os
import threading
import time

import pytest

from epoch_backend.candidate_runner import CandidateError, CandidateRunner, inspect_runner
from epoch_backend.environment_store import EnvironmentStore
from epoch_backend.repair_verification import component_proofs, isolation_proof
from epoch_backend.sandbox_adapters import serialize_checklist

pytestmark = pytest.mark.skipif(
    os.getenv("EPOCH_TEST_DOCKER") != "1", reason="Set EPOCH_TEST_DOCKER=1 for real Docker checks"
)


@pytest.fixture(scope="module")
def runner():
    info = inspect_runner()
    assert info["available"], info
    return CandidateRunner(info["image_id"])


def test_actual_container_boundary(runner):
    proof = isolation_proof(runner.image_id, threading.Event())
    assert proof["passed"], proof


def test_actual_payload_and_host_file_unchanged(runner, tmp_path):
    sentinel = tmp_path / "protected.txt"
    sentinel.write_text("unchanged")
    source = (
        "import os\n"
        "def serialize_checklist(**args):\n"
        "    assert not os.path.exists(args.pop('host_path'))\n"
        "    return args\n"
    )
    assert runner.run(source, {"items": ["安全", "a\nb"], "host_path": str(sentinel)}) == {
        "items": ["安全", "a\nb"]
    }
    assert sentinel.read_text() == "unchanged"


@pytest.mark.parametrize(
    "source",
    [
        "def serialize_checklist(**args):\n    while True: pass\n",
        "import time\ndef serialize_checklist(**args):\n    time.sleep(100)\n",
        "def serialize_checklist(**args):\n    print('x' * 200000)\n    return {}\n",
        "def serialize_checklist(**args):\n    return 'not an object'\n",
        "def serialize_checklist(**args):\n    return {'bad': float('nan')}\n",
    ],
)
def test_actual_resource_and_output_limits(runner, source):
    started = time.monotonic()
    with pytest.raises(CandidateError):
        runner.run(source, {})
    assert time.monotonic() - started < 25


def test_precancelled_creates_no_execution(runner):
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(CandidateError, match="not started"):
        runner.run("def serialize_checklist(**args): return args", {}, cancelled=cancelled)


def test_actual_failed_candidate_stays_inactive_after_restart(runner, tmp_path):
    store = EnvironmentStore(tmp_path / "environments.sqlite3")
    store.initialize()
    version = store.stage(
        "demo",
        "import json\n" + inspect.getsource(serialize_checklist),
        image_id=runner.image_id,
        runner_version="docker-serializer-v1",
        parent="builtin",
        diagnosis={"source": "developer negative test, not LLM output"},
        diff="negative control",
    )
    results = component_proofs(version, threading.Event())
    assert not next(p for p in results if p["kind"] == "component")["passed"]
    assert next(p for p in results if p["kind"] == "regression")["passed"]
    with pytest.raises(CandidateError, match="Every required trusted check"):
        store.publish(version["id"], results, expected_active="builtin")
    store.reject(version["id"], results, "Actual Docker component checks failed.")
    reopened = EnvironmentStore(store.path)
    reopened.initialize()
    assert reopened.active_id("demo") == "builtin"
    assert reopened.version(version["id"])["status"] == "rejected"
    assert reopened.version(version["id"])["proofs"] == results
