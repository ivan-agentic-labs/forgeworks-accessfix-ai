# Panduan staging — accessfix-ai

URL: https://accessfix-ai-staging.up.railway.app/

## Akses

Login menggunakan akun Supabase Auth yang telah diverifikasi dan memiliki membership aktif serta grant produk dari administrator. Koneksi akun Supabase, Railway, atau GitHub ke ChatGPT tidak otomatis membuat akun pengguna aplikasi. Pada pemeriksaan 2026-10-09 UTC, akun calon pemilik belum terdaftar. Password tidak disimpan pada browser atau repository; sesi halaman menggunakan token dalam memori dan akan hilang saat halaman dimuat ulang.

## Alur

Masuk, isi origin HTTPS dan UUID repository, buat bukti, terbitkan berkas bukti pada URL yang ditampilkan, kemudian klik verifikasi. Pemindaian browser jarak jauh belum tersedia.

Berkas sumber dibatasi 1 MiB, kecuali APIShield 2 MiB. SHA-256 dan ukuran diperiksa sebelum commit. Unduhan hasil diverifikasi terhadap digest tersimpan. AccessFix tidak memakai penyimpanan artefak S3.

## Batas verifikasi

Deployment dan CI tidak membuktikan login pemilik atau seluruh alur bisnis melalui browser live. Browser lingkungan pemeriksaan memblokir domain staging Railway dengan `ERR_BLOCKED_BY_CLIENT`. Pengujian lokal dan CI memakai data sintetis, sedangkan probe Railway hanya membuktikan upload/read/delete objek probe terisolasi.

Staging ini belum dinyatakan siap produksi atau selesai untuk seluruh fungsi produk. Akun pemilik, pengujian live berautentikasi, GitHub App khusus APIShield, dan runner browser terisolasi AccessFix masih merupakan dependensi terbuka. AgentTest menerima hasil evaluasi eksplisit; eksekusi agen otomatis tetap nonaktif.
