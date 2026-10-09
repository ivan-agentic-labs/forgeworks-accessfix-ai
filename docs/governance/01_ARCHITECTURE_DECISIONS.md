# Architecture decision record — arah desain yang dipilih
Semua **SELECTED DESIGN** di bawah adalah rekomendasi arsitektur saat ini, bukan bukti kompatibilitas vendor/keamanan atau persetujuan owner. Seluruh pilihan vendor yang mengikat pembelian/domisili data tetap `OPEN`.

| ADR | Arah keputusan | Alasan, trade-off, kondisi perubahan | Status |
|---|---|---|---|
| ADR-01 | Modular monolith per produk + async worker, DB privat per produk | Meminimalkan overhead microservice untuk solo founder; pecah hanya jika kebutuhan scaling/boundary terbukti | SELECTED DESIGN |
| ADR-02 | Next.js same-origin BFF, FastAPI bearer behind BFF, OIDC eksternal | Browser tidak memegang refresh/API token; tambah lapisan BFF yang harus diuji CSRF/session | SELECTED DESIGN |
| ADR-03 | PostgreSQL, composite tenant foreign key, RLS sebagai defense-in-depth, bukan otorisasi tunggal | Keamanan tenant butuh app membership check + DB policy + dua role; tidak aman bila SQL injection bisa set tenant context | SELECTED DESIGN |
| ADR-04 | Transactional outbox + inbox dedupe + remote-effect ledger | At-least-once retry, bukan exactly-once; perlu reconciliation remote API | SELECTED DESIGN |
| ADR-05 | Private S3-compatible storage: quarantine → scan → ready → expired/deleted | Hindari direct public bucket dan raw unscanned execution, tambah biaya storage/scanning | SELECTED DESIGN |
| ADR-06 | AI planning/analysis hanya mengusulkan, deterministic policy mengotorisasi | Hindari agent membuat keputusan akhir untuk uang, PR merge, keamanan, compliance | SELECTED DESIGN |
| ADR-07 | Isolated ephemeral VM/microVM runner untuk untrusted input; fail closed sampai teruji | Container berbagi host tidak otomatis sandbox aman; vendor, egress firewall dan isolation review wajib | SELECTED DESIGN; VENDOR OPEN |
| ADR-08 | Kontrak OAS 3.1.2 baseline hingga ada validator/codegen interoperability proof | Pinning mengurangi drift; bukan klaim bahwa 3.2 tidak didukung | SELECTED DESIGN |
| ADR-09 | Append-only audit + data minimization + subject erasure/redaction policy | Invarians audit harus berdampingan dengan hak data, tidak boleh imutabilitas tanpa pengecualian hukum | SELECTED DESIGN; LEGAL OPEN |
| ADR-10 | Semua fitur tulis eksternal butuh human approval dan version-bound idempotency | Latensi approval tambahan; tidak auto-merge, auto-send, auto-transfer | SELECTED DESIGN |
| ADR-11 | Durable job state disimpan PostgreSQL; queue hanya mengantarkan pesan | Redis/broker boleh dipilih belakangan; source of truth tetap transaksi DB | SELECTED DESIGN; PROVIDER OPEN |
| ADR-12 | Baseline support tenant-level quota, rate limit, cost reservation, emergency kill switch | Menghindari runaway billing; threshold numerik ditentukan dari benchmark/budget | SELECTED DESIGN; LIMIT OPEN |

## Open decision records (harus ditandatangani, tidak dapat dijawab oleh dokumen saja)
| ID | Keputusan | Default sementara yang aman | Bukti yang dibutuhkan |
|---|---|---|---|
| OD-01 | Cloud & region data | Gunakan synthetic fixtures saja, jangan unggah customer data | Penawaran 2+ vendor, DPA, network/security matrix dan anggaran |
| OD-02 | IdP & session-revocation contract | BFF only; no custom password backend | OIDC test tenant, issuer/audience, JWKS, revocation latency |
| OD-03 | Sandbox vendor & isolation | Disable untrusted execution & web browsing | Isolation/egress/secret/metadata tests; third-party review |
| OD-04 | Licensing, privacy, DPA, retention | Private repo/internal project docs; no real PII | Founder/legal signoff & published policies |
| OD-05 | AI model & unit economics | Adapter, hard budget 0 real calls until funded | Quality eval dataset, terms, prices, measured cost and failover |
| OD-06 | Buyer/ICP pricing, acceptance | Hypothesis only; do not claim customers | Interviews, acceptance criteria and evidence |
| OD-07 | Accessibility manual review | No WCAG conformance claim | Expert adjudication on representative pages |
| OD-08 | Finance domain/accounting policy | Synthetic exact 1:1 same-currency only | Controller-reviewed reference datasets and conservation tests |
| OD-09 | Monitoring SLO, retention period, restore RPO/RTO | Planning thresholds, no SLA promise | Actual vendor capability, restore drills, cost approval |

**Human decision template:** `ID | selected option | comparison evidence | reviewer name/role | timestamp | artifact hash | scope | accepted risk | rollback trigger`. Kosong berarti `OPEN`, bukan `PASS`.
