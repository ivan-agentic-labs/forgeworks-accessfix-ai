# AccessFix AI — P0 Product Requirements & Scope

**Target buyer:** Web engineering lead, agency, dan pemilik situs.

**Measurable user promise:** Audit aksesibilitas untuk target yang kepemilikannya terverifikasi, usulkan perbaikan pada source yang dapat dipetakan, lalu buat draft PR setelah retest dan review manusia.

## P0 end-to-end workflow
Domain/repo ownership proof → allowlist target → isolated browser + axe → temuan beserta cakupan scan → DOM-to-source evidence → patch proposal → browser retest + lint/build → manual keyboard/screen-reader review → approval → draft PR.

## Included in P0
- Website HTTPS dengan ownership challenge terverifikasi
- Audit sebagian aturan otomatis dan laporan cakupan
- Satu repo Next.js/React yang didukung untuk source patch
- Manual review wajib sebelum PR

## Explicitly out of scope
- Klaim konformitas WCAG menyeluruh dari automated scan
- Penjelajahan bebas URL dan jaringan privat
- Perbaikan konten pihak ketiga yang tidak dikendalikan pengguna
- Auto-merge perubahan aksesibilitas

## Roles & permission model
- `org_owner`: billing, org settings, members, quotas; does not automatically grant bypass to data policy.
- `org_admin`: invites within same tenant, configures allowed integrations, reviews impact.
- `editor`: creates runs/imports/draft analyses, cannot approve their own high-impact external write if separation-of-duty policy enables it.
- `reviewer`: approves signed revision/digest within policy and time window.
- `auditor`: read-only access to redacted audit + evidence.
- `service_worker`: machine identity with narrowly scoped effect grants, never unrestricted user impersonation; the BFF carries verified user access claims server-side.

## Product value and validation
Business hypothesis: targeted buyer experiences frequent repeatable failure that is expensive enough to justify adoption. Evidence needed: 3–5 structured buyer interviews, their current workaround, time/expense per incident, willingness to share consented/synthetic fixtures, and pilot pass criteria. These are **future prerequisites**, not interviews already done.

**North-star and guardrail metrics:** supported rule coverage by page type, confirmed finding precision on labeled pages, patch retest pass rate, manual-review completion rate, false accessibility certification claims = 0.

## P0 completion criteria
1. One authorized end-to-end job reaches its intended output with reproducible fixture and trace.
2. Duplicate requests / partial external timeout / revocation / cross-tenant access fail safely.
3. Every material output cites a source/digest/rule version and has a reviewer action where needed.
4. Evidence of output correctness must come from deterministic assertion and human review of edge cases; AI alone does not sign off.
5. Security, privacy, budget, and recovery gate conditions defined in governance are respected.

## Critical G1 assumptions pending
- Target W3C WCAG edition/success criteria and test matrix reviewer needed
- Browser isolation provider and network egress controls need test
- DOM-to-source support matrix depends on pilot framework corpus

**Scope owner:** Founder/Product. **Security owner:** assigned reviewer. **Domain validator:** qualified buyer/SME. **Status:** PROVISIONAL, awaiting actual signed reviews.
