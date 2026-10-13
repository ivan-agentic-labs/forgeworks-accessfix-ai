# AccessFix AI — revised owner product specification (2026-10-13)

**Source basis:** `AccessFix_AI_Full_Detailed_v2.2.md`, `AccessFix_AI_Expanded_Parent_v3.0.md`, `AccessFix_AI_Ultra_Detailed_Extension.md` and the matching `IR/` catalogue in the owner's uploaded `ForgeWorks_5_Projects_Long_Narrative_plus_IR.zip`.

**Document state:** owner design requirements; not independent evidence of implemented or hosted functionality. This replaces the old bootstrap-era design-review and handoff prose, while preserving actual code/contracts/migrations/tests and dated audit evidence.

## Product scope
Website accessibility auditing and evidence-backed remediation. It remains a separate backend service connected through the planned shared ForgeWorks front end; not a separate production domain.

## Owner P0 workflow / controls
1. Begin a DNS TXT or `.well-known` ownership challenge, exact token match, expiry 24 hours; failed challenge blocks scanning.
2. Allow only verified HTTPS target with SSRF/private-IP/metadata endpoint and unsafe-redirect checks.
3. Run isolated Playwright + axe scan and record findings, rule id, node selector, page-type coverage and tool version.
4. Map results to Next.js/React source only when confidence is high; medium/low produce finding-only output.
5. Prepare patch, run targeted and lightweight full retest, require keyboard/focus/screen-reader human review.
6. Bind approval to exact patch digest and ownership; create draft PR only; never auto-merge.
7. Revocation aborts the workflow safely; export source/scan/coverage/retest/approval evidence.

The current implementation candidate adds a **local fixture-only evidence manifest** for this export step. It is not a signed audit artifact, does not include raw source or patch bytes, and does not satisfy production/privacy/retention or independent accessibility acceptance. See the dated [evidence-export change advisory](../architecture/EVIDENCE_EXPORT_CHANGE_ADVISORY_2026-10-13.md); the remaining limits and release gates in this specification still apply.

## Limits and non-goals
Owner-designed challenge: DNS TXT up to three retries at 30-second intervals, max five minutes; well-known file up to two retries. Two concurrent scans per workspace by default. Evidence retention proposed two years (must pass privacy review). Automated checks cannot certify full WCAG compliance.

## Implementation records and proof
The uploaded catalogue contains **400 IR IDs but 10 distinct topic patterns**, each repeated 40 times. ID count is not completion count. The distinctive topics are:

- 01. ownership challenge
- 02. network policy
- 03. isolated scan
- 04. coverage calculation
- 05. source mapping
- 06. patch generation
- 07. retest
- 08. human review
- 09. draft PR
- 10. permission revocation

For each topic, bind the implemented source file, requirement ID, positive/negative test, fixture digest, result, commit SHA, environment, reviewer and known limits. A generic repeated checklist is not a passed test.

## Production acceptance
The latest repository source and actual hosted runtime take precedence over an older blueprint's claim of implementation. Explicitly verify real identity and authorization, RLS/tenant isolation, bounded provider permissions, reconciliation, audit, backup/restore and domain-review acceptance before marking RELEASED. Current gate remains open until source-SHA-bound evidence is accepted.

See [shared-app boundary](../platform/ONE_APP_FIVE_SERVICES.md), [current gate evidence](../verification/CURRENT_GATE_EVIDENCE.md) and [hosted runbook](../../ops/runbooks/RUNTIME_RELEASE_VERIFICATION.md).

## Complete uploaded source

Read [the complete owner documents and IR catalogue](source/README.md). These files are preserved byte-for-byte; this page is a summary. The source index records each file size and Git blob SHA.
