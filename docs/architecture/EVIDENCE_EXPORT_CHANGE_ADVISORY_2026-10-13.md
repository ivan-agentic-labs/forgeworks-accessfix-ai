# AccessFix fixture evidence export — change advisory

**Status:** implementation candidate for PR review; not a production or G1-E acceptance record.

## Scope

Adds `GET /v1/scans/{scan_id}/evidence-export`, a read-only JSON manifest for a completed local synthetic scan. It requires the existing tenant membership and `scan:read` scope. The handler only operates when `APP_ENV` is explicitly `development` or `test` (missing/unknown values fail closed), and only when the scan belongs to `http://fixture.local`. Unknown or cross-tenant scan IDs remain hidden as not found; incomplete scans are rejected.

The manifest contains scan and local-source hashes, byte length, rule/fixture coverage limits, finding fingerprints and evidence digests, proposal/retest digests and status, and review actor/decision/status. Content-derived source/patch digests are unkeyed identifiers for this synthetic fixture only; they can be guessable and **do not provide confidentiality**. No separate alt-text digest is exported. `bundle_sha256` hashes minified UTF-8 JSON with that property omitted: recursively sort object keys in ascending Unicode code-point order, preserve array order, UTF-8 encode non-ASCII characters, use JSON string escapes, allow no floats, and add no trailing newline. The digest detects accidental changes; it is not a signature. The implementation adds no table, migration, remote call, network scan, or GitHub write.

## Privacy and integrity controls

- Does **not** include raw HTML, unified diff, patched HTML, or owner-entered alt text, and does not publish an alt-text digest.
- Source/patch hashes that remain in the fixture manifest are unkeyed integrity identifiers, not a secrecy mechanism; production/general-data use remains disabled pending privacy review.
- Recomputes the stored source digest and rebuilds each proposal patch/patched source from the verified source, selector, and stored alt text before exporting; corrupted or missing proposal evidence fails closed.
- Uses an explicit tenant-scoped database transaction and compares the complete stored finding fingerprint set and metadata with a fresh local scan; missing, duplicate, or altered findings fail closed.
- Sends `Cache-Control: no-store` and an attachment filename; all underlying reads filter by tenant.
- Does not persist an export object or create a remote storage artifact.

## Explicit limits

This is a convenience evidence manifest, **not signed, immutable, timestamp-complete, or independently attested**. Current review storage lacks an event timestamp and general audit-event ID, so the export does not claim to be a complete audit log. Source revision binding remains false; scan mode is static local fixture HTML (not rendered browser/axe), coverage is one root fixture and one `image-alt` rule, and it does not establish WCAG conformance. Raw source/patch bytes are intentionally omitted, so a recipient cannot recreate the page or patch from the bundle alone. Production export remains disabled until privacy, retention, storage, and independent review controls are approved.

## Verification receipt

- Final full local Python suite: **385 passed, 9 skipped**. Eight skips are opt-in/disposable Chromium proofs; one is PostgreSQL unavailable. None is reported as a browser or PostgreSQL runtime pass.
- Focused export/permission tests are included in the full-suite receipt, including canonical digest, strict OpenAPI-compatible payload validation (UUIDs, integer bounds and timestamps), exact boolean/integer const typing, content omission, explicit tenant connection, complete finding-set enforcement, single-statement listing snapshot, repeatable-read export transaction, concurrent SQLite snapshot proof, tenant isolation, insufficient scope, tampered source/patch/alt text/finding metadata, scanner rejection, 422/HTTP exception problem media type, disabled-route media type, missing environment, null alt text, and float rejection.
- The disposable PostgreSQL runtime test now exercises both findings listing and evidence export under the adapter's repeatable-read transaction, but its execution is pending GitHub CI; it is not claimed as a local pass.
- `python scripts/verify_bootstrap.py`: **PASS**, 195 files scanned, no findings.
- `python scripts/verify_contracts.py`: **PASS**, 14 operations, no errors.
- `python scripts/validate_openapi_independent.py`: **PASS**.
- SDK generation + strict TypeScript check: **PASS**.
- `node --check apps/web/app.js` and browser-session tests: **PASS**, 3 tests.
- `git diff --check`: **PASS**.

PostgreSQL runtime, hosted services, and independent domain/privacy approval are separate evidence and are not inferred here. CI results for the exact PR commit will supersede this local receipt only for their explicitly tested scope.
