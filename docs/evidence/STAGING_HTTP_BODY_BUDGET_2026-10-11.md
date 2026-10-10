# 2026-10-11 staged HTTP request budget

## Exact code and acceptance boundary
- Release source SHA: `d4b6319255d1540d2e8172e24aabc07de31cdb6b`.
- Railway staging deployment: `80cce2ea-2485-4782-a057-32518a081f8d`, observed `SUCCESS` with one running, zero crashed replica at checkpoint.
- Request budget: 8 MiB actual/declared body; maximum 16,384 chunks; malformed/oversized Content-Length bounded; invalid requests return 400/413.
- Tests are synthetic TestClient/pure-ASGI, not measured external attack traffic or rate-limiting proof.
- Railway source is explicitly pinned to this SHA; documentation-only commits after it need not be deployed.

## Exact CI receipts
- G1 Contract Verification: **success**, https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38087963623
- AccessFix MVP Application CI: **success**, https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38087963576
- AccessFix PostgreSQL Runtime Proof: **success**, https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38087963592
- AccessFix Disposable Chromium Patch Proof: **success**, https://github.com/ivan-agentic-labs/forgeworks-accessfix-ai/actions/runs/38087963610

## Scope and remaining evidence
All listed CI checks were `success` for the pinned source. Staging deployment `SUCCESS` confirms startup/health gates according to Railway, not full product functionality. External `/readyz` and authenticated business workflow tests could not be independently completed from this execution environment; owner/tenant membership provisioning and all G3-G6 acceptance remain OPEN.
