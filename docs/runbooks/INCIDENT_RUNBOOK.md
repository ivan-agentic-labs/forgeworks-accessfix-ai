# Incident runbook — accessfix-ai

Scope: staging service `accessfix-ai` (Railway project *ForgeWorks AI staging*, env `staging`,
service id `16693650-fec8-48e4-b934-e032dd391808`), Supabase project `fljekuwplgkrpdoajyhn`, schema `fw_accessfix_ai`.
Fits `docs/governance/04_OPERATIONS.md` (incident classes), `05_RELEASE_CHANGE_CONTROL.md`
(rollback/change control) and `03_DATA_SECURITY.md` (tenant data). There is no production
environment yet; adapt IDs when one exists.

## 1. Detection
- Scheduled GitHub Actions: *Staging Public Readiness* (~6 h), *Staging Release Drift*,
  *Deployed Release Identity Proof*; APIShield hosts five-product inventory/live integration.
- Manual: `curl -fsS https://accessfix-ai-staging.up.railway.app/healthz` and `/readyz` (both must be 200);
  `/versionz` shows the deployed release SHA.
- Railway: service deployments, deploy/HTTP logs (filter `@status:500`), healthcheck `/readyz`.
- Supabase: Security/Performance Advisors, Postgres logs.
- Gap: no paging/alerting service yet (see production-readiness checklist).

## 2. Severity
| Sev | Definition | Response |
|---|---|---|
| SEV1 | Cross-tenant data exposure, credential leak, data loss/corruption | Stop traffic (scale down / remove domain), revoke secrets, owner notified immediately |
| SEV2 | Service down (`/readyz` ≠ 200 > 10 min) or core workflow broken | Roll back within 30 min |
| SEV3 | Degraded latency/errors, single feature broken, workaround exists | Fix forward next business day |
| SEV4 | Cosmetic / CI-only flake | Ticket |

Any suspected tenant-isolation breach is SEV1 until disproven (04_OPERATIONS: deny + alert, revoke tokens).

## 3. Triage checklist
1. Note start time (WIB + UTC), symptom, affected endpoints, release SHA from `/versionz`.
2. Check latest Railway deployment and whether it matches the expected `main` commit.
3. Check deploy logs around the start time; check Supabase status and connection limits.
4. Decide: rollback (bad release) vs. config/infra fix vs. DB restore.

## 4. Rollback (Railway)
- Preferred: Railway dashboard → service → Deployments → last known-good deployment → **Redeploy**
  (or Railway MCP/CLI `redeploy` of that deployment id).
- Alternative: `git revert <bad-sha>` on `main` (local tests first, single push); CI must be green
  before Railway deploys (enable *Wait for CI* on the service).
- Verify: `/healthz`, `/readyz` 200 and `/versionz` shows the rolled-back SHA; rerun
  *Staging Public Readiness* via `workflow_dispatch`.

## 5. Database restore
- Migrations are forward-only SQL in the repo; never hand-edit staging. Fix forward with a new
  migration whenever possible.
- Current plan is Supabase **Free**: no PITR; only the platform's limited daily backups. Before
  any risky change take a logical dump: `pg_dump --schema=fw_accessfix_ai --no-owner` with the owner DSN.
- Restore: into a fresh database first, verify table digests/RLS flags (pattern from
  `scripts/verify_disposable_restore.py` where present), then switch DSN or re-import the schema.
- Data-loss incidents are SEV1; record RPO actually achieved.

## 6. Communication
- Single incident owner (Ivan) and one channel (1:1 chat). Updates: SEV1 every 30 min, SEV2 every 60 min.
- Include: impact, start time, current status, next update time. No secrets or customer data in messages.
- Tenant notification for confirmed data exposure follows 03_DATA_SECURITY and legal advice.

## 7. Postmortem (SEV1/SEV2 within 5 working days)
Blameless; timeline, root cause, detection gap, what went well/poorly, action items with owners
and dates, evidence (CI runs, deployment ids, log excerpts). Store under
`docs/evidence/INCIDENT_<YYYY-MM-DD>.md` and link from `docs/verification/EVIDENCE_INDEX.md` if present.
