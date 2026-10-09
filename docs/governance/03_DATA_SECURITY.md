# Data architecture, isolation, threat boundaries

## Database role model yang akan diverifikasi
- `schema_owner`: role migrasi terpisah yang memiliki DDL, hanya tersedia untuk CI migration authorized.
- `app_rw`: role grup `NOLOGIN NOBYPASSRLS`, tidak memiliki DDL/ownership. Login role layanan berbeda, hanya mendapat GRANT eksplisit ke operasi/tabel yang perlu.
- `app_login`: `LOGIN NOSUPERUSER NOBYPASSRLS`, tidak menjadi table owner, kredensial rotation dan scoped permission. Periksa role inheritance dan effective grants, bukan label role saja.
- `support_ro`: akses terbatas, time-bound, audited, tidak boleh menjadikan `BYPASSRLS` bypass.
- Global `tenants`, `users` tidak memakai generik tenant RLS secara buta; aksesnya ditentukan layanan identity + ACL/permissions spesifik. `memberships` tenant-scoped dan lookup harus tervalidasi.

## RLS / transaksi
- Semua write/read tenant-scoped harus menjalankan auth membership di API serta `SET LOCAL app.tenant_id` **di dalam transaksi**; reset dilakukan otomatis ketika transaksi selesai, diuji dengan connection pooling dan concurrent requests.
- Default deny jika tenant context hilang; periksa salah format, tenant asing, lateral relation, `INSERT/UPDATE` via `WITH CHECK`, `SELECT`, `DELETE`, `COPY` paths, index/unique error side channels, privileged SQL.
- Composite FK `(tenant_id, entity_id)` untuk semua relasi tenant-domain agar referensi silang organisasi ditolak oleh database. `ON DELETE` dipilih sesuai invariant/retention, bukan cascade sembarangan.
- Keamanan tidak bisa bergantung pada custom GUC saja. SQL injection dapat mengubah sesi/tenant context bila penyerang mengeksekusi perintah SQL. Parameterization, least-privilege, policy separation, defense in depth, dan negative tests wajib.
- Contoh SQL di `docs/verification/sql-candidates/10_schema_candidate.sql` **tidak untuk langsung dijalankan**. Masih butuh serial migration, extension/role provisioning, GRANT audit, down/forward-only policy, lock timeout, trusted seed, backup dan rollback plan.

## Baseline threat model
| Attack | Batas yang harus bertahan | Negative proof |
|---|---|---|
| Tenant IDOR / privilege escalation | BFF → API authorization → scoped repo → RLS | unauthorized read/write/download, enumerate hidden ID, changed tenant context |
| Prompt injection / exfiltration | LLM tool policy and output validation | malicious repo/doc instructions cannot trigger privilege change/network/secret access |
| SSRF/metadata | URL/domain proof + egress network deny | redirect chain, DNS rebinding, private/loopback/link-local/metadata IPv4 & IPv6 blocked |
| Remote code/browser escape | ephemeral VM/microVM isolation | no host mounts, no service credentials, quotas, blocked outbound, escape probes |
| Replay/webhook forgery | signed raw-body webhook + nonce/timestamp + receipt | old/replayed/wrong installation rejected |
| Financial or CI state corruption | deterministic invariants & versioned approval | concurrent reconcile/PR attempts do not double-apply |
| Data leak logs/trace | redaction+data-class retention | secret and PII never written to default telemetry |
| Backup/account delete mismatch | backup expiry legal hold + delete audit | recovery does not silently resurrect deleted customer data |

## APIShield / AccessFix runner boundary
A trusted control plane creates one-use scoped job; runner fetches read-only artefact via short-lived token, starts without product DB/IdP/production credentials, network deny by default, CPU/memory/wall clock cap, file size cap and destroy-on-completion. Egress exceptions must be reviewed and logged. No user shell as superuser. Failure to provide isolation means execution path disabled (`FAIL CLOSED`).

## Audit events & evidentiary quality
Audit records should include tenant/actor/action/resource/trace_id/time, policy decision/version and outcome; log fail-open policy forbidden for critical approvals. But audit logs containing PII need retention, encryption, access controls, and erasure/legal-hold policy reviewed by counsel. Do not claim immutable logs solve deletion compliance.
