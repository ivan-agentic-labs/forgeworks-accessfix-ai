import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def probe():
    path = Path(__file__).resolve().parents[2] / "scripts/probe_deployed_release.py"
    spec = importlib.util.spec_from_file_location("deployed_release_probe_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def responses(probe):
    manifest = {"profile": "forgeworks-runtime-manifest-v1", "file_count": 1, "sha256": "b" * 64}
    return manifest, {
        "/healthz": (200, {"status": "ok"}),
        "/readyz": (200, {"status": "ready"}),
        "/versionz": (200, {"product": probe.PRODUCT, "environment": "staging",
                           "revision_sha": "a" * 40, "runtime_manifest": manifest}),
        "/metricsz": (401, None),
        "/v1/jobs/00000000-0000-0000-0000-000000000001": (401, None),
    }


def test_release_probe_requires_exact_identity(probe, responses):
    manifest, values = responses
    result = probe.verify_release("a" * 40, manifest, request=lambda path: values[path])
    assert result["result"] == "PASS"
    assert result["private_metrics"] == "NOT_REQUESTED"
    assert "no authenticated business acceptance" in result["limits"]


@pytest.mark.parametrize("path", ["/healthz", "/readyz", "/versionz", "/metricsz",
                                 "/v1/jobs/00000000-0000-0000-0000-000000000001"])
def test_release_probe_rejects_failed_health_or_open_boundary(probe, responses, path):
    manifest, values = responses
    values[path] = (200, {}) if path in {"/metricsz", "/v1/jobs/00000000-0000-0000-0000-000000000001"} else (503, None)
    with pytest.raises(ValueError):
        probe.verify_release("a" * 40, manifest, request=lambda target: values[target])


def test_release_probe_rejects_wrong_fingerprint_or_revision(probe, responses):
    manifest, values = responses
    with pytest.raises(ValueError):
        probe.verify_release("a" * 40, {**manifest, "sha256": "c" * 64},
                             request=lambda path: values[path])
    with pytest.raises(ValueError):
        probe.verify_release("c" * 40, manifest, request=lambda path: values[path])
    with pytest.raises(ValueError):
        probe.verify_release("", manifest, request=lambda path: values[path])


def test_private_metrics_are_opt_in_and_secret_never_reported(probe, responses):
    manifest, values = responses
    calls = []
    def request(path, **kwargs):
        calls.append((path, kwargs))
        if kwargs:
            assert kwargs["secret"] == "private-metrics-test-secret"
            return 200, {"scope": "single-process-since-start", "requests": []}
        return values[path]
    result = probe.verify_release("a" * 40, manifest, request=request,
                                  metrics_secret="private-metrics-test-secret")
    assert result["private_metrics"] == "PASS"
    assert "private-metrics-test-secret" not in json.dumps(result)
    assert sum(bool(kwargs) for _, kwargs in calls) == 1


def test_probe_rejects_unknown_path_before_network(probe):
    with pytest.raises(ValueError, match="PATH_FORBIDDEN"):
        probe.fetch("/admin/reset")


def test_transient_readiness_retries_are_bounded_and_visible(probe, responses):
    manifest, values = responses
    counts = {"/healthz": 0, "/readyz": 0}
    sleeps = []

    def request(path):
        if path in counts:
            counts[path] += 1
            if path == "/healthz" and counts[path] == 1:
                return 503, None
            if path == "/readyz" and counts[path] == 1:
                return 429, None
            if path == "/readyz" and counts[path] == 2:
                return 503, None
        return values[path]

    result = probe.verify_release("a" * 40, manifest, request=request,
                                  sleep=sleeps.append)
    assert result["result"] == "PASS"
    assert result["health_attempts"] == 2
    assert result["readiness_attempts"] == 3
    assert counts == {"/healthz": 2, "/readyz": 3}
    assert sleeps == pytest.approx([0.2, 0.2, 0.4])


def test_persistent_readiness_failure_stays_failed_after_three_attempts(probe, responses):
    manifest, values = responses
    paths = []

    def request(path):
        paths.append(path)
        return (503, None) if path == "/readyz" else values[path]

    with pytest.raises(ValueError, match="RELEASE_READINESS_FAILED"):
        probe.verify_release("a" * 40, manifest, request=request, sleep=lambda _: None)
    assert paths == ["/healthz", "/readyz", "/readyz", "/readyz"]


def test_nontransient_health_and_identity_are_not_retried(probe, responses):
    manifest, values = responses
    calls = []

    def request(path):
        calls.append(path)
        return (401, None) if path == "/readyz" else values[path]

    with pytest.raises(ValueError, match="RELEASE_READINESS_FAILED"):
        probe.verify_release("a" * 40, manifest, request=request,
                             sleep=lambda _: pytest.fail("unexpected sleep"))
    assert calls == ["/healthz", "/readyz"]

    with pytest.raises(ValueError, match="RELEASE_RETRY_PATH_FORBIDDEN"):
        probe.probe_health_with_bounded_retry("/versionz", request, lambda _: None)
    assert calls == ["/healthz", "/readyz"]
