import time
from concurrent.futures import ThreadPoolExecutor

from accessfix_ai.infrastructure.store import SITE, TENANT, Store
from accessfix_ai.worker import ScanWorker, WorkerConfig

REPO = "a" * 40
POLICY = "policy-digest"


def test_terminal_scan_cannot_create_findings_or_be_rewritten(tmp_path):
    store = new_store(tmp_path)
    scan = store.scan(TENANT, SITE, REPO, POLICY)
    lease = store.claim_scan()
    assert store.fail_scan(TENANT, scan["id"], "TEST_FAILURE", max_attempts=1, lease_until=lease["lease_until"]) == "FAILED"
    assert not store.complete_scan(TENANT, scan["id"])
    assert store.findings(TENANT, scan["id"]) == []
    assert store.fail_scan(TENANT, scan["id"], "LATE_FAILURE") == "FAILED"
    assert store.get_scan(TENANT, scan["id"])["last_error_code"] == "TEST_FAILURE"


def test_stale_worker_cannot_consume_new_lease_cancellation(tmp_path):
    store = new_store(tmp_path)
    scan = store.scan(TENANT, SITE, REPO, POLICY)
    old = store.claim_scan(lease_seconds=0.01)
    time.sleep(0.03)
    newer = store.claim_scan()
    store.request_cancel(TENANT, scan["id"])
    assert store.fail_scan(TENANT, scan["id"], "OLD", lease_until=old["lease_until"]) == "STALE_LEASE"
    assert store.get_scan(TENANT, scan["id"])["lease_until"] == newer["lease_until"]
    assert store.fail_scan(TENANT, scan["id"], "NEW", lease_until=newer["lease_until"]) == "CANCELLED"


def test_independent_adapters_allow_exactly_one_review(tmp_path):
    store = new_store(tmp_path)
    scan = store.scan(TENANT, SITE, REPO, POLICY)
    ScanWorker(store).run_once()
    finding = store.findings(TENANT, scan["id"])[0]
    proposal = store.proposal(TENANT, finding["id"], REPO, "patch")
    assert store.retest(TENANT, proposal["id"], REPO, 1)[1] == "OK"
    adapters = [Store(store.path), Store(store.path)]
    def approve(index):
        return adapters[index].review(TENANT, proposal["id"], f"reviewer-{index}", "patch", "approve", "passed", 2)[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(approve, range(2))) == ["OK", "STALE"]
    assert store.proposal_get(TENANT, proposal["id"])["version"] == 3
    with store.conn() as connection:
        assert connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1


def new_store(tmp_path):
    store = Store(str(tmp_path / "worker.db"))
    store.seed()
    return store


def test_duplicate_scan_idempotency_and_no_duplicate_findings_or_proposals(tmp_path):
    store = new_store(tmp_path)
    first = store.scan(TENANT, SITE, REPO, POLICY, principal="worker-test", idempotency_key="scan-key-00000001")
    duplicate = store.scan(TENANT, SITE, REPO, POLICY, principal="worker-test", idempotency_key="scan-key-00000001")
    assert first["id"] == duplicate["id"]
    ScanWorker(store).run_once()
    assert len(store.findings(TENANT, first["id"])) == 1
    assert store.complete_scan(TENANT, first["id"]) is False
    finding = store.findings(TENANT, first["id"])[0]
    proposal = store.proposal(TENANT, finding["id"], REPO, "patch-digest")
    duplicate_proposal = store.proposal(TENANT, finding["id"], REPO, "patch-digest")
    assert proposal["id"] == duplicate_proposal["id"]
    with store.conn() as connection:
        assert connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] == 1


def test_lease_expiry_allows_restart_reclaim(tmp_path):
    store = new_store(tmp_path)
    scan = store.scan(TENANT, SITE, REPO, POLICY)
    claimed = store.claim_scan(lease_seconds=0.01, timeout_seconds=1)
    assert claimed["id"] == scan["id"]
    time.sleep(0.03)
    restarted = ScanWorker(store, WorkerConfig(lease_seconds=0.1, timeout_seconds=1, max_attempts=3))
    assert restarted.run_once() is True
    final = store.get_scan(TENANT, scan["id"])
    assert final["status"] == "SUCCEEDED"
    assert final["attempt_count"] == 2
    assert len(store.findings(TENANT, scan["id"])) == 1


def test_retry_then_success_and_terminal_failure_are_bounded(tmp_path):
    store = new_store(tmp_path)
    scan = store.scan(TENANT, SITE, REPO, POLICY)
    attempts = {"count": 0}

    def flaky(_row):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("synthetic worker fault")

    worker = ScanWorker(store, WorkerConfig(max_attempts=3), flaky)
    assert worker.drain(5) == 2
    assert store.get_scan(TENANT, scan["id"])["status"] == "SUCCEEDED"
    assert store.get_scan(TENANT, scan["id"])["attempt_count"] == 2

    terminal_scan = store.scan(TENANT, SITE, "b" * 40, POLICY)
    terminal = ScanWorker(store, WorkerConfig(max_attempts=2), lambda _row: (_ for _ in ()).throw(RuntimeError("always fails")))
    started = time.monotonic()
    assert terminal.drain(10) == 2
    assert time.monotonic() - started < 1.0
    failed = store.get_scan(TENANT, terminal_scan["id"])
    assert failed["status"] == "FAILED"
    assert failed["attempt_count"] == 2
    assert failed["last_error_code"] == "WORKER_ERROR"


def test_stale_retest_revision_cancellation_and_timeout_bounds(tmp_path):
    store = new_store(tmp_path)
    scan = store.scan(TENANT, SITE, REPO, POLICY)
    assert store.request_cancel(TENANT, scan["id"]) is True
    worker = ScanWorker(store, WorkerConfig(max_attempts=1))
    assert worker.run_once() is True
    assert store.get_scan(TENANT, scan["id"])["status"] == "CANCELLED"

    timed_scan = store.scan(TENANT, SITE, "c" * 40, POLICY)
    timeout_worker = ScanWorker(
        store,
        WorkerConfig(timeout_seconds=0.01, max_attempts=1),
        lambda _row: time.sleep(0.03),
    )
    started = time.monotonic()
    assert timeout_worker.run_once() is True
    assert time.monotonic() - started < 0.5
    timed = store.get_scan(TENANT, timed_scan["id"])
    assert timed["status"] == "FAILED"
    assert timed["last_error_code"] == "WORKER_TIMEOUT"

    # A stale revision is rejected before a retest can change proposal state.
    completed = store.scan(TENANT, SITE, "d" * 40, POLICY)
    ScanWorker(store).run_once()
    finding = store.findings(TENANT, completed["id"])[0]
    proposal = store.proposal(TENANT, finding["id"], "d" * 40, "patch")
    assert store.retest(TENANT, proposal["id"], "e" * 40, 1)[1] == "REVISION_MISMATCH"
    retested, status = store.retest(TENANT, proposal["id"], "d" * 40, 1)
    assert status == "OK" and retested["version"] == 2
    assert store.retest(TENANT, proposal["id"], "d" * 40, 1)[1] == "STALE"

