# Contribution policy
All changes require review against product contracts, tenant isolation, negative tests and risk controls. Never commit `.env` files, real customer data or tokens. Candidate database SQL is review-only; avoid activating external tool execution. Do not claim production readiness based on static checks.

## Owner-authorized main workflow (2026-10-13)

The owner authorized direct commits to `main` for routine documentation and small, reversible engineering changes. Review the diff and run checks appropriate to the change before committing; record the exact source SHA and check scope. A separate pull request is optional for these changes.

Use a pull request for substantial authentication/authorization changes, database migrations, cross-product integration or major dependency upgrades, so relevant tests can be reviewed before merging. Existing branch protections and CI checks continue to apply. Never merge a failing change merely to reduce the number of open pull requests. A direct commit or merged PR is not proof of deployed or production acceptance.

Dependabot continues to propose dependency updates through pull requests. Merge reviewed updates only with relevant passing checks; diagnose failing upgrades separately. Historical merged PRs remain part of the audit trail.
