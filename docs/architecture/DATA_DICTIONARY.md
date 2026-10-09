# AccessFix AI — Data model, relational constraints and transaction design

## Canonical relational aggregates (v4.1: authoritative)

Previous v4.0 terminology is mapped to **one** physical table per aggregate. Never generate two tables for one alias.

| Previous functional term | Canonical table | Mapping |
|---|---|---|
| `sites` | `sites` | Unchanged |
| `ownership_challenges` | `verification_challenges` | Renamed alias |
| `scan_jobs` | `scan_jobs` | Unchanged |
| `scan_targets` | `scan_targets` | Unchanged |
| `accessibility_findings` | `findings` | Renamed alias |
| `source_mappings` | `source_mappings` | Unchanged |
| `fix_proposals` | `fix_proposals` | Unchanged |
| `retest_results` | `retest_results` | Unchanged |
| `manual_reviews` | `manual_reviews` | Unchanged |

All canonical tables must have a physical column contract below; shared per-product platform tables are covered in governance.

## RLS and role design (not executed migration)
- Separate migration/owner role from API/worker read-write roles; application roles never hold BYPASSRLS/superuser or table owner privileges.
- Enable RLS and FORCE where suitable, separate `USING` and `WITH CHECK`; set `app.tenant_id` with `SET LOCAL` inside transactional request after auth membership resolution.
- Transaction-pool reused sessions must not inherit tenant variables. Test PgBouncer/pooled mode after selected provider is known.
- Compound FK + membership/policy validation is required despite RLS; no cross-tenant object keys or storage ACL inheritance.
- Synthetic two-tenant fixtures cover SELECT/INSERT/UPDATE/DELETE, foreign keys, joined views, workers and pooled connections.

## SQL transaction boundaries
1. Job accepted: domain validation + write `jobs` + `outbox` + `idempotency_records` in a **single commit**; return 202 only after commit succeeds.
2. Worker lease: visibility timeout/fencing token; dedupe message ID in inbox; at-least-once delivery with idempotent handlers.
3. Approval: compare `version` and content SHA, actor role+tenant, policy, expiry and external permission; conflicting writers return 409.
4. External effect: commit unique effect reservation → invoke outside DB transaction → store external ID/outcome; timeout -> `UNKNOWN_REMOTE` -> provider-specific lookup/reconciliation; never retry blindly.
5. Artifact: quarantine content until checksum, MIME, virus/format checks and final tenant-owner authorization; download intent scoped and revocation bounded by provider semantics.

## Domain-specific invariants and source column dictionary
No arbitrary scan target; proof of domain + repository control, short expiry; browser runs without cloud credentials; connect-time egress denylist enforced outside browser; accessibility claims constrained by WCAG-EM.

# AccessFix AI — proposed physical model, not executed DDL

## Shared physical schema model (applied independently per product)

All tenant-owned tables: `tenant_id UUID NOT NULL`, `id UUID NOT NULL`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `PRIMARY KEY (tenant_id,id)`.
A child FK must use `(tenant_id,parent_id) REFERENCES parent(tenant_id,id)`; foreign UUID alone is insufficient. Database roles: migration owner != API/worker; API/worker roles have no SUPERUSER/BYPASSRLS privileges. Proposed RLS uses `tenant_id = nullif(current_setting('app.tenant_id',true),'')::uuid` with `USING` and `WITH CHECK`; tenant context set `SET LOCAL` **inside a transaction** using server-verified membership, never client supplied. Connection pool reuse without transaction isolation is prohibited.

Other independent core tables for every product: `tenants`, `users`, `memberships`, `jobs`, `outbox_events`, `inbox_receipts`, `idempotency_records`, `audit_events`, `artifact_references` (tenant-scoped). Their schema and cleanup/retention must be supplied by the shared-platform contract before migration code.

Immutable audit records require explicit retention/legal basis. Event idempotency does not imply exactly-once external effects; use reconciliation and unique natural business keys. Soft deletion alone is not a privacy deletion implementation.


## Domain tables

### `sites`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `canonical_origin` | `text NOT NULL` |
| `repository_id` | `uuid NOT NULL` |
| `verification_status` | `text NOT NULL` |
| `verified_until` | `timestamptz` |
| `revoked_at` | `timestamptz` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, canonical_origin)`.
**Domain constraints:** canonical origin must be https except explicit local fixture policy.

### `verification_challenges`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `site_id` | `uuid NOT NULL` |
| `token_sha256` | `char(64) NOT NULL` |
| `expires_at` | `timestamptz NOT NULL` |
| `used_at` | `timestamptz` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, token_sha256)`.
**Scoped FK:** `(tenant_id,site_id) -> sites(tenant_id,id)`.
**Domain constraints:** single-use token; revoke on ownership change.

