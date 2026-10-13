from accessfix_ai.infrastructure.store import SITE, TENANT, Store


def test_sqlite_repeatable_read_keeps_snapshot_during_concurrent_commit(tmp_path):
    store = Store(str(tmp_path / "repeatable-read.db"))
    with store.conn() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            "INSERT INTO scans(tenant_id,id,site_id,commit_sha,policy_sha,status,created_at,job_id,attempt_count) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (TENANT, "11111111-1111-1111-1111-111111111111", SITE, "a" * 40, "b" * 64,
             "SUCCEEDED", "2026-10-13T09:00:00Z", "22222222-2222-2222-2222-222222222222", 1),
        )

    reader = store.conn(TENANT, repeatable_read=True)
    try:
        first = reader.execute(
            "SELECT status FROM scans WHERE tenant_id=? AND id=?",
            (TENANT, "11111111-1111-1111-1111-111111111111"),
        ).fetchone()["status"]
        assert first == "SUCCEEDED"
        with store.conn() as writer:
            writer.execute(
                "UPDATE scans SET status='FAILED' WHERE tenant_id=? AND id=?",
                (TENANT, "11111111-1111-1111-1111-111111111111"),
            )
        second = reader.execute(
            "SELECT status FROM scans WHERE tenant_id=? AND id=?",
            (TENANT, "11111111-1111-1111-1111-111111111111"),
        ).fetchone()["status"]
        assert second == "SUCCEEDED"
    finally:
        reader.close()

    with store.conn() as db:
        committed = db.execute(
            "SELECT status FROM scans WHERE tenant_id=? AND id=?",
            (TENANT, "11111111-1111-1111-1111-111111111111"),
        ).fetchone()["status"]
    assert committed == "FAILED"
