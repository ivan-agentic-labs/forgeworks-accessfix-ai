# ForgeWorks AI — G1 Design Consolidation Candidate
**Tanggal:** 9 Oktober 2026 · **Tahap:** perancangan, bukan implementasi · **Lima produk independen**.

## Apa yang diselesaikan paket ini
1. Menetapkan **urutan otoritas sumber** secara eksplisit agar file historis tidak mendikte implementasi.
2. Mengunci **keputusan arah desain** yang dapat dibuat sekarang tanpa membeli layanan atau mengklaim pengujian.
3. Membuat **kontrak non-fungsional, batas keamanan, dan paket review spesifik untuk kelima produk**.
4. Menyajikan **daftar keputusan yang membutuhkan signoff manusia** dan **bukti runtime yang belum tersedia**.
5. Memeriksa semua contoh artefak kanonis dalam lingkup checker offline yang disertakan.

## Aturan penggunaan
- Mulai baca `docs/governance/00_SOURCE_OF_TRUTH.md`, `docs/governance/01_ARCHITECTURE_DECISIONS.md`, `docs/governance/02_CONTRACT_RULES.md`, `docs/governance/03_DATA_SECURITY.md`, `docs/governance/04_OPERATIONS.md`, `docs/verification/EVIDENCE_INDEX.md`, lalu `docs/architecture/DESIGN_REVIEW.md`.
- `contracts/openapi.yaml` dan `events.schema.json` adalah **kontrak kandidat terkini**; `docs/verification/sql-candidates/10_schema_candidate.sql` adalah **SQL desain, bukan migrasi yang boleh dieksekusi sebagai production DDL**.
- `archive/v4_3_reference/` hanya sejarah yang dibekukan. `evidence/v4_5/` berisi log/scripts uji offline sebelumnya yang disalin apa adanya untuk provenance.
- Catatan di dalam arsip historis dapat tidak konsisten. Jika bertentangan, gunakan dokumen `canonical/` dan baca register konflik; **jangan mengira keputusan vendor, finance, legal, atau compliance sudah disetujui**.
- Ini bukan lima repository aplikasi. Belum ada deployment, data pelanggan, atau tes PostgreSQL live.

**Status akhir:** `DESIGN DOCUMENTATION CONSOLIDATED` (cakupan terbatas); **G1 SIGNOFF = BLOCKED**, karena bukti independen/runtime dan keputusan pemilik masih diperlukan. Tidak ada klaim 100% production-ready.
