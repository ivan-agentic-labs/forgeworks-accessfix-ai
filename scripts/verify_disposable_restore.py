"""Compare logical backup/restore of fresh CI databases; never production or customer data."""
import hashlib
import importlib
import json
import os
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo


def snapshot(dsn):
    result = {}
    with psycopg.connect(dsn) as db:
        tables = [row[0] for row in db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
        for table in tables:
            rows = db.execute(sql.SQL("SELECT to_jsonb(t) FROM {} t").format(sql.Identifier('public',table))).fetchall()
            documents = sorted(json.dumps(row[0], sort_keys=True, separators=(',',':')) for row in rows)
            columns = db.execute("SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(table,)).fetchall()
            constraints = db.execute("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=%s::regclass ORDER BY conname",('public.'+table,)).fetchall()
            flags = db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass",('public.'+table,)).fetchone()
            policies = db.execute("SELECT polname,polpermissive,polcmd,pg_get_expr(polqual,polrelid),pg_get_expr(polwithcheck,polrelid),ARRAY(SELECT rolname FROM pg_roles WHERE oid=ANY(polroles) ORDER BY rolname) FROM pg_policy WHERE polrelid=%s::regclass ORDER BY polname",('public.'+table,)).fetchall()
            triggers = db.execute("SELECT tgname,pg_get_triggerdef(oid),tgenabled,pg_get_functiondef(tgfoid) FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal ORDER BY tgname",('public.'+table,)).fetchall()
            grants = db.execute("SELECT grantee,privilege_type,is_grantable FROM information_schema.role_table_grants WHERE table_schema='public' AND table_name=%s ORDER BY grantee,privilege_type,is_grantable",(table,)).fetchall()
            result[table] = {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(documents,separators=(',',':')).encode()).hexdigest(),'columns':columns,'constraints':constraints,'rls_flags':flags,'rls_policies':policies,'triggers_and_functions':triggers,'grants':grants}
    return result


def main():
    info = conninfo_to_dict(os.environ['FW_DISPOSABLE_OWNER_DSN'])
    if os.getenv('G1_DISPOSABLE_DB')!='yes' or info.get('host') not in {'localhost','127.0.0.1'} or info.get('dbname')!='forgeworks_runtime':
        raise SystemExit('Refusing non-disposable database configuration')
    restored = {**info,'dbname':'forgeworks_restore'}
    before, after = snapshot(make_conninfo(**info)), snapshot(make_conninfo(**restored))
    if not before or before!=after:
        raise SystemExit('Logical backup/restore differs in schema/table data digests')
    module = importlib.import_module(os.environ['FW_PRODUCT_MODULE']+'.infrastructure.postgres_store')
    login = {**restored,'user':'fw_runtime_test','password':'synthetic-local-runtime-test-only'}
    store = module.PostgresStore(make_conninfo(**login))
    tenant='00000000-0000-0000-0000-000000000001'
    actor='00000000-0000-0000-0000-000000000010'
    assert store.member(tenant,actor)
    assert not store.member(tenant,'unmapped-oidc-subject')
    with psycopg.connect(make_conninfo(**login)) as db:
        db.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(module.ROLE)))
        assert db.execute('SELECT count(*) FROM memberships').fetchone()[0]==0
    print(json.dumps({'check':'disposable logical restore and restored membership/RLS','tables':len(before),'rows':sum(x['rows'] for x in before.values()),'result':'PASS','limits':'Not PITR, regional failover, production RTO/RPO or operational signoff'},sort_keys=True))


if __name__=='__main__':
    main()
