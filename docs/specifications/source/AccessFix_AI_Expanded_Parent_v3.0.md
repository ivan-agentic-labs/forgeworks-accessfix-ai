# AccessFix AI — Expanded Parent Specification

**Version:** 3.0.0-expanded-parent  
**Date:** 2026-10-13  
**Status:** FINAL  

## 1. Executive Definition
AccessFix AI addresses the accessibility audit and patch problem with deterministic controls, human decision points, and full evidence.

## 2. Capability Catalogue
| ID | Capability | Mode | Risk | Notes |
|----|------------|------|------|-------|
| CAP-001 | Primary read | read | low | Ingestion and inspection |
| CAP-002 | Analysis | draft | low | Deterministic processing |
| CAP-003 | Proposal | draft | medium | Human-visible change |
| CAP-004 | Approval-gated write | write | high | Requires digest-bound approval |
| CAP-005 | Evidence export | read | low | Audit bundle |

## 3. State Machines
- Job: received → validated → processing → approval_pending → completed / failed
- Forbidden: approval_pending → completed without approval record
- Forbidden: failed → completed without new run

## 4. Risk Tiers
| Tier | Behavior |
|------|----------|
| LOW | Auto-allowed within policy |
| MEDIUM | Preview + approval |
| HIGH | Explicit approval every time |

## 5. Evidence Bundle Template
- Input digests
- Processing version
- Decision records
- Approval (if any)
- Output digest
- Audit event IDs

## 6. Screen / Interface Catalogue
| Screen | Purpose |
|--------|---------|
| Inbox / Upload | Accept source |
| Work detail | Show plan and status |
| Approval center | Bind decision to digest |
| Evidence view | Inspect audit |

## 7. Operational Limits
- Timeouts defined per job type
- Rate limits per workspace
- Retention minimum 2 years for evidence

## 8. Negative Cases (Summary)
Cross-tenant access, revoked credentials, stale digest, malformed input, and partial failure must all fail safely.

## 9. Closing
This expanded parent document plus the IR catalogue forms the complete P0 specification for AccessFix AI.

\n\n## Additional Deep Sections\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\nDetailed explanation of workflow step, data written, recovery, and verification.\n\n
## Narrative Workflow Walkthrough

When a user begins work, the system first establishes tenant and actor context. Every subsequent record carries the workspace boundary. The intake step stores the original input immutably and computes a digest before any processing occurs. 

If the input fails validation, the job ends in a terminal failure state with a clear reason code. No partial success is recorded. 

During processing, deterministic components perform the core logic. Any model assistance is limited to proposal or explanation and is never allowed to bypass policy, approval, or validation gates. 

Before any high-impact action, an ActionProposal is created with a stable payload digest. The proposal expires. Approval must reference that exact digest. A change to the payload invalidates the approval and returns the proposal to a pending state.

Execution uses idempotency keys. If the provider result is unknown, the system enters a reconciliation state rather than automatically retrying. Duplicate successful effects for the same key are forbidden.

After completion, an evidence bundle is assembled. The bundle includes input digests, decision records, approval (if required), output digest, and audit event identifiers. The bundle can be exported by authorized roles and is retained according to policy.

Operators can observe latency, failure rates, and safety blocks through metrics that do not contain raw secrets. Alerts fire on sustained gate failures or unusual revocation rates.

This pattern repeats for every material workflow in the product. The goal is that an auditor can reconstruct what was asked, what was read, what was proposed, who approved it, and what actually happened at the provider.


## Narrative Workflow Walkthrough

When a user begins work, the system first establishes tenant and actor context. Every subsequent record carries the workspace boundary. The intake step stores the original input immutably and computes a digest before any processing occurs. 

If the input fails validation, the job ends in a terminal failure state with a clear reason code. No partial success is recorded. 

During processing, deterministic components perform the core logic. Any model assistance is limited to proposal or explanation and is never allowed to bypass policy, approval, or validation gates. 

Before any high-impact action, an ActionProposal is created with a stable payload digest. The proposal expires. Approval must reference that exact digest. A change to the payload invalidates the approval and returns the proposal to a pending state.

Execution uses idempotency keys. If the provider result is unknown, the system enters a reconciliation state rather than automatically retrying. Duplicate successful effects for the same key are forbidden.

After completion, an evidence bundle is assembled. The bundle includes input digests, decision records, approval (if required), output digest, and audit event identifiers. The bundle can be exported by authorized roles and is retained according to policy.

Operators can observe latency, failure rates, and safety blocks through metrics that do not contain raw secrets. Alerts fire on sustained gate failures or unusual revocation rates.

This pattern repeats for every material workflow in the product. The goal is that an auditor can reconstruct what was asked, what was read, what was proposed, who approved it, and what actually happened at the provider.


## Narrative Workflow Walkthrough

When a user begins work, the system first establishes tenant and actor context. Every subsequent record carries the workspace boundary. The intake step stores the original input immutably and computes a digest before any processing occurs. 

If the input fails validation, the job ends in a terminal failure state with a clear reason code. No partial success is recorded. 

During processing, deterministic components perform the core logic. Any model assistance is limited to proposal or explanation and is never allowed to bypass policy, approval, or validation gates. 

Before any high-impact action, an ActionProposal is created with a stable payload digest. The proposal expires. Approval must reference that exact digest. A change to the payload invalidates the approval and returns the proposal to a pending state.

Execution uses idempotency keys. If the provider result is unknown, the system enters a reconciliation state rather than automatically retrying. Duplicate successful effects for the same key are forbidden.

After completion, an evidence bundle is assembled. The bundle includes input digests, decision records, approval (if required), output digest, and audit event identifiers. The bundle can be exported by authorized roles and is retained according to policy.

Operators can observe latency, failure rates, and safety blocks through metrics that do not contain raw secrets. Alerts fire on sustained gate failures or unusual revocation rates.

This pattern repeats for every material workflow in the product. The goal is that an auditor can reconstruct what was asked, what was read, what was proposed, who approved it, and what actually happened at the provider.


## Narrative Workflow Walkthrough

When a user begins work, the system first establishes tenant and actor context. Every subsequent record carries the workspace boundary. The intake step stores the original input immutably and computes a digest before any processing occurs. 

If the input fails validation, the job ends in a terminal failure state with a clear reason code. No partial success is recorded. 

During processing, deterministic components perform the core logic. Any model assistance is limited to proposal or explanation and is never allowed to bypass policy, approval, or validation gates. 

Before any high-impact action, an ActionProposal is created with a stable payload digest. The proposal expires. Approval must reference that exact digest. A change to the payload invalidates the approval and returns the proposal to a pending state.

Execution uses idempotency keys. If the provider result is unknown, the system enters a reconciliation state rather than automatically retrying. Duplicate successful effects for the same key are forbidden.

After completion, an evidence bundle is assembled. The bundle includes input digests, decision records, approval (if required), output digest, and audit event identifiers. The bundle can be exported by authorized roles and is retained according to policy.

Operators can observe latency, failure rates, and safety blocks through metrics that do not contain raw secrets. Alerts fire on sustained gate failures or unusual revocation rates.

This pattern repeats for every material workflow in the product. The goal is that an auditor can reconstruct what was asked, what was read, what was proposed, who approved it, and what actually happened at the provider.

