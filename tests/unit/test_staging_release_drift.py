"""Source-vs-release drift is never reported as hosted acceptance."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_staging_release_drift.py"
spec = importlib.util.spec_from_file_location("staging_drift_probe", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def record():
    return {
        "schema": "forgeworks-staging-release-v1",
        "product": checker.PRODUCT,
        "environment": "staging",
        "revision_sha": "a" * 40,
        "runtime_manifest": {"sha256": "b" * 64},
        "deployment_status": "SUCCESS",
    }


def test_equal_revision_is_only_a_record_match(record):
    result = checker.inspect(record, "a" * 40)
    assert result["record_is_current"] is True
    assert result["status"] == "RECORD_MATCHES_MAIN"
    assert "not verified" in result["scope"]


def test_new_main_is_reported_as_stale_and_not_success(record):
    result = checker.inspect(record, "c" * 40)
    assert result["record_is_current"] is False
    assert result["status"] == "STAGING_RELEASE_STALE"


@pytest.mark.parametrize("field,value", [
    ("product", "wrong-product"), ("environment", "production"),
    ("revision_sha", "unsafe"), ("deployment_status", "FAILED"),
    ("schema", "unknown"),
])
def test_invalid_release_record_is_rejected(record, field, value):
    record[field] = value
    with pytest.raises(ValueError):
        checker.inspect(record, "a" * 40)


def test_invalid_manifest_or_main_commit_is_rejected(record):
    record["runtime_manifest"]["sha256"] = "short"
    with pytest.raises(ValueError):
        checker.inspect(record, "a" * 40)
    record["runtime_manifest"]["sha256"] = "b" * 64
    with pytest.raises(ValueError):
        checker.inspect(record, "not-a-commit")
