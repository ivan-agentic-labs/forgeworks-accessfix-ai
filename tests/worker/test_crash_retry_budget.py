"""Lease reclaims must consume the same attempt budget as reported failures."""
import pytest

from accessfix_ai.infrastructure.store import Store, TENANT, SITE
from accessfix_ai.worker import ScanWorker, WorkerConfig


def expire(store, scan_id):
    with store.conn() as db:
        db.execute('UPDATE scans SET lease_until=? WHERE tenant_id=? AND id=?',
                   ('2000-01-01T00:00:00Z', TENANT, scan_id))


def test_default_claim_budget_stops_unreported_crashes(tmp_path):
    store = Store(str(tmp_path / 'jobs.db'))
    store.seed()
    scan = store.scan(TENANT, SITE, 'a' * 40, 'policy')
    for _ in range(3):
        assert store.claim_scan() is not None
        expire(store, scan['id'])
    assert store.claim_scan() is None
    assert store.get_scan(TENANT, scan['id'])['attempt_count'] == 3


@pytest.mark.parametrize('budget', [1, 2, 3])
def test_expired_claims_stop_at_budget_and_do_not_starve_next_scan(tmp_path, budget):
    store = Store(str(tmp_path / 'jobs.db'))
    store.seed()
    crashed = store.scan(TENANT, SITE, 'a' * 40, 'policy')
    for attempt in range(1, budget + 1):
        claim = store.claim_scan(max_attempts=budget)
        assert claim['id'] == crashed['id'] and claim['attempt_count'] == attempt
        # Even the last allowed attempt retains its live lease.
        assert store.claim_scan(max_attempts=budget) is None
        assert store.get_scan(TENANT, crashed['id'])['status'] == 'RUNNING'
        expire(store, crashed['id'])
    assert store.claim_scan(max_attempts=budget) is None
    final = store.get_scan(TENANT, crashed['id'])
    assert final['status'] == 'FAILED' and final['attempt_count'] == budget
    assert final['last_error_code'] == 'MAX_ATTEMPTS_EXCEEDED'
    assert final['lease_until'] is None and final['timeout_at'] is None
    assert store.findings(TENANT, crashed['id']) == []
    assert store.scan_source(TENANT, crashed['id']) is None
    next_scan = store.scan(TENANT, SITE, 'b' * 40, 'policy')
    claim = store.claim_scan(max_attempts=budget)
    assert claim['id'] == next_scan['id']
    assert store.complete_scan(TENANT, claim['id'], claim['lease_until'])


def test_worker_crashes_obey_configured_attempt_budget(tmp_path):
    store = Store(str(tmp_path / 'jobs.db'))
    store.seed()
    scan = store.scan(TENANT, SITE, 'a' * 40, 'policy')
    calls = []
    class ProcessCrash(BaseException):
        pass
    def crash(row):
        calls.append(row['attempt_count'])
        raise ProcessCrash()
    for _ in range(2):
        worker = ScanWorker(store, WorkerConfig(max_attempts=2), crash)
        with pytest.raises(ProcessCrash):
            worker.run_once()
        expire(store, scan['id'])
    assert not ScanWorker(store, WorkerConfig(max_attempts=2), crash).run_once()
    assert calls == [1, 2]
    assert store.get_scan(TENANT, scan['id'])['status'] == 'FAILED'


@pytest.mark.parametrize('budget', [True, 0, -1, 1.5, '3'])
def test_invalid_attempt_budget_does_not_mutate_jobs(tmp_path, budget):
    store = Store(str(tmp_path / 'jobs.db'))
    store.seed()
    scan = store.scan(TENANT, SITE, 'a' * 40, 'policy')
    with pytest.raises(ValueError):
        store.claim_scan(max_attempts=budget)
    assert store.get_scan(TENANT, scan['id'])['attempt_count'] == 0
    with pytest.raises(ValueError):
        WorkerConfig(max_attempts=budget)


@pytest.mark.parametrize('state', ['PENDING', 'RUNNING'])
def test_exhausted_cancelled_job_preserves_cancellation(tmp_path, state):
    store = Store(str(tmp_path / 'jobs.db'))
    store.seed()
    scan = store.scan(TENANT, SITE, 'a' * 40, 'policy')
    assert store.claim_scan(max_attempts=1)
    with store.conn() as db:
        db.execute('UPDATE scans SET status=?,cancel_requested=1,lease_until=? WHERE id=?',
                   (state, '2000-01-01T00:00:00Z', scan['id']))
    assert store.claim_scan(max_attempts=1) is None
    final = store.get_scan(TENANT, scan['id'])
    assert final['status'] == 'CANCELLED' and final['last_error_code'] == 'CANCELLED'
    assert final['attempt_count'] == 1


def test_exhausted_scan_does_not_block_ready_scan(tmp_path):
    store = Store(str(tmp_path / 'jobs.db'))
    store.seed()
    crashed = store.scan(TENANT, SITE, 'a' * 40, 'policy')
    assert store.claim_scan(max_attempts=1)
    expire(store, crashed['id'])
    ready = store.scan(TENANT, SITE, 'b' * 40, 'policy')
    assert store.claim_scan(max_attempts=1)['id'] == ready['id']
    assert store.get_scan(TENANT, crashed['id'])['status'] == 'FAILED'
