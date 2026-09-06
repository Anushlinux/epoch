import gzip
import json
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from epoch_backend.telemetry import TelemetryService
from epoch_backend.telemetry_api import telemetry_router


class EvidenceSink:
    def __init__(self):
        self.records = {}

    def ingest_evidence(self, records):
        for record in records:
            self.records.setdefault(record["source_id"], record)


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("EPOCH_TELEMETRY_TOKEN", "local-test-token")
    monkeypatch.delenv("NEATLOGS_API_KEY", raising=False)
    settings = SimpleNamespace(
        data_dir=tmp_path, telemetry_enabled=True, neatlogs_cloud_enabled=False
    )
    service = TelemetryService(settings, EvidenceSink())
    service.initialize()
    yield service
    service.close()


def request_data():
    request = ExportTraceServiceRequest()
    resource = request.resource_spans.add()
    resource.resource.attributes.add(key="secret_resource").value.string_value = "secret-value"
    span = resource.scope_spans.add().spans.add()
    span.trace_id, span.span_id = b"a" * 16, b"b" * 8
    span.start_time_unix_nano = 1_700_000_000_000_000_000
    span.end_time_unix_nano = span.start_time_unix_nano + 1_000_000
    span.name = "private user question"
    for key, value in {
        "epoch.project_id": "demo",
        "epoch.workflow": "release",
        "input.value": "private prompt",
        "output.value": "private response",
        "epoch.error_code": "schema_validation",
    }.items():
        span.attributes.add(key=key).value.string_value = value
    span.events.add(name="private event")
    return request


def client_for(service):
    app = FastAPI()
    app.include_router(telemetry_router(service))
    return TestClient(app)


