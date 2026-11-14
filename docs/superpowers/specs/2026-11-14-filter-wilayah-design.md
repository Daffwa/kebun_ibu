# Filter wilayah di `/admin/pasar` — desain

Tanggal: 14 Nov 2026 · Melengkapi `2026-11-13-dashboard-manalagi-design.md` dan
`2026-11-14-admin-pasar-web-design.md`.

## Tujuan

Ibuk bisa melihat harga Mangga Manalagi untuk satu wilayah saja (misalnya Jawa Timur, Bali, atau
Kota Surabaya), dengan semua grafik dan tabel ikut wilayah itu.

## Keputusan pengguna (14 Nov)

1. Filter wilayah = **kotak cari**, sejajar dengan "Semua pasar" dan "Semua waktu".
2. Diklik tanpa mengetik: tampil **5 provinsi** dengan **toko terbanyak**. Rentang waktu tidak
   memengaruhi daftar ini.
3. Mengetik: mencari di **semua tingkat** (kelompok seperti Jabodetabek, provinsi, kota/kabupaten)
   sesuai kata kunci.
4. Rancang seolah datanya **sudah cukup** untuk setiap wilayah.

**Bukan tujuan:** peta, grafik yang membandingkan beberapa wilayah sekaligus, peringatan "data
tipis" (keputusan 4), mengganti kolom `region` lama di gudang (tetap dipakai analisis lain).

## Sumber daftar wilayah

- `cahyadsn/wilayah`, berkas `db/wilayah.sql`, sesuai **Kepmendagri No 300.2.2-2138 Tahun 2025**,
  lisensi MIT. Kode 2 digit = provinsi (38), kode `NN.NN` = kabupaten/kota (514).
- Disalin sekali ke repo sebagai `data-science/referensi/wilayah_kabkota.csv`
  (`kode, nama, jenis, provinsi_kode, provinsi`), dibuat oleh skrip kecil dari `wilayah.sql`, dengan
  atribusi di kepala berkas. Tidak diunduh saat pipeline berjalan.

## Mencocokkan `kota` ke wilayah resmi

Normalisasi kedua sisi: huruf kecil, buang isi kurung, buang awalan `Kota`, `Kab.`, `Kabupaten`,
`Administrasi`, lalu **buang semua spasi**. Awalan (kota/kabupaten), kalau ada, dipakai untuk
memilih di antara dua nama yang sama.

Hasil uji 14 Nov pada gudang: **147 dari 147** nama kota cocok ke tepat satu provinsi, termasuk
`Kab.Ciamis` (tanpa spasi), `Kota Palangka Raya` (resmi: Palangkaraya), dan `Kota Pematang Siantar`.

- Satu-satunya nama yang sama di dua provinsi se-Indonesia: **Banjar** (Kabupaten Banjar, Kalimantan
  Selatan; Kota Banjar, Jawa Barat). Dengan awalan: tepat. Tanpa awalan (gaya Tokopedia):
  `kabkota_kode` dan `provinsi_kode` kosong (keputusan saya: lebih baik kosong daripada salah).
- **Cek I: kota tidak dikenal** (keputusan pengguna 14 Nov: pola cek H). Kalau `kota` terisi tetapi
  tidak cocok, atau cocok ke lebih dari satu provinsi, baris itu **disalin** ke `produk_karantina`
  dengan `alasan = "cek_I_kota_tidak_dikenal"` dan **tetap dimuat** dengan kode kosong. Harganya
  tetap terhitung di "Semua wilayah"; hanya tidak muncul di filter wilayah.
- `kota` kosong bukan galat (±23 baris Tokopedia per hari, toko tidak mengisi kota): kode kosong,
  tidak disalin ke karantina.
- Memperbaiki nama yang tertahan: tambahkan ke daftar alias (`ALIAS_KOTA` di
  `transform/wilayah.py`), lalu muat ulang tanggal itu.

## Tingkat wilayah dan kuncinya

| Tingkat | Kunci (di URL dan tabel) | Contoh nama tampil |
|---|---|---|
| semua | `semua` | Semua wilayah |
| kelompok | `jabodetabek` | Jabodetabek |
| provinsi | kode 2 digit, `35` | Jawa Timur |
| kabupaten/kota | kode `NN.NN`, `35.78` | Kota Surabaya |

- Nama tampil = nama resmi, tanpa kata "Administrasi" dan tanpa spasi di ujung (data sumber punya
  `'Kota Administrasi Jakarta Utara '`).
- Kelompok saat ini hanya **Jabodetabek** = semua kab/kota DKI Jakarta + Kota/Kab. Bogor, Kota Depok,
  Kota/Kab. Bekasi, Kota/Kab. Tangerang, Kota Tangerang Selatan (keputusan saya; kelompok lain cukup
  ditambah di satu kamus).
- Kata kunci tambahan untuk pencarian provinsi (keputusan saya): Jatim, Jateng, Jabar, DIY/Jogja,
  DKI/Jakarta, Kalsel, Sulsel, Sumut, dll.

## Perubahan data (laptop)

1. Modul baru `transform/wilayah.py`: muat CSV, `cocokkan(kota) -> (kabkota_kode, provinsi_kode)`,
   anggota kelompok, `ALIAS_KOTA`.
2. **Pencocokan di tahap transform**, jadi semua analisis memakainya, bukan hanya dashboard:
   - `fakta_harga` mendapat `kabkota_kode` dan `provinsi_kode` (`transform/model.py`). Gudang lama
     mendapat kolomnya lewat `_tambah_kolom_baru`; semua tanggal dimuat ulang sekali.
   - Cek I di `transform/skema.pisahkan`, di samping cek H.
   - `v_produk` ikut membawa kedua kode.
