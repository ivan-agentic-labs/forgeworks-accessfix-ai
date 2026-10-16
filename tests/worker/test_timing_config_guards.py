"""Worker scheduling errors must never claim or mutate customer scan jobs."""
import math

import pytest

from accessfix_ai.infrastructure.store import Store, TENANT, SITE
from accessfix_ai.worker import ScanWorker, WorkerConfig


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), -float("inf"), True, False, "5", None, 3601])
@pytest.mark.parametrize("parameter", ["lease_seconds", "timeout_seconds"])
def test_worker_rejects_invalid_lease_or_timeout(parameter, bad):
    with pytest.raises(ValueError, match=parameter):
        WorkerConfig(**{parameter: bad})


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True, "5", 3601])
@pytest.mark.parametrize("parameter", ["lease_seconds", "timeout_seconds"])
def test_sqlite_claim_rejects_invalid_timing_before_job_mutation(tmp_path, parameter, bad):
    store = Store(str(tmp_path / "timing.db"))
    store.seed()
    scan = store.scan(TENANT, SITE, "a" * 40, "policy")
    with pytest.raises(ValueError, match=parameter):
        store.claim_scan(**{parameter: bad})
    untouched = store.get_scan(TENANT, scan["id"])
    assert untouched["status"] == "PENDING"
    assert untouched["attempt_count"] == 0
    assert untouched["lease_until"] is None


@pytest.mark.parametrize("bad", [0, -1, 1.0, float("nan"), True, "5", 10001])
def test_worker_drain_rejects_invalid_step_limit_without_claim(tmp_path, bad):
    store = Store(str(tmp_path / "drain.db"))
    store.seed()
    scan = store.scan(TENANT, SITE, "b" * 40, "policy")
    with pytest.raises(ValueError, match="max_steps"):
        ScanWorker(store).drain(bad)
    assert store.get_scan(TENANT, scan["id"])["attempt_count"] == 0


def test_valid_small_lease_and_timeout_preserve_retry_behavior(tmp_path):
    store = Store(str(tmp_path / "valid.db"))
    store.seed()
    scan = store.scan(TENANT, SITE, "c" * 40, "policy")
    config = WorkerConfig(lease_seconds=0.01, timeout_seconds=1.0, max_attempts=2)
    assert ScanWorker(store, config).drain(2) == 1
    assert store.get_scan(TENANT, scan["id"])["status"] == "SUCCEEDED"
