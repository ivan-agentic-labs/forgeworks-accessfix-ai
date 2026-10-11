# Strict version input — 2026-10-11

Baseline: 087aa38071c71cde57532d1ae001c3a4ba120d36.

The API accepted boolean true, numeric string "1", and floating JSON 1.0 as version 1. Require strict integer inputs for expected_version; SpecForge also requires strict source_version. Existing positive integer bounds remain unchanged. Invalid request validation now returns a stable INVALID_REQUEST 422 problem envelope without echoing raw input or serializing nonfinite values.

Behavioral tests exercise real product HTTP routes with a synthetic authorized principal and spy on the existing store methods. Rejected requests cannot call mutation/generation methods. The 1e400 test uses syntactically valid JSON and covers safe nonfinite error handling. Integer versions 1, 2 and 2147483647 remain accepted by models. Tests use missing resource IDs to focus on the input boundary; this is not real customer acceptance.

Baseline new suite: 12 fail, 3 pass. Failures cover coercion, problem-envelope consistency and nonfinite error serialization; not every failed test represents newly accepted input. Candidate new suite: 15 pass. Full local suite: 232 pass, 8 skipped. AccessFix skips seven browser cases without local browser tooling and one PostgreSQL case; SpecForge skips one PostgreSQL case. Node session tests: 3 pass per repo. Bootstrap, static contracts and independent OpenAPI validation pass. Required GitHub workflow results must be checked before merge. No deployment or production acceptance claimed.