def test_real_protobuf_gzip_auth_dedup_and_redaction(service):
    client = client_for(service)
    data = gzip.compress(request_data().SerializeToString())
    headers = {"content-type": "application/x-protobuf", "content-encoding": "gzip"}
    assert client.post("/v1/traces", content=data, headers=headers).status_code == 401
    headers["x-api-key"] = "local-test-token"
    for _ in range(2):
        response = client.post("/v1/traces", content=data, headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-protobuf"
    assert service.runtime_info()["stored_spans"] == 1
    assert len(service.incidents.records) == 1
    with closing(service._connect()) as connection:
        row = connection.execute("SELECT * FROM spans").fetchone()
    cloud = ExportTraceServiceRequest.FromString(row["cloud_payload"])
    encoded = str(cloud)
    assert "private" not in encoded and "secret" not in encoded
    assert "schema_validation" in encoded
    source = client.get(next(iter(service.incidents.records.values()))["source_ref"]).json()
    assert "private prompt" in json.dumps(source["otlp"])
    assert "secret-value" in json.dumps(source["otlp"])
    assert "local-test-token" not in json.dumps(service.runtime_info())


def test_malformed_oversized_and_invalid_span_requests(service):
    client = client_for(service)
    headers = {
        "x-api-key": "local-test-token",
        "content-type": "application/x-protobuf",
        "content-encoding": "gzip",
    }
    assert client.post("/v1/traces", content=b"bad", headers=headers).status_code == 400
    assert (
        client.post(
            "/v1/traces", content=gzip.compress(b"x" * (4 * 1024 * 1024 + 1)), headers=headers
        ).status_code
        == 413
    )
    headers.pop("content-encoding")
    request = request_data()
    request.resource_spans[0].scope_spans[0].spans[0].trace_id = b"bad"
    assert (
        client.post("/v1/traces", content=request.SerializeToString(), headers=headers).status_code
        == 400
    )
    assert service.runtime_info()["stored_spans"] == 0


def test_native_event_export_reimport_and_restart_do_not_duplicate(service):
    event = {
        "id": "event-1",
        "sequence": 1,
        "type": "executor.tool_started",
        "emitted_at": "2026-09-06T00:00:00+00:00",
        "payload": {"name": "checklist", "arguments": {"secret": "hidden"}},
    }
    sandbox = SimpleNamespace(
        metadata=lambda: {"project_id": "demo"}, events=lambda after=0: [event] if after < 1 else []
    )
    record = SimpleNamespace(id="run-1", task_id="task-1")
    service.project_events(record, sandbox)
    service.project_events(record, sandbox)
    with closing(service._connect()) as connection:
        raw = connection.execute("SELECT cloud_payload FROM spans").fetchone()[0]
    service.ingest(raw)
    assert service.runtime_info()["stored_spans"] == 1
    assert service.incidents.records == {}
    service.close()
    restarted = TelemetryService(service.settings, EvidenceSink())
    restarted.initialize()
    try:
        restarted.project_events(record, sandbox)
        assert restarted.runtime_info()["stored_spans"] == 1
    finally:
        restarted.close()


def test_cloud_failure_bounded_and_does_not_lose_local_evidence(service):
    service.cloud_enabled, service._key = True, "cloud-test-token"
    # Avoid a live worker and mock the only network surface.
    service.close()
    service.ingest(request_data().SerializeToString())
    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.side_effect = OSError("must never disclose token")
        for _ in range(4):
            with closing(service._connect()) as connection, connection:
                connection.execute("UPDATE spans SET next_attempt=0")
            service._export_one()
        assert opener.return_value.open.call_count == 3
    assert service.runtime_info()["failed"] == 1
    assert len(service.incidents.records) == 1
    with closing(service._connect()) as connection:
        assert (
            connection.execute("SELECT error FROM spans").fetchone()[0] == "cloud_transport_failed"
        )


def test_two_span_cloud_batch_preserves_identity_and_conservative_partial_result(service):
    service.close()
    service.cloud_enabled, service._key = True, "cloud-test-token"
    first = request_data()
    second = request_data()
    second.resource_spans[0].scope_spans[0].spans[0].span_id = b"c" * 8
    service.ingest(first.SerializeToString())
    service.ingest(second.SerializeToString())
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse

    response = ExportTraceServiceResponse()
    response.partial_success.rejected_spans = 1
    with patch("urllib.request.build_opener") as opener:
        opener.return_value.open.return_value.__enter__.return_value.read.return_value = (
            response.SerializeToString()
        )
        service._export_one()
        assert opener.return_value.open.call_count == 1
        sent = opener.return_value.open.call_args.args[0]
        batch = ExportTraceServiceRequest.FromString(gzip.decompress(sent.data))
        ids = {
            span.span_id
            for resource in batch.resource_spans
            for scope in resource.scope_spans
            for span in scope.spans
        }
        assert ids == {b"b" * 8, b"c" * 8}
    assert service.runtime_info()["failed"] == 2
    assert service.runtime_info()["delivered"] == 0
    with closing(service._connect()) as connection:
        assert [row[0] for row in connection.execute("SELECT attempts FROM spans")] == [1, 1]


def test_rejected_evidence_does_not_block_other_spans(service):
    service.close()
    first = request_data()
    second = request_data()
    second.resource_spans[0].scope_spans[0].spans[0].span_id = b"c" * 8
    original = service.incidents.ingest_evidence

    def selective(records):
        if records[0]["span_id"] == (b"b" * 8).hex():
            raise ValueError("Rejected evidence")
        original(records)

    service.incidents.ingest_evidence = selective
    service.ingest(first.SerializeToString())
    service.ingest(second.SerializeToString())
    service._deliver_evidence()
    assert service.runtime_info()["evidence_failed"] == 1
    assert len(service.incidents.records) == 1
    assert service.get_span((b"a" * 16).hex(), (b"b" * 8).hex())["otlp"]


def test_standard_sdk_error_and_workflow_need_no_epoch_attributes(service):
    request = request_data()
    resource = request.resource_spans[0]
    resource.resource.ClearField("attributes")
    resource.resource.attributes.add(key="neatlogs.workflow_name").value.string_value = "release"
    span = resource.scope_spans[0].spans[0]
    span.ClearField("attributes")
    span.attributes.add(key="tool.name").value.string_value = "create_checklist"
    span.status.code = 2
    service.ingest(request.SerializeToString())
    evidence = next(iter(service.incidents.records.values()))
    assert evidence["workflow"] == "release"
    assert evidence["tool"] == "create_checklist"
    assert evidence["error_code"] == "span_error"
    assert evidence["status"] == "error"
