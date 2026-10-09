# Cross-product contracts dan API conventions

## HTTP/API
- OpenAPI 3.1.2 sebagai **candidate contract**, operasi dengan `operationId` unik per produk, security declarations, `x-required-scope`, dan `Idempotency-Key` untuk mutasi yang ditandai idempotent.
- Success: `201` untuk resource tercipta, `202` untuk job durable accepted, `200` untuk read, `204` untuk no-body mutations; `Location`/`Retry-After` dapat ditambahkan setelah response compatibility review.
- Error: `application/problem+json` sesuai RFC 9457. `type`, `title`, `status`, `detail` + machine-readable `code`, `trace_id` bila disetujui; `detail` tidak boleh bocorkan credential atau tenant existence.
- `401` unauthenticated, `403` unauthorized, `404` resource tidak ada/tidak terlihat untuk cegah enumeration, `409` stale `expected_version`/idempotency conflict, `413` oversize, `422` semantic invalid, `429` quota, `503` outage.
- Tujuh endpoint list P0 yang teridentifikasi SUDAH memiliki `cursor`, `limit`, dan respons `items`/`next_cursor`/`has_more`. Yang belum terbukti adalah sorting stabil, cursor bertanda tangan/tenant-filter-bound, tamper rejection, dan load test. Jangan membuka gap pagination palsu; tutup semantic-test gap saat pengujian.
- Jangan menggunakan `GET` untuk mutation atau signed export yang membuat state tak terkontrol. DataReconcile legacy `GET /v1/reports/{id}/download` bertanda `deprecated`; rute pengganti adalah download-intent artefak. Kebijakan sunset, client migration dan compatibility test tetap butuh approval.

## Idempotency dan concurrency
- Key scoped oleh `{tenant, principal, operation, key}` dan body canonical hash, dengan TTL yang ditentukan per operasi. Repeated key + hash sama mengembalikan outcome semula; hash berbeda → 409.
- Resource review/approval wajib membawa `expected_version`, resource snapshot ID, dan current actor; verify version di transaksi atomik. Missing/stale → 409, tidak menulis remote side effect.
- Outbox write dan domain mutation dalam **satu transaksi**. External call timeout tidak boleh blind retry; lookup outcome dengan idempotency correlation ID atau reconcile queue.
- Job state terminal tidak boleh dipulihkan menjadi running kecuali di bawah explicit retry state machine yang terdokumentasi.

## Artefak
`create upload intent → client uploads to private quarantine → commit metadata/checksum → async scan/content validation → READY → short-lived tenant-scoped download intent → expiry/deletion`. MIME sniff + size + format whitelist; no public URL; signed URL TTL pendek; audit akses; delete/tombstone dengan backup expiry. Tidak boleh menganggap `upload commit` berarti file bersih.

## Domain events
Envelope minimal: `event_id`, `event_type`, `event_version`, `tenant_id`, `aggregate_id`, `aggregate_version`, `occurred_at`, `correlation_id`, `payload` (opsional `causation_id`). Payload diverifikasi menggunakan `events.schema.json` **per produk**, tidak menyalin payload bisnis antarproduk. Evolusi event: tambah field optional nonbreaking; breaking schema memerlukan new version + consumer rollout + dead-letter inspection.

## BFF dan service API
Browser hanya berbicara dengan same-origin BFF memakai secure HttpOnly cookie, Origin checks dan CSRF defense; BFF menukar/menyimpan token di sisi server. Service API memakai audience-bound bearer dari BFF atau machine client, validasi `iss`, `aud`, `exp`, signature, scope dan server-derived tenant membership. Tidak mempercayai `X-Tenant-ID` atau tenant_id dari body sebagai otorisasi.

## Contract-check gate sebelum frozen
1. Independent official/schema-aware OpenAPI validator berhasil untuk lima dokumen.
2. Generated standard SDK (bukan type-only generator) berhasil dikompilasi serta cocok dengan mock/spec.
3. Respons/error/collection pagination/enum/version semantics diuji contoh positif dan negatif.
4. Security scopes, CSRF/BFF contract, event consumers, backward compatibility, rate-limit dan idempotency diuji.
Saat ini poin 1–4 **BELUM dinyatakan PASS**.
