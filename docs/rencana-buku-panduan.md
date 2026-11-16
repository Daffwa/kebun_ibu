# Rencana buku panduan Kebun Ibu

Tanggal: 14 Nov 2026 · Status: **rencana**. Ditulis **setelah website 100% selesai**, supaya
tangkapan layar dan langkah-langkahnya tidak berubah lagi.

## Tujuan

Satu buku panduan dengan dua bagian:

| Bagian | Pembaca | Isi |
|---|---|---|
| A. Pembeli | kerabat yang membeli hasil kebun | cara melihat barang dan mengirim tawaran |
| B. Admin | Ibu dan Bapak (pengelola) | cara mengelola barang, tawaran, dan membaca halaman Pasar |

Bahasa Indonesia sehari-hari, tanpa istilah teknis. Setiap langkah disertai tangkapan layar HP,
karena pengguna membuka situs dari HP.

## Kerangka

### A. Pembeli

1. Membuka situs dan melihat daftar barang (`/`).
2. Halaman satu barang (`/l/[id]`): membaca harga, jumlah, dan mengirim tawaran.
3. Apa yang terjadi sesudah tawaran dikirim.

### B. Admin

1. Masuk (`/admin/login`).
2. Kotak masuk (`/admin`): tawaran yang masuk.
3. Barang (`/admin/listing`): membuat barang baru, mengubah, melihat tawaran per barang.
4. Riwayat (`/admin/riwayat`).
5. Pengaturan (`/admin/pengaturan`).
6. **Pasar (`/admin/pasar`)**: lihat bagian berikut.

Isi setiap langkah diperiksa ulang di website yang sudah selesai saat menulis, bukan dari
daftar ini.

## Bahan untuk bab Pasar (dari diskusi 14 Nov)

Penjelasan ini sudah dibahas dan dipahami; tinggal ditulis ulang dengan bahasa Ibuk.

**Filter.** Marketplace (Semua / Tokopedia / Blibli) dan rentang waktu (30 hari, 1 tahun,
5 tahun, Semua, Kustom). Tombol rentang terkunci (abu-abu) sampai datanya cukup, misalnya
"terbuka setelah 30 hari data (sekarang 8/30)".

**Grafik 1 (angka utama) dan grafik 2 (sebaran harga per kg).** Memakai **hari terakhir**
rentang yang dipilih, bukan seluruh rentang, supaya toko yang muncul setiap hari tidak terhitung
berkali-kali. Median = harga tengah; rata-rata terseret harga ekstrem; tertimbang terjual =
perkiraan harga yang benar-benar dibayar pembeli.

**Grafik 3 (harga produk yang sama).** Menjawab "apakah harga pasar benar-benar naik atau turun
dalam beberapa minggu/bulan?". Cara membuat garis biru:

1. Setiap produk dibandingkan dengan harganya sendiri pada pengamatan sebelumnya (paling lama
   30 hari). Produk baru atau yang hilang dilewati.
2. Setiap hari diambil **perubahan tengah** (median), misalnya ×1,00 atau ×1,10.
3. Perubahan harian dikalikan berantai mulai dari harga tengah hari pertama.
4. Garis digeser supaya titik terakhirnya sama dengan harga tengah hari terakhir.

Contoh untuk buku: hari 3, produk C hilang dan dua produk mahal baru muncul. Garis oranye
(harga tengah semua produk) melonjak dari Rp33.000 ke Rp46.500, padahal tidak ada penjual yang
menaikkan harga; garis biru tetap Rp33.000. Garis biru hanya bergerak kalau **lebih dari separuh**
produk yang sama berubah harga ke arah yang sama.

**Grafik 6 (lonjakan harga).** Menjawab "apakah ada yang tiba-tiba berubah minggu ini?".
Membandingkan hari ini dengan 7 hari sebelumnya: pasar dianggap melonjak kalau berubah ≥ 5%,
satu toko kalau ≥ 10%. Tidak menangkap kenaikan pelan (+21% dalam 2 bulan hanya tampak ±1,3% per
hari); itu tugas grafik 3.

## Yang harus diputuskan sebelum menulis

- [ ] Grafik 3: tetap tampil, disembunyikan sampai 30 hari data, atau dihapus.
- [ ] Grafik 1–2: tetap "hari terakhir" (dengan judul yang menyebutkannya), seluruh rentang,
      atau pilihan keduanya.
- [x] Harga Ibuk dihapus dari grafik 2 (14 Nov): pemilik bisa menjual lebih dari satu produk.
- [ ] Bentuk buku: halaman di website, PDF, atau keduanya.
- [ ] Siapa yang menulis bab Pasar dan siapa yang mengambil tangkapan layar.

## Syarat mulai

1. Semua halaman website selesai, termasuk polesan tampilan dari teman.
2. Keputusan di atas sudah diambil.
3. Data Pasar minimal 30 hari, supaya tangkapan layar grafik 3 dan 6 tidak kosong.
