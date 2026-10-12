"""Bounded runtime identity and request telemetry without request payloads."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import Header, HTTPException
from starlette.responses import JSONResponse

MAX_MANIFEST_FILES = 256
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MANIFEST_PATTERNS = (
    "apps/api/src/**/*.py", "apps/worker/src/**/*.py",
    "apps/web/**/*.html", "apps/web/**/*.js", "apps/web/**/*.css",
    "contracts/*.yaml", "contracts/*.json", "migrations/versions/*.sql",
    "scripts/start_staging.py", "scripts/start_service.py", "scripts/storage_probe.py",
    "requirements-runtime.lock", "Dockerfile", "railway.toml",
)


def runtime_manifest(root: Path) -> dict:
    root = root.resolve()
    paths = sorted({path for pattern in MANIFEST_PATTERNS for path in root.glob(pattern)})
    if not 1 <= len(paths) <= MAX_MANIFEST_FILES:
        raise ValueError("RUNTIME_MANIFEST_FILE_BUDGET")
    remaining = MAX_MANIFEST_BYTES
    files = []
    for path in paths:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("RUNTIME_MANIFEST_UNSAFE_PATH")
        with path.open("rb") as handle:
            body = handle.read(remaining + 1)
        remaining -= len(body)
        if remaining < 0:
            raise ValueError("RUNTIME_MANIFEST_BYTE_BUDGET")
        files.append({"path": path.relative_to(root).as_posix(),
                      "sha256": hashlib.sha256(body).hexdigest(), "size": len(body)})
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"profile": "forgeworks-runtime-manifest-v1", "file_count": len(files),
            "sha256": hashlib.sha256(canonical).hexdigest()}


@lru_cache(maxsize=8)
def deployed_manifest(root: str) -> dict:
    return runtime_manifest(Path(root))


def runtime_identity(root: Path, product: str) -> dict:
    environment = os.getenv("APP_ENV", "development")
    platform_revision = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")
    operator_revision = os.getenv("FORGEWORKS_RELEASE_SHA", "")
    if platform_revision and operator_revision and platform_revision != operator_revision:
        raise ValueError("RUNTIME_REVISION_BINDING_MISMATCH")
    revision = platform_revision or operator_revision
    if environment not in {"development", "test", "staging", "production"}:
        raise ValueError("RUNTIME_ENVIRONMENT_INVALID")
    if revision and not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("RUNTIME_REVISION_INVALID")
    if environment in {"staging", "production"} and not revision:
        raise ValueError("RUNTIME_REVISION_REQUIRED")
    return {"product": product, "environment": environment, "revision_sha": revision or None,
            "runtime_manifest": deployed_manifest(str(root.resolve()))}


class RequestMetrics:
    """Bounded per-process counters, not a fleet or percentile metric backend."""
    def __init__(self, limit: int = 256):
        self.limit = limit
        self.lock = threading.Lock()
        self.rows = {}
        self.overflow = 0

    def observe(self, method: str, route: str, status: int, duration: float,
                complete: bool = True, exception: bool = False) -> None:
        key = (method, route, f"{status // 100}xx")
        with self.lock:
            if key not in self.rows and len(self.rows) >= self.limit:
                self.overflow += 1
                return
            row = self.rows.setdefault(key, [0, 0.0, 0.0, 0, 0])
            row[0] += 1
            row[1] += duration
            row[2] = max(row[2], duration)
            row[3] += int(not complete)
            row[4] += int(exception)

    def snapshot(self) -> dict:
        with self.lock:
            rows = [
                {"method": method, "route": route, "status_class": status,
                 "count": value[0], "duration_seconds_sum": round(value[1], 6),
                 "duration_seconds_max": round(value[2], 6),
                 "incomplete_responses": value[3], "handler_exceptions": value[4]}
                for (method, route, status), value in sorted(self.rows.items())
            ]
            return {"scope": "single-process-since-start", "series_limit": self.limit,
                    "overflow_requests": self.overflow, "requests": rows}


class RequestTelemetryMiddleware:
    def __init__(self, app, metrics: RequestMetrics, logger: logging.Logger, product: str):
        self.app, self.metrics, self.logger, self.product = app, metrics, logger, product

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = uuid4().hex
        status = 499
        response_started = False
        complete = False
        exception = False
        method = scope.get("method", "OTHER")
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            method = "OTHER"

        async def traced_send(message):
            nonlocal status, response_started, complete
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                replaced = {b"x-request-id", b"referrer-policy", b"x-content-type-options"}
                headers = [(key, value) for key, value in message.get("headers", [])
                           if key.lower() not in replaced]
                message = {**message, "headers": headers + [
                    (b"x-request-id", request_id.encode()),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-content-type-options", b"nosniff")]}
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                complete = True

        try:
            await self.app(scope, receive, traced_send)
        except Exception:
            exception = True
            if not response_started:
                status = 500
                if os.getenv("APP_ENV") in {"staging", "production"}:
                    response = JSONResponse(
                        {"type": "about:blank", "title": "Internal server error", "status": 500,
                         "code": "INTERNAL_ERROR", "request_id": request_id},
                        status_code=500, media_type="application/problem+json")
                    await response(scope, receive, traced_send)
                    return
            raise
        finally:
            route = getattr(scope.get("route"), "path", "UNMATCHED")
            if not isinstance(route, str) or len(route) > 256:
                route = "UNMATCHED"
            duration = time.monotonic() - started
            self.metrics.observe(method, route, status, duration, complete, exception)
            if os.getenv("FORGEWORKS_HTTP_LOGS") == "1":
                self.logger.info(json.dumps(
                    {"event": "http.request", "product": self.product, "request_id": request_id,
                     "method": method, "route": route, "status": status,
                     "response_complete": complete, "handler_exception": exception,
                     "duration_ms": round(duration * 1000, 3)},
                    separators=(",", ":")))


def register_operations(app, root: Path, product: str) -> None:
    metrics = RequestMetrics()
    app.state.request_metrics = metrics
    logger = logging.getLogger("forgeworks.http")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    app.add_middleware(RequestTelemetryMiddleware, metrics=metrics, logger=logger, product=product)

    @app.get("/versionz", include_in_schema=False)
    def version():
        try:
            identity = runtime_identity(root, product)
        except (OSError, ValueError):
            raise HTTPException(503, detail={"code": "RUNTIME_IDENTITY_UNAVAILABLE"}) from None
        return JSONResponse(identity, headers={"Cache-Control": "no-store"})

    @app.get("/metricsz", include_in_schema=False)
    def private_metrics(authorization: str | None = Header(default=None)):
        secret = os.getenv("METRICS_READ_SECRET", "")
        if (not 32 <= len(secret) <= 256 or not secret.isascii()
                or any(ord(c) < 33 or ord(c) == 127 for c in secret)
                or secret in {os.getenv("DEV_AUTH_SECRET"), os.getenv("ARTIFACT_SIGNING_SECRET")}):
            raise HTTPException(503, detail={"code": "METRICS_NOT_CONFIGURED"})
        if (not authorization or not authorization.isascii() or len(authorization) > 512
                or not hmac.compare_digest(authorization, f"Bearer {secret}")):
            raise HTTPException(401, detail={"code": "METRICS_AUTH_REQUIRED"})
        return JSONResponse(metrics.snapshot(), headers={"Cache-Control": "no-store"})
