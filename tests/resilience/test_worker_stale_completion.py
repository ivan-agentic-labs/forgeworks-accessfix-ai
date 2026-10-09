from accessfix_ai.infrastructure.store import Store,TENANT,SITE
from accessfix_ai.worker import ScanWorker,WorkerConfig


def test_real_worker_cannot_finish_reclaimed_lease(tmp_path):
    store=Store(str(tmp_path/'db.sqlite'));store.seed()
    scan=store.scan(TENANT,SITE,'a'*40,'b'*64)
    newer=[]
    def processor(row):
        with store.conn() as db:
            db.execute("UPDATE scans SET lease_until=? WHERE tenant_id=? AND id=?",('2000-01-01T00:00:00Z',TENANT,row['id']))
        newer.append(store.claim_scan(10,20))
    worker=ScanWorker(store,WorkerConfig(lease_seconds=5,timeout_seconds=20),processor)
    assert worker.run_once()
    assert newer[0]['attempt_count']==2
    assert store.get_scan(TENANT,scan['id'])['status']=='RUNNING'
    assert store.findings(TENANT,scan['id'])==[]
    assert store.complete_scan(TENANT,scan['id'],newer[0]['lease_until'])
