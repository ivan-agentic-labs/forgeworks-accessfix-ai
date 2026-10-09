# Operations, privacy, cost, release governance

## Deployment reference topology (provider-neutral)
- Separate development/staging/production accounts/projects, network boundaries, secrets, object buckets and databases. No production data in development by default.
- Inbound TLS → Next.js BFF → internal FastAPI → private PostgreSQL/worker; outbox dispatcher → managed queue; untrusted browser/code isolated away from control plane.
- Container images pinned by digest, least privilege workload identity, secrets in secret manager, dependency and image scanning, signed artifacts/provenance, protected branch, deploy approval, forward/back-compatible migrations and rollback.
- Each service exports traces, metrics, structured/redacted logs with `trace_id` and tenant pseudonym where appropriate; avoid logging raw prompts/docs/payment data by default.

## Operational gates (design-only, NOT achieved)
| Gate | Acceptance method | Required artifacts |
|---|---|---|
| Restore | PITR/backup actually restored into disposable region/project; reconcile effects | restore logs, checksum comparisons, owner approval |
| Rollback | Deploy failure + schema forward/backward compatibility simulation | image digests, migrate/rollback logs, app test |
| Outage | LLM outage, queue backlog, GitHub outage, object store unavailable | controlled fail-safe statuses, runbooks, metric samples |
| Tenant incident | Cross-tenant attempt triggers deny+alert, revoke tokens | incident drill, forensics and remediation |
| Quota | hard cap at tenant/job/provider; idempotent refund of unused reservation | cost breakdown, rejected over-budget calls |
| Vendor exit | export artifacts + DB without violating deletion restrictions | export/restore proof, contract/procurement review |

## Privacy-by-design checklist (requires counsel/owner)
- Map data: personal identifier, source-code/IP, API definitions, website snapshots, model traces, transaction data by owner/controller/processor; record region and cross-border flows.
- Establish purpose and lawful basis, minimal collection, subprocessors and model-provider data-use restrictions; no training on customer data by default unless documented customer authorization.
- Define retention at table/object/log/backup level; avoid false claims of instantaneous deletion from backups; document legal hold and rights request procedures.
- Contracts required before real users/data: Terms, Privacy Notice, DPA as applicable, incident response contacts, vendor DPAs, security disclosure policy, license and trademark review.
- Legal applicability to Indonesia incl. UU PDP must be reviewed in applicable context; this is NOT a statement of legal compliance.

## Financial guardrails
Cost worksheet per job: token input/output, retries, walltime sandbox, object storage, DB/queue, observability, support, egress. Use hard job-level and org-level token/runtime/storage quotas with admission control and kill-switch. **No numeric unit margin, pricing, SLO, RTO/RPO or SLA may be called achieved** until actual workload tests and vendor price/terms verification.

## Owner model
Solo founder can be `A` (accountable) for product, technical, finance, privacy decisions but cannot sign independent expert assessments for WCAG or finance accuracy simply by changing a spreadsheet. Design owner should obtain external/qualified reviews as needed before regulated/enterprise use. Approval record must include real name/role/date/evidence/hash and unresolved-risk decision.
