# accessfix-ai: Audit-log permission contract (design candidate)

- Database application role: `fw_accessfix_ai_rw`.
- `audit_events` grants: SELECT/INSERT only, not UPDATE/DELETE/TRUNCATE.
- Row-level policies: explicit SELECT and INSERT with `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`. No FOR ALL.
- Application must set transaction-scoped, validated tenant context. SQL must never be composed from model output or user input.
- Privileged migration, correction, retention or lawful erasure operations require a separate approved role, case identifier, logs and authorization. Current script is **not** a privacy-deletion implementation.
- Verify on disposable PostgreSQL: `has_table_privilege` by role, `pg_policies`, missing tenant context, tenant A/B reads and inserts, denied UPDATE/DELETE/TRUNCATE; test owner/BYPASS role separately.
- **Status:** DESIGNED + STATIC_CHECKED; database runtime NOT RUN; external review/signoff OPEN.
