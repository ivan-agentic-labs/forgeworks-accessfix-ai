"""Trust Railway's deployment revision while rejecting conflicting operator pins."""
from pathlib import Path

import pytest

from accessfix_ai.presentation import operations


@pytest.fixture
def binding(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setattr(
        operations, "deployed_manifest",
        lambda _root: {"profile": "unit-runtime-manifest", "sha256": "b" * 64},
    )


@pytest.mark.parametrize("operator_sha", ["", "a" * 40])
def test_staging_identity_uses_current_platform_commit(binding, monkeypatch, operator_sha):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "a" * 40)
    monkeypatch.setenv("FORGEWORKS_RELEASE_SHA", operator_sha)
    identity = operations.runtime_identity(Path("."), "accessfix-ai")
    assert identity["revision_sha"] == "a" * 40
    assert identity["environment"] == "staging"


def test_staging_identity_rejects_stale_operator_pin(binding, monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "a" * 40)
    monkeypatch.setenv("FORGEWORKS_RELEASE_SHA", "c" * 40)
    with pytest.raises(ValueError, match="RUNTIME_REVISION_BINDING_MISMATCH"):
        operations.runtime_identity(Path("."), "accessfix-ai")


def test_staging_identity_rejects_missing_release_provenance(binding, monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("FORGEWORKS_RELEASE_SHA", raising=False)
    with pytest.raises(ValueError, match="RUNTIME_REVISION_REQUIRED"):
        operations.runtime_identity(Path("."), "accessfix-ai")


@pytest.mark.parametrize("bad_sha", ["", "not-a-sha", "A" * 40, "a" * 39])
def test_staging_identity_rejects_invalid_platform_sha(binding, monkeypatch, bad_sha):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", bad_sha)
    monkeypatch.delenv("FORGEWORKS_RELEASE_SHA", raising=False)
    with pytest.raises(ValueError, match="RUNTIME_REVISION_(REQUIRED|INVALID)"):
        operations.runtime_identity(Path("."), "accessfix-ai")
