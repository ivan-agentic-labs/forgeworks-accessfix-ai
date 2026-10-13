# Target architecture — ForgeWorks portfolio: two applications / two domains

**Owner decision (2026-10-13):** Five existing product repositories collectively power ONE future ForgeWorks application and ONE domain. **SealAngel Work is a SEPARATE application on a second domain**, with its own planned repository. Actual domain names, DNS, ownership and production deployment are not yet decided or implied.

```text
Domain A (TBD)  --> ForgeWorks unified Web UI + BFF/SSO
                   /apishield     --> APIShield backend
                   /accessfix     --> AccessFix backend
                   /specforge     --> SpecForge backend
                   /agenttest     --> AgentTest backend
                   /datareconcile --> DataReconcile backend

Domain B (TBD)  --> SealAngel Work UI / API / worker / data (independent)
```

Keep five backend repositories independently versioned and tested. The portal should unify login, nav, workspace switching, billing/usage and customer experience **without** bypassing per-service authorization, tenant isolation or provider permission scopes. Set separate audience-bound tokens, deny by default, per-product release gates, monitored BFF route guards, and rollback boundaries. Do not merge database tables into a shared privilege domain simply to share a domain. A unified portal is not a production acceptance proof for any component.

Current stage: design/rollout target; no hostname registered or DNS changed by this documentation commit. See each repository's `docs/verification/CURRENT_GATE_EVIDENCE.md` and hosted runbooks for source-SHA-bound evidence.