3. `dashboard_manalagi.hitung()`:
   - `baris` mendapat `kabkota_kode` dan `provinsi_kode` dari `v_produk`.
   - `harian` dihitung **per (wilayah, pasar)**: `semua`, setiap kelompok, setiap provinsi, dan
     setiap kab/kota yang punya data. Indeks berantai, jendela 7 hari, dan lonjakan pasar dihitung
     terpisah untuk setiap deret, pada seluruh riwayat (aturan D tetap berlaku).
   - **Baris `wilayah = 'semua'` harus sama persis dengan `harian` sekarang** (uji regresi).
   - Semua pemakai `harian` yang belum mengenal wilayah menyaring `wilayah == 'semua'` di perubahan
     yang sama: `dashboard_contoh.ipynb` dan `ekspor_uji_web.py` (fixture uji web). Tanpa ini,
     keduanya diam-diam mencampur semua wilayah.
4. Daftar wilayah untuk kotak cari, `wilayah`: satu baris per (wilayah, pasar) yang punya data, dengan
   `nama`, `tingkat`, `provinsi_kode` (untuk kab/kota), `jumlah_toko` = toko berbeda **sepanjang
   seluruh data** (tidak ikut rentang). `pasar` ikut dihitung (keputusan saya): di "Blibli", 5
   teratas hanya menghitung toko Blibli.

## Supabase

Satu migrasi baru (dijalankan di dashboard supabase.com, bukan Studio lokal):

| Tabel | Perubahan |
|---|---|
| `pasar_manalagi` | `+ kabkota_kode text`, `+ provinsi_kode text` (boleh kosong) |
| `pasar_manalagi_harian` | `+ wilayah text not null default 'semua'`; primary key jadi `(tanggal, pasar, wilayah)` |
| `pasar_wilayah` (baru) | `wilayah, pasar, nama, tingkat, provinsi_kode, kata_kunci, jumlah_toko`; PK `(wilayah, pasar)`; RLS sama: baca pengelola, tulis service_role |

- `kata_kunci` (mis. "jatim jawa timur") disimpan di tabel supaya web tidak menulis daftar singkatan
  sendiri (ditambahkan saat menyusun rencana).
- `ganti_pasar_manalagi` dibuat ulang: `jsonb_populate_recordset` mengisi kunci yang tidak ada dengan
  NULL, bukan nilai bawaan kolom, jadi baris harian tanpa `wilayah` harus diisi `'semua'` di fungsi.
  Hapus per tanggal tetap mencakup semua wilayah.
- Fungsi baru `ganti_pasar_wilayah(p_baris jsonb)`: hapus semua lalu isi ulang `pasar_wilayah` dalam
  satu transaksi (±200 baris).
- `kirim_supabase.py`: kolom baru di `KOLOM_BARIS`/`KOLOM_HARIAN`, kunci `harian` menjadi
  `tanggal, pasar, wilayah`, panggil `ganti_pasar_wilayah` sesudah tanggal-tanggal terkirim.
  Kolom berubah: hapus `warehouse/terkirim/` lalu kirim `--semua` sekali.
- pgTAP: tabel baru, PK baru, anon/non-pengelola ditolak, `ganti_pasar_wilayah` hanya service_role.

## Web (sesi `/admin/pasar`, sesudah halamannya selesai)

- Kotak cari (`"use client"`) di baris filter, isi dari `pasar_wilayah` untuk pasar terpilih.
  - Fokus tanpa teks: 5 provinsi dengan `jumlah_toko` terbesar.
  - Mengetik: cocok sebagian, tanpa beda huruf besar/kecil, di semua tingkat dan kata kunci
    tambahan; maksimal 10 hasil; label "Jawa Timur · provinsi · 7 toko".
  - Keyboard (panah, Enter, Esc) dan sentuh di HP; tombol hapus pilihan kembali ke Semua wilayah.
- Pilihan masuk URL: `?wilayah=35`, seperti filter lain; nilai asing jatuh ke `semua`.
- Semua bacaan ikut wilayah:
  - `pasar_manalagi_harian`: `.eq("wilayah", w)`.
  - `pasar_manalagi`: provinsi → `provinsi_kode = w`; kab/kota → `kabkota_kode = w`; kelompok →
    `kabkota_kode in (anggota)`.
- Kunci rentang dan baris cakupan dihitung dari deret wilayah terpilih.

## Urutan supaya tidak ada yang rusak

1. **Migrasi** di produksi. Baris harian yang sudah ada otomatis `wilayah = 'semua'`, jadi web yang
   lama tetap benar.
2. **Web** membaca `.eq("wilayah", "semua")` secara bawaan, lalu di-deploy.
3. **Data**: laptop mulai mengirim baris per wilayah (`--semua` sekali).

Kalau langkah 3 mendahului 2, grafik web mencampur semua wilayah. Karena itu `kirim_supabase.py`
mendapat saklar `KIRIM_PER_WILAYAH = False` yang baru dinyalakan sesudah langkah 2.

## Perkiraan waktu

Data + Supabase ±3,5 jam (sesi ini, termasuk cek I dan muat ulang gudang). Web ±1 jam
(sesi `/admin/pasar`).

## Diserahkan ke pembuat

Tampilan kotak cari dan daftar hasil (teman memoles), urutan hasil pencarian yang sama skornya.
