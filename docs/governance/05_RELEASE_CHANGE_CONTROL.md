# Gate policy, handoff, change management

## G0–G6
- **G0 Problem/Product:** ICP, proses bisnis yang terukur, data classification, buyer use case, non-goals, privacy feasibility; review owner.
- **G1 Design:** setiap requirement P0 → model domain/API/architecture/security/invariant/test mapping, keputusan vendor/legal yang relevan, formal contract validation, database/auth/sandbox proof **yang memang dijadikan prasyarat G1 saat ini**. Bila bukti ini belum ada, gate blocked.
- **G2 Foundation:** repository bootstrap, pinned dependencies, IaC staging, CI, actual DB migrations, baseline auth/observability. No public launch.
- **G3 Functional:** P0 user journeys, human approvals, deterministic rules, negative tests and agent eval pass.
- **G4 Resilience/Security:** load, red team, crash recovery, backup/restore, tenant isolation, incident response.
- **G5 Controlled pilot:** opted-in users, no unsupported claims, consent/DPA where needed, measured reliability/usefulness.
- **G6 GA:** support model, verified operational SLO, incident ownership, legal/contract signoff, rollback and billing readiness.

**Catatan dependency:** jika G1 mewajibkan pengujian live PG/OIDC, maka pengujian terbatas dalam lingkungan verifikasi adalah *test harness*, bukan implementasi fitur produk; pemilik boleh menyetujui pemindahan item tersebut ke G2 melalui ADR terdokumentasi, tetapi status G1 versi saat ini tidak boleh diam-diam diubah.

## Handoff definition
Developer harus bisa menjawab untuk setiap P0: siapa user dan izin, input contract, typed validation, state transition, DB constraints, job idempotency, tool boundary, artifact retention, error taxonomy, positive and negative tests, operational metrics, rollback, exact success evidence.

## Change classification
- Security boundary/tenant model/financial rule = high risk: change advisory, threats, dual review, compatibility, rollback.
- Additive fields or observability = medium: update schema tests and consumers.
- Docs typo only = low: lint + review.

## Release evidence
Tidak boleh menggunakan screenshot manual atau klaim AI sebagai pengganti log pengujian, SQL trace, signed migration report, customer consent, ataupun security review. Human acceptance diperlukan ketika dampaknya finansial, kepatuhan, atau data milik pengguna lain.
