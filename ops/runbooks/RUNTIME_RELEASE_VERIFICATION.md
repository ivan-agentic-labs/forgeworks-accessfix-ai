# Runtime release verification

This runbook distinguishes source verification, a deployed staging identity, and actual production acceptance. A synthetic test signature is never a reviewer approval.

## Hosted runtime

The Docker entrypoint is scripts/start_service.py. It accepts APP_ENV=staging or production with AUTH_MODE=supabase, the product's least-privilege PostgreSQL URL, no development secret and no seed fixture. scripts/start_staging.py is a staging-only compatibility entrypoint.

The Python base image is pinned by registry digest. requirements-runtime.lock is installed with --require-hashes in both the image and application CI. The digest was independently retrieved and verified from public ECR on 2026-10-12; update it only after checking registry content and regression tests.

GET /versionz reports product, environment, revision_sha and a bounded runtime_manifest. Railway's RAILWAY_GIT_COMMIT_SHA is preferred; FORGEWORKS_RELEASE_SHA is a fallback pin when platform metadata is absent. If both are present they must match. Hosted identity with missing or malformed revision fails with 503.

The manifest covers Python runtime source, web HTML/JS/CSS, source contracts, SQL migrations, hosted entrypoints, storage probe, runtime lock, Dockerfile and railway.toml. It excludes documentation, tests and the release record. Symlinks, path escapes, over 256 files or more than 8 MiB fail. Its selected-source fingerprint is cached on first use in each immutable deployment; this is not continuous filesystem tamper detection, a signed container attestation, or a complete dependency provenance proof.

## Request telemetry

FORGEWORKS_HTTP_LOGS=1 enables JSON http.request records with a generated request ID, product, method, registered route template, status, duration, completion and handler-exception flags. Raw paths, query strings, request headers/bodies, inbound request IDs, tenant IDs and object IDs are excluded. Uvicorn access logging is disabled. Responses receive no-referrer, nosniff and a generated request ID.

GET /metricsz requires a separate server-only METRICS_READ_SECRET: 32–256 printable ASCII characters, no whitespace, and different from auth/artifact secrets. Missing or incorrect authorization returns 401 after configuration. Absent/invalid configuration returns 503. Never place the credential in the web console, URLs, GitHub source or release evidence. The endpoint uses Cache-Control: no-store.

Counters are bounded to 256 method/registered-route/status-class series. Duration sum/max, incomplete responses and handler exceptions are per process since startup, reset on deploy, and do not establish fleet p95, persistence, alert delivery or a load SLO. A started stream preserves its original status on failure and increments incomplete/exception counters. Unhandled hosted errors before response start return a sanitized 500; development exceptions remain visible.

Railway edge tracing can be enabled independently of application instrumentation. Never include request payloads or credentials in trace evidence.

## Staging promotion

1. Read the current main and pinned Railway revision. Record the live revision and deployment ID for rollback.
2. Require successful relevant CI at the exact proposed source SHA, including application regression, contracts and PostgreSQL negative tests. Inspect the actual jobs and logs rather than run labels alone.
3. Stage Railway source with repo, branch=main and commitSha=<tested SHA>. Set matching FORGEWORKS_RELEASE_SHA, FORGEWORKS_HTTP_LOGS=1 and a freshly generated metrics credential. Preserve auth, least-privilege database logins, private S3 storage and predeploy storage probes.
4. Review all staged environment changes. Apply only the intended non-destructive patch. Poll the actual service deployment to terminal SUCCESS at that SHA.
5. Run python scripts/probe_deployed_release.py --expected-revision <tested SHA> from that source. It calls only a fixed product staging origin, rejects redirects, bounds response sizes, verifies health/readiness, exact revision/fingerprint and anonymous business/metrics denial. An operator can additionally set METRICS_READ_SECRET locally to verify private metrics; no credential is printed.
6. After success, commit ops/releases/staging.json with the actual revision, fingerprint, deployment ID, CI URLs and timestamp. The Deployed Release Identity Proof workflow reruns the public identity/access proof from that reviewed record. A documentation-only record commit is distinct from the runtime source pin.

On failure, restore BOTH the previous commitSha and FORGEWORKS_RELEASE_SHA. Database rollback/restore is a separate reviewed procedure: reverting source does not reverse schema or data changes.

## Production acceptance

Production requires independently configured Railway project/environment and Supabase project IDs. Relabelling the known shared staging infrastructure as production is rejected.

An actual trusted operator provides PRODUCTION_ACCEPTANCE_PUBLIC_KEY_PEM (Ed25519) and a regular, non-symlink PRODUCTION_ACCEPTANCE_FILE. Keep the signing private key outside the application/repository. The receipt binds product, production environment, exact revision, runtime fingerprint, infrastructure IDs, issued/expiry times and reviewed controls.

Required PASS controls: authenticated-own-tenant, authenticated-cross-tenant, session-revocation, product-integration, storage-lifecycle, load-slo, restore-dr, security-review, domain-review, privacy-legal, owner-release. Each has an HTTPS evidence URI without credentials/query/fragment, SHA-256 evidence digest, and an actual reviewer. OPEN, missing, duplicate, malformed, future, expired, tampered or wrong-target receipts are rejected.

infra/environments/production/acceptance-template.json is deliberately unsigned and OPEN; it cannot enable production. No actual production receipt has been issued as part of this change. Unit-test signatures are synthetic and do not constitute factual evidence, reviewer expertise, legal clearance or owner consent.

Signing protocol: JSON envelope keys are algorithm, key_id, payload, signature. algorithm=Ed25519; key_id is SHA-256 of the raw 32-byte public key. Sign UTF-8 json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False). signature is canonical padded URL-safe Base64 of 64 bytes. The receipt schema is forgeworks-production-acceptance-v1 with UTC YYYY-MM-DDTHH:MM:SSZ validity timestamps.

Verification is a startup gate, not continuous review of receipt expiry. A fresh deployment/restart needs a currently valid receipt. The application validates a trusted attestation, not the factual contents of externally hosted evidence; the operator must review the exact artifact/digest before signing.

## Open external gates

Authenticated two-tenant hosted tests require approved live test identities and current sessions; all previously revoked memberships remain revoked. Product acceptance needs the actual GitHub App/provider/runner/owned-site/domain/corpus inputs relevant to each product. Storage retention/deletion and restore/DR need observed infrastructure results. Domain expertise, privacy/legal review, production budget and ownership approvals cannot be inferred from synthetic CI or uptime.

The connected Supabase organization was Free on 2026-10-12. Leaked-password protection requires Pro or higher; upgrading is a cost decision, and disabled protection remains an open gate. RLS-enabled tables with no public policies and no anon/authenticated privileges intentionally deny public database access; do not create permissive policies to clear an informational advisor.