### `scan_jobs`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `site_id` | `uuid NOT NULL` |
| `repo_commit_sha` | `text NOT NULL` |
| `network_policy_sha256` | `char(64) NOT NULL` |
| `status` | `text NOT NULL` |
| `budget_pages` | `int NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `INDEX (tenant_id, site_id, created_at DESC)`.
**Scoped FK:** `(tenant_id,site_id) -> sites(tenant_id,id)`.
**Domain constraints:** ownership verified for each scan; revalidate redirects.

### `findings`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `scan_id` | `uuid NOT NULL` |
| `rule_id` | `text NOT NULL` |
| `selector` | `text NOT NULL` |
| `fingerprint` | `char(64) NOT NULL` |
| `severity` | `text NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, scan_id, fingerprint)`.
**Scoped FK:** `(tenant_id,scan_id) -> scan_jobs(tenant_id,id)`.
**Domain constraints:** zero findings is not WCAG conformance.

### `source_mappings`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `finding_id` | `uuid NOT NULL` |
| `repository_path` | `text NOT NULL` |
| `line_number` | `int NOT NULL` |
| `confidence` | `numeric(4,3) NOT NULL` |
| `evidence_hash` | `char(64) NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; No additional domain index proposed.
**Scoped FK:** `(tenant_id,finding_id) -> findings(tenant_id,id)`.
**Domain constraints:** map ambiguity blocks automated patch.

### `fix_proposals`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `version` | `int NOT NULL DEFAULT 1 CHECK (version >= 1)` |
| `finding_id` | `uuid NOT NULL` |
| `base_sha` | `text NOT NULL` |
| `patch_sha256` | `char(64) NOT NULL` |
| `retest_status` | `text NOT NULL` |
| `visual_status` | `text NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id, finding_id, patch_sha256)`.
**Scoped FK:** `(tenant_id,finding_id) -> findings(tenant_id,id)`.
**Domain constraints:** patch must be source linked.

### `manual_reviews`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `proposal_id` | `uuid NOT NULL` |
| `reviewer_id` | `uuid NOT NULL` |
| `proposal_version` | `int NOT NULL CHECK (proposal_version >= 1)` |
| `reviewed_patch_sha256` | `char(64) NOT NULL` |
| `decision` | `text NOT NULL` |
| `manual_check_status` | `text NOT NULL` |
| `reviewed_at` | `timestamptz NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; No additional domain index proposed.
**Scoped FK:** `(tenant_id,proposal_id) -> fix_proposals(tenant_id,id)`.
**Domain constraints:** approval cannot be automated; approved reviews bind the current proposal version and patch SHA; required manual checks must pass, and a stale proposal version fails closed.

## Transaction boundaries

- Creating a job: validate actor+tenant+resource; insert job and outbox in same PostgreSQL commit, then return HTTP 202. Broker delivery happens after transaction commit.
- External mutation: reserve unique business effect key and approval snapshot inside DB transaction; call external API outside transaction; reconcile remote effect ID after uncertain timeout.
- Final approval: optimistic `version`/If-Match plus exact content digest; reject stale updates.
- Tenant isolation test: same IDs searched under different tenant contexts must not disclose existence or associated storage objects.

## Schema proof not yet collected

Column design is not a generated migration and has not been executed against PostgreSQL. FK/index names, enum strategy, JSONB evidence fields, full SQL migration, query plans, retention and concurrency isolation must be validated during implementation.


> **DDL status:** conceptual physical design; no migration executed or database schema proved. Exact FK constraint names, indexes, query plans, row locks and RLS enforcement require G2/G4 evidence. The appended v3.2 dictionary is historic source input, not an executed implementation.


## v4.1 — Added physical model definitions and closure notes

These are **design-only table contracts**, not executed migrations. Explicit FK/index names, datatype behavior, RLS, and transaction isolation remain subject to PostgreSQL tests.

### `scan_targets`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `site_id` | `UUID NOT NULL` |
| `origin` | `TEXT NOT NULL` |
| `normalized_url` | `TEXT NOT NULL` |
| `scope_digest` | `CHAR(64) NOT NULL` |
| `crawl_depth` | `INTEGER NOT NULL DEFAULT 0` |
| `approved_at` | `TIMESTAMPTZ` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id,site_id,normalized_url)`.
**Scoped FK:** `(tenant_id,site_id) -> sites`.
**Domain constraints:** Targets must remain within verified host/scope, private IPs and redirect pivots prohibited; `crawl_depth >= 0`.

### `retest_results`

| Column | PostgreSQL design type / rule |
|---|---|
| `tenant_id` | `UUID NOT NULL` |
| `id` | `UUID NOT NULL` |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` |
| `proposal_id` | `UUID NOT NULL` |
| `scan_job_id` | `UUID NOT NULL` |
| `tool_version` | `TEXT NOT NULL` |
| `before_violations` | `INTEGER NOT NULL` |
| `after_violations` | `INTEGER NOT NULL` |
| `evidence_sha256` | `CHAR(64) NOT NULL` |
| `status` | `TEXT NOT NULL` |

**Keys/indexes:** `PRIMARY KEY (tenant_id,id)`; `UNIQUE (tenant_id,proposal_id,scan_job_id,tool_version)`.
**Scoped FK:** `(tenant_id,proposal_id) -> fix_proposals`; `(tenant_id,scan_job_id) -> scan_jobs`.
**Domain constraints:** Non-negative counters; `after_violations=0` never implies full WCAG conformance; review tests manual and assisted.


### Domain-specific mapping decisions

- `verification_challenges` is canonical database name for ownership challenge resource.
- `findings` is canonical for accessibility findings. If a scan requires many targets, `scan_jobs` must reference or snapshot the approved set of `scan_targets`.
