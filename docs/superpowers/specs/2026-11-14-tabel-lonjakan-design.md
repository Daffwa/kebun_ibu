# Tabel lonjakan toko berdiri sendiri + grafik per bulan (desain singkat)

Tanggal: 14 Nov 2026. Halaman: `/admin/pasar`. Lanjutan dari `2026-11-14-admin-pasar-web-design.md`
dan `2026-11-14-filter-wilayah-design.md`.

## Maksud

1. **Tabel "Lonjakan toko"** sekarang menumpang di kartu grafik 3, ikut saringan halaman, dan hanya
   menampilkan 20 baris terbaru. Pemilik ingin tabel ini menjadi kartu sendiri dengan aturannya
   sendiri: saringan sendiri, urutan, jumlah baris per halaman, dan halaman (pagination).
   Data tabel **tidak bergantung** pada data grafik (keputusan pengguna).
2. **Grafik "Harga pasar vs 7 hari sebelumnya"** (dan grafik lain yang memakai `deret`): rentang
   1 tahun harus tampil per bulan (Jan, Feb, ...), bukan 52 titik per minggu.

## Tujuan

- Kartu baru di bawah grafik 3: judul "Lonjakan toko: N", baris saringan sendiri
  (pasar, waktu, wilayah), pilihan urutan, pilihan baris per halaman, tabel, navigasi halaman.
- Mengubah saringan grafik tidak mengubah tabel, dan sebaliknya.
- Muat ulang atau tautan yang dibagikan tetap menampilkan tabel yang sama.

## Bukan tujuan

- Tidak mengubah aturan lonjakan toko (tetap `lonjak_toko` dari laptop: ≥10% dari median 7 hari
  tokonya sendiri, harga berubah, minimal 3 hari data).
- Tidak menambah kolom tabel; kolom tetap Tanggal, Toko, Pasar, Kota, Sebelumnya, Sekarang, Perubahan.
- Tidak mengubah apa pun di Supabase atau laptop (data sudah cukup: `pasar_manalagi`).

## Pendekatan (dipilih: 1)

| | Cara | Untung / rugi |
|---|---|---|
| **1. Pengaturan di URL, dirender di server** ✅ | Parameter sendiri berawalan `t_`; komponen saringan yang ada dipakai ulang. | Sama dengan cara halaman sekarang; refresh/tautan menyimpan keadaan. Rugi: setiap klik tabel memuat ulang seluruh halaman (±0,5–1 dtk). |
| 2. Tabel memuat datanya sendiri di browser | Klien Supabase dari browser. | Klik lebih cepat; refresh mengulang tabel; cara kedua mengambil data. |
| 3. Halaman terpisah `/admin/pasar/lonjakan` | Kartu berisi 5 terbaru + "Lihat semua". | Grafik tidak pernah dimuat ulang; satu halaman dan satu klik lagi. |

Dipilih pengguna: **1**. Kalau muat ulang terasa mengganggu, pindah ke 3 mudah.

## Keputusan

**Parameter URL tabel** (semua opsional; nilai asing jatuh ke bawaan, seperti `bacaFilter`):

| Parameter | Nilai | Bawaan |
|---|---|---|
| `t_pasar` | semua, blibli, tokopedia | semua |
| `t_rentang` (+ `t_dari`, `t_sampai` untuk kustom) | sama dengan `rentang` | semua |
| `t_wilayah` | kode dari `pasar_wilayah` untuk `t_pasar` | semua wilayah |
| `t_urut` | `baru` (tanggal terbaru dulu), `turun` (perubahan terendah dulu), `naik` (perubahan tertinggi dulu) | baru |
| `t_baris` | 10, 25, 50, 100 | 10 |
| `t_hal` | bilangan bulat ≥ 1 | 1 |

- **Bawaan tabel tidak menyalin saringan grafik** (data tabel berdiri sendiri). *Panggilan saya.*
- Batas preset (30 hari/1 tahun terkunci) dihitung dari data `t_pasar` + `t_wilayah` sendiri
  (`ambilBatas`), sama seperti saringan grafik.
- Mengganti saringan, urutan, atau jumlah baris mengembalikan `t_hal` ke 1.
- `t_hal` melebihi halaman terakhir → dijepit ke halaman terakhir (bukan tabel kosong).
- **Kedua saringan saling menjaga URL:** saringan grafik mempertahankan semua parameter `t_*`,
  saringan tabel mempertahankan parameter grafik. (`alamat()` di `Saringan.tsx` sekarang membuat
  URL dari nol, jadi ini perlu diubah.)
- Urutan stabil untuk halaman: urutan pilihan, lalu `tanggal` turun, lalu `produk_key`
  (kunci utama `pasar_manalagi` = `tanggal, produk_key`, jadi unik). `rasio_jendela` kosong ditaruh
  terakhir.
- Pengambilan per halaman di Supabase: `.range((hal-1)*baris, hal*baris-1)` + `count: "exact"`.
  Maksimal 100 baris per permintaan, jauh di bawah batas 1000.
- Kartu grafik 3 tidak lagi berisi tabel; grafik batang naik/turun di grafik 3 tetap.

**Grafik per bulan** (*panggilan saya, belum dikonfirmasi angka 90-nya*):

- `kerapatan`: rentang ≤ 90 hari → per hari; lebih dari itu → per bulan. Per minggu dihapus.
  1 tahun = 12 titik.
- Satu titik bulan tetap "vs 7 hari sebelumnya": median rasio harian bulan itu; batang toko = jumlah
  toko berubah dalam bulan itu (sudah begitu di `gabung`).
- Aturan ini ada dua salinan yang diuji silang: notebook `dashboard_contoh.ipynb` (sel `kerapatan`)
  dan `src/lib/pasar.ts`. Ubah keduanya, lalu jalankan ulang `ekspor_uji_web.py` untuk
  `pasar.fixture.json`.

## Diserahkan ke pembangun

- Bentuk navigasi halaman (mis. `‹ 1 2 3 … 9 ›`), asal muat di HP (lebar 360 px) tanpa geser halaman.
- Teks label pilihan urutan dan baris.
- Apakah tipe `Satuan` tetap memuat `"minggu"` atau dibuang.
- Kartu kosong: "Tidak ada toko yang melonjak untuk saringan ini."
