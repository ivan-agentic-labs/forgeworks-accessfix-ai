# Owner Decision Register — 9 keputusan tanpa signoff

| ID | Keputusan | Default rancangan sampai diputuskan | Evidence wajib | Fail-closed action | Status |
|---|---|---|---|---|---|
| OD-01 | Cloud/region | Satu region dan database privat per produk; isolasi akun dev/staging/prod | DPA + data residency map + dua penawaran vendor + perkiraan biaya | NO CUSTOMER DATA | OPEN |
| OD-02 | OIDC/IdP | Managed OIDC + same-origin BFF; sesi server-side; no custom password | Issuer/audience/JWKS, revocation, CSRF tests pada test tenant | NO PUBLIC LOGIN | OPEN |
| OD-03 | Sandbox | Ephemeral hardened VM/microVM; egress allowlist; short-lived identity | Provider evidence + breakout/metadata/secret/SSRF tests | UNTRUSTED EXECUTION DISABLED | OPEN |
| OD-04 | Lisensi dan privasi | Private repos sampai strategi lisensi, IP, DPA dan retensi ditetapkan | Owner/legal signoff; data class table + deletion/backup matrix | PRIVATE + SYNTHETIC ONLY | OPEN |
| OD-05 | LLM dan unit economics | Provider adapter, no hard-coded model; prompt-data-minimization | Benchmark kualitas + token/cost quote + TOS/data-use review | REAL AI CALLS DISABLED | OPEN |
| OD-06 | Target buyer / P0 | ICP hipotesis per produk; satu workflow inti diprioritaskan | Catatan wawancara dan acceptance criteria pengguna nyata | NO CUSTOMER CLAIM | OPEN |
| OD-07 | Reviewer aksesibilitas | Manual WCAG test untuk sampel representatif | Qualified reviewer report + issues not covered by axe | NO WCAG CONFORMANCE CLAIM | OPEN |
| OD-08 | Aturan finansial | Exact 1:1 same currency, integer minor units, synthetic fixtures | Finance controller review + reversal and reconciliation golden cases | NO REAL FINANCIAL DATA | OPEN |
| OD-09 | Operasional/SLO | SLO/RTO/RPO proposed only; emergency stop; safe rollback | Costed runbooks + restore drills + SLO benchmark | NO SLA PROMISE | OPEN |

## Format tanda tangan per keputusan
`Decision ID | option selected | alternatives and trade-offs | accountable owner | independent reviewer if needed | decision UTC | artifact hash | residual risk | limits | review/expiry date`

Belum ada pilihan cloud/vendor, harga, wilayah data, atau pemberian lisensi yang diwakilkan sebagai persetujuan. Rekomendasi teknis di atas hanya default untuk menjaga keamanan fase perancangan.
