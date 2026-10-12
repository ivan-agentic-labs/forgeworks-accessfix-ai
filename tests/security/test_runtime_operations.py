import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from accessfix_ai.presentation import operations as ops


@pytest.fixture
def source(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM synthetic-test-image\n")
    return tmp_path


def configure(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "a" * 40)
    monkeypatch.delenv("FORGEWORKS_RELEASE_SHA", raising=False)
    monkeypatch.delenv("METRICS_READ_SECRET", raising=False)
    monkeypatch.setenv("FORGEWORKS_HTTP_LOGS", "0")


def test_manifest_tracks_runtime_not_readme(source):
    first = ops.runtime_manifest(source)
    (source / "README.md").write_text("editorial change")
    assert ops.runtime_manifest(source) == first
    (source / "Dockerfile").write_text("changed runtime")
    assert ops.runtime_manifest(source)["sha256"] != first["sha256"]


def test_manifest_rejects_symlink_escape(source, tmp_path):
    (source / "Dockerfile").unlink()
    (source / "Dockerfile").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        ops.runtime_manifest(source)


@pytest.mark.parametrize("budget", ["MAX_MANIFEST_BYTES", "MAX_MANIFEST_FILES"])
def test_manifest_bounded(source, monkeypatch, budget):
    monkeypatch.setattr(ops, budget, 0)
    with pytest.raises(ValueError):
        ops.runtime_manifest(source)


@pytest.mark.parametrize("revision", ["", "bad", "A" * 40])
def test_hosted_identity_rejects_absent_or_invalid_revision(source, monkeypatch, revision):
    configure(monkeypatch)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", revision)
    with pytest.raises(ValueError):
        ops.runtime_identity(source, "accessfix-ai")


def test_operator_fallback_and_conflict(source, monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA")
    monkeypatch.setenv("FORGEWORKS_RELEASE_SHA", "b" * 40)
    assert ops.runtime_identity(source, "accessfix-ai")["revision_sha"] == "b" * 40
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "a" * 40)
    with pytest.raises(ValueError, match="BINDING_MISMATCH"):
        ops.runtime_identity(source, "accessfix-ai")


def test_public_version_exposes_only_release_metadata(source, monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("ARTIFACT_SIGNING_SECRET", "private-artifact-secret")
    app = FastAPI()
    ops.register_operations(app, source, "accessfix-ai")
    with TestClient(app) as client:
        response = client.get("/versionz")
        assert response.status_code == 200
        assert set(response.json()) == {"product", "environment", "revision_sha", "runtime_manifest"}
        assert "private-artifact-secret" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert len(response.headers["x-request-id"]) == 32


def test_metrics_credential_and_resource_privacy(source, monkeypatch):
    configure(monkeypatch)
    app = FastAPI()
    ops.register_operations(app, source, "accessfix-ai")
    @app.get("/objects/{object_id}")
    def resource(object_id: str):
        return {"ok": True}
    with TestClient(app) as client:
        assert client.get("/metricsz").status_code == 503
        monkeypatch.setenv("METRICS_READ_SECRET", "m" * 48)
        assert client.get("/metricsz").status_code == 401
        assert client.get("/metricsz", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.get("/metricsz", headers={"Authorization": b"Bearer \xe9"}).status_code == 401
        client.get("/objects/sensitive-resource?token=sensitive-query",
                   headers={"Authorization": "Bearer private-business-token"})
        response = client.get("/metricsz", headers={"Authorization": "Bearer " + "m" * 48})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["scope"] == "single-process-since-start"
        assert "/objects/{object_id}" in response.text
        assert all(value not in response.text for value in (
            "sensitive-resource", "sensitive-query", "private-business-token", "m" * 48))
        monkeypatch.setenv("ARTIFACT_SIGNING_SECRET", "m" * 48)
        assert client.get("/metricsz").status_code == 503


def test_series_cardinality_is_bounded():
    metrics = ops.RequestMetrics(limit=2)
    for index in range(4):
        metrics.observe("GET", f"/route-{index}", 200, 0.1)
    snapshot = metrics.snapshot()
    assert len(snapshot["requests"]) == 2
    assert snapshot["overflow_requests"] == 2


def run_middleware(app, metrics, logger):
    messages = []
    async def receive():
        return {"type": "http.disconnect"}
    async def send(message):
        messages.append(message)
    scope = {"type": "http", "method": "GET", "path": "/items/private-id",
             "query_string": b"token=private-query",
             "headers": [(b"authorization", b"Bearer private-token"),
                         (b"x-request-id", b"private-user-request-id")],
             "route": SimpleNamespace(path="/items/{item_id}")}
    middleware = ops.RequestTelemetryMiddleware(app, metrics, logger, "accessfix-ai")
    return scope, messages, lambda: asyncio.run(middleware(scope, receive, send))


def test_log_excludes_request_secrets_and_inbound_ids(monkeypatch):
    monkeypatch.setenv("FORGEWORKS_HTTP_LOGS", "1")
    records = []
    logger = SimpleNamespace(info=records.append)
    metrics = ops.RequestMetrics()
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"private-body"})
    scope, messages, invoke = run_middleware(endpoint, metrics, logger)
    invoke()
    record = json.loads(records[0])
    assert record["route"] == "/items/{item_id}"
    assert record["response_complete"] is True
    assert len(record["request_id"]) == 32
    assert all(value not in records[0] for value in (
        "private-id", "private-query", "private-token", "private-user-request-id", "private-body"))


def test_hosted_unhandled_error_is_sanitized(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("FORGEWORKS_HTTP_LOGS", "0")
    metrics = ops.RequestMetrics()
    async def endpoint(scope, receive, send):
        raise RuntimeError("database-password-private")
    _, messages, invoke = run_middleware(endpoint, metrics, logging.getLogger("test"))
    invoke()
    assert messages[0]["status"] == 500
    body = b"".join(m.get("body", b"") for m in messages)
    assert b"database-password-private" not in body
    assert json.loads(body)["code"] == "INTERNAL_ERROR"
    row = metrics.snapshot()["requests"][0]
    assert row["handler_exceptions"] == 1
    assert row["incomplete_responses"] == 0


def test_partial_stream_exception_preserves_started_status(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("FORGEWORKS_HTTP_LOGS", "0")
    metrics = ops.RequestMetrics()
    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"partial", "more_body": True})
        raise RuntimeError("stream failed")
    _, messages, invoke = run_middleware(endpoint, metrics, logging.getLogger("test"))
    with pytest.raises(RuntimeError):
        invoke()
    assert len([m for m in messages if m["type"] == "http.response.start"]) == 1
    row = metrics.snapshot()["requests"][0]
    assert row["status_class"] == "2xx"
    assert row["handler_exceptions"] == row["incomplete_responses"] == 1


def test_disconnect_without_response_is_counted(monkeypatch):
    monkeypatch.setenv("FORGEWORKS_HTTP_LOGS", "0")
    metrics = ops.RequestMetrics()
    async def endpoint(scope, receive, send):
        await receive()
    _, _, invoke = run_middleware(endpoint, metrics, logging.getLogger("test"))
    invoke()
    row = metrics.snapshot()["requests"][0]
    assert row["status_class"] == "4xx"
    assert row["handler_exceptions"] == 0
    assert row["incomplete_responses"] == 1
