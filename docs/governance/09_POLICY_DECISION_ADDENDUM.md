# G1-D addendum — identity and audit authorization

**New critical review item (2026-10-09).** Earlier application-role grants gave tenant-scoped CRUD to the `memberships` table. Row-scoped membership visibility does not mean the application role should alter membership status or privilege level. Five candidate grants have been changed to `SELECT` only for that table. Provisioning and invitations must use a separately authenticated, audited, least-privilege identity workflow whose own DB permissions are **not yet designed or tested**. Features relying on generic membership writes are **disabled** until that workflow is complete.

The `audit_events` table remains SELECT+INSERT only for the generic app role; no UPDATE/DELETE, and its policies are SELECT and INSERT only. Deletion/retention requires a separately authorized and audited legal-compliance workflow.

**P0 caution:** `SET LOCAL app.tenant_id`/a custom GUC is an application-scoped selector, not an unfalsifiable identity. Service-level authorization, database permissions, SQL injection defense, least privilege, transaction pooling context reset, and cross-tenant negative tests remain mandatory. Composite FKs do not solve authorization.

**No production/security signoff.** These changes harden the *design candidate* only.
