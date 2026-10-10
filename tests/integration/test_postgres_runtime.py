"""Actual disposable PostgreSQL fixture scan, worker fencing, approvals and RLS proof."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from accessfix_ai.infrastructure.store import TENANT,USER,SITE
from accessfix_ai.infrastructure.postgres_store import PostgresStore, ROLE
from accessfix_ai.worker import ScanWorker,WorkerConfig


def test_postgres_scan_worker_retest_review_and_tenant_boundary(monkeypatch):
    owner=os.getenv('ACCESSFIX_DISPOSABLE_OWNER_DSN')
    if not owner:pytest.skip('Disposable PostgreSQL unavailable; NOT a runtime pass')
    info=conninfo_to_dict(owner)
    if os.getenv('G1_DISPOSABLE_DB')!='yes' or info.get('host') not in {'localhost','127.0.0.1'} or info.get('dbname')!='forgeworks_runtime':pytest.fail('Refusing non-disposable database')
    root=Path(__file__).resolve().parents[2];other=str(uuid4())
    with psycopg.connect(owner) as db:
        if db.execute("SELECT to_regclass('sites')").fetchone()[0]:pytest.fail('Proof requires a fresh empty database')
        for name in ['001_accessfix_mvp.sql','002_accessfix_runtime.sql','003_accessfix_source_snapshots.sql','004_accessfix_proposal_sources.sql']:db.execute((root/'migrations/versions'/name).read_text())
        db.execute((root/'infra/environments/staging/003_fk_lookup_index.sql').read_text())
        definition = db.execute("SELECT pg_get_indexdef('idx_scan_jobs_tenant_site'::regclass)").fetchone()[0]
        assert 'scan_jobs USING btree (tenant_id, site_id)' in definition
        db.execute((root/'infra/environments/staging/004_sites_rls_initplan.sql').read_text())
        db.execute((root/'infra/environments/staging/005_sites_rls_current_setting_initplan.sql').read_text())
        db.execute((root/'infra/environments/staging/006_remaining_tenant_rls_initplans.sql').read_text())
        for table, policy_name in [['findings','findings_tenant'],['idempotency_keys','tenant_boundary'],['memberships','tenant_boundary'],['proposal_sources','tenant_boundary'],['proposals','tenant_boundary'],['reviews','tenant_boundary'],['scan_jobs','scan_jobs_tenant'],['scan_sources','tenant_boundary'],['verification_challenges','tenant_boundary']]:
            row = db.execute("SELECT qual, with_check FROM pg_policies WHERE schemaname=current_schema() AND tablename=%s AND policyname=%s", (table, policy_name)).fetchone()
            assert row and all('SELECT current_setting' in clause for clause in row)

        policy = db.execute("SELECT qual, with_check FROM pg_policies WHERE schemaname=current_schema() AND tablename='sites' AND policyname='sites_tenant'").fetchone()
        assert policy and all('SELECT' in predicate.upper() for predicate in policy)
        assert all('SELECT current_setting' in predicate for predicate in policy)
        db.execute("CREATE ROLE fw_runtime_test LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'synthetic-local-runtime-test-only'")
        db.execute('GRANT fw_accessfix_ai_rw TO fw_runtime_test')
        db.execute('INSERT INTO tenants VALUES(%s,%s,%s)',(TENANT,'synthetic-demo','ACTIVE'))
        db.execute('INSERT INTO tenants VALUES(%s,%s,%s)',(other,'synthetic-other','ACTIVE'))
        db.execute('INSERT INTO memberships VALUES(%s,%s,%s,%s)',(TENANT,USER,'editor','ACTIVE'))
        db.execute('INSERT INTO sites VALUES(%s,%s,%s,%s,%s,%s)',(TENANT,SITE,'http://fixture.local',str(uuid4()),'UNVERIFIED',None))
    info.update(user='fw_runtime_test',password='synthetic-local-runtime-test-only');runtime=make_conninfo(**info)
    with pytest.raises(ValueError,match='superuser'):PostgresStore(owner)
    store=PostgresStore(runtime)
    assert store.member_role(TENANT, USER) == 'editor'
    assert store.member_role(other, USER) is None
    assert store.member_role(TENANT, 'not-a-uuid') is None
    assert not store.member(TENANT, "unmapped-oidc-subject")
    # Runtime login and its group cannot own tenant/provisioning tables either.
    for table, new_owner in [('memberships','fw_runtime_test'),('tenants',ROLE)]:
        with psycopg.connect(owner) as db:
            db.execute(psycopg.sql.SQL('ALTER TABLE {} OWNER TO {}').format(psycopg.sql.Identifier(table),psycopg.sql.Identifier(new_owner)))
        try:
            with pytest.raises(ValueError,match='own product tables'):
                PostgresStore(runtime)
        finally:
            with psycopg.connect(owner) as db:
                db.execute(psycopg.sql.SQL('ALTER TABLE {} OWNER TO postgres').format(psycopg.sql.Identifier(table)))
                db.execute(psycopg.sql.SQL('REVOKE ALL ON {} FROM {}').format(psycopg.sql.Identifier(table),psycopg.sql.Identifier(new_owner)))

    assert store.member(TENANT,USER) and not store.member(other,USER)
    assert store.site(other,SITE) is None
    with psycopg.connect(runtime) as db:
        db.execute('SET LOCAL ROLE fw_accessfix_ai_rw')
        assert db.execute('SELECT count(*) FROM sites').fetchone()[0]==0
    with store.conn(TENANT) as db:
        assert db.execute('UPDATE sites SET origin=? WHERE tenant_id=?',('http://forbidden.invalid',other)).rowcount==0
        assert db.execute('DELETE FROM sites WHERE tenant_id=?',(other,)).rowcount==0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):db.execute('INSERT INTO sites VALUES(?,?,?,?,?,?)',(other,str(uuid4()),'http://forbidden.invalid',str(uuid4()),'UNVERIFIED',None))
    challenge=store.challenge(TENANT,SITE,'synthetic-token','2030-01-01T00:00:00Z')
    assert store.verify(TENANT,challenge)['status']=='VERIFIED'
    peers=[PostgresStore(runtime),PostgresStore(runtime)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids=list(pool.map(lambda i:peers[i%2].scan(TENANT,SITE,'a'*40,'b'*64,principal=USER,idempotency_key='pg-scan-001')['id'],range(8)))
    assert len(set(ids))==1;scan_id=ids[0]
    monkeypatch.setenv('ACCESSFIX_WORKER_TENANTS',TENANT)
    with ThreadPoolExecutor(max_workers=2) as pool:leases=list(pool.map(lambda store:store.claim_scan(20,30),peers))
    assert sum(row is not None for row in leases)==1
    old=next(row for row in leases if row)
    with store.conn(TENANT) as db:db.execute('UPDATE scans SET lease_until=? WHERE id=?',('2000-01-01T00:00:00Z',scan_id))
    newer=store.claim_scan(20,30)
    assert not store.complete_scan(TENANT,scan_id,old['lease_until'])
    assert store.complete_scan(TENANT,scan_id,newer['lease_until'])
    assert store.scan_source(TENANT,scan_id)['source_html'].startswith('<!doctype html>')
    assert store.scan_source(other,scan_id) is None
    with store.conn(TENANT) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('UPDATE scan_sources SET source_html=? WHERE scan_id=?',('tampered',scan_id))
    finding=store.findings(TENANT,scan_id)[0]
    proposal=store.proposal(TENANT,finding['id'],'a'*40,'c'*64)
    content=store.proposal_content(TENANT,proposal['id'])
    assert ' alt="' in content['patched_html'] and content['patch_text']
    assert store.proposal_content(other,proposal['id']) is None
    with store.conn(TENANT) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('UPDATE proposal_sources SET patched_html=? WHERE proposal_id=?',('tampered',proposal['id']))
    retested,status=store.retest(TENANT,proposal['id'],'a'*40,1)
    assert status=='OK' and retested['version']==2
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviews=list(pool.map(lambda index:peers[index].review(TENANT,proposal['id'],str(uuid4()),proposal['patch_sha'],'approve','passed',2),range(2)))
    assert sorted(result[1] for result in reviews)==['OK','STALE']
    assert next(result[0] for result in reviews if result[1]=='OK')[1]=='APPROVED'
    assert store.proposal_get(TENANT,proposal['id'])['version']==3
    with store.conn(TENANT) as db:
        assert db.execute('SELECT count(*) FROM reviews WHERE proposal_id=?',(proposal['id'],)).fetchone()[0]==1
    assert store.proposal_get(other,proposal['id']) is None
    next_scan=store.scan(TENANT,SITE,'d'*40,'b'*64)
    assert ScanWorker(store,WorkerConfig(lease_seconds=20,timeout_seconds=30)).run_once()
    assert store.get_scan(TENANT,next_scan['id'])['status']=='SUCCEEDED'
    from fastapi.testclient import TestClient
    from accessfix_ai.main import create_app
    from test_accessfix_flow import hdr
    monkeypatch.setenv('ACCESSFIX_DATABASE_URL',runtime)
    with TestClient(create_app()) as client:
        findings=client.get(f'/v1/scans/{scan_id}/findings',headers=hdr('scan:read'))
        assert findings.status_code==200 and findings.json()['items'][0]['rule_id']=='image-alt'
        job=client.get(f"/v1/jobs/{store.get_scan(TENANT,scan_id)['job_id']}",headers=hdr('job:read'))
        assert job.status_code==200 and job.json()['state']=='SUCCEEDED'
