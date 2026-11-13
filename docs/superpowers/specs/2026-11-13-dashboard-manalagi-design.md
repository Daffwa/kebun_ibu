# Dashboard harga Mangga Manalagi — desain

Tanggal: 13 Nov 2026 · Prototipe: `data-science/dashboard_contoh.ipynb` (matplotlib/seaborn)

## Tujuan

Pemilik website (Ibuk) melihat harga pasar Mangga Manalagi di Blibli dan Tokopedia, lalu
memutuskan apakah harga jualnya perlu diubah. Dashboard harus tetap benar **bertahun-tahun**
(target pengguna: satu dekade atau lebih), jadi aturan di bawah tidak boleh bergantung pada
jumlah hari data saat ini.

## Grafik

| # | Grafik | Jenis | Isi |
|---|---|---|---|
| 1 | Angka utama | potret | median, rata-rata, rata-rata tertimbang terjual (per kg) |
| 2 | Histogram harga per kg | potret | kelompok Rp5.000; garis median (putus-putus abu-abu) dan garis harga Ibuk (hitam), "X dari N produk lebih murah" |
| 3 | Tren harga produk yang sama | tren | harga per kg tanpa efek "produk yang muncul berganti" |
| 6 | Peringatan lonjakan harga | tren | lonjakan pasar (garis) + jumlah toko naik/turun (batang) + tabel toko yang melonjak |

**Tidak dipakai (dan alasannya):**

| Usulan | Keputusan | Alasan |
|---|---|---|
| Blibli vs Tokopedia | dibuang | sudah dicakup filter marketplace |
| Tren per wilayah | ditunda | data luar Jabodetabek terlalu sedikit (±1–4 produk/hari); pengguna memikirkannya nanti |
| Perbandingan varietas mangga | dibuang | pemilik tidak membutuhkannya |
| Jumlah buah terjual per hari/bulan | tidak bisa | tidak ada sumber: Tokopedia hanya label bertingkat ("30+", "1rb+"); Blibli punya total kumulatif pasti tetapi hanya ±4 penjualan Manalagi per minggu |

## Data

`v_produk` dengan filter: `jenis_buah = 'mangga'`, `nama ILIKE '%manalagi%'`, `opsi_default`,
`NOT olahan`, `harga_per_kg IS NOT NULL`, mulai tanggal pertama gudang yang lengkap
(Blibli 7 Nov, Tokopedia 8 Nov 2026; `MULAI_GUDANG` di `run.py`).

## Filter (satu baris, di atas semua grafik)

1. **Marketplace**: Semua / Tokopedia / Blibli. Berlaku untuk semua grafik.
2. **Rentang waktu**: 30 hari · 1 tahun · 5 tahun · Semua · Kustom (dari–sampai).

## Aturan grafik tren

Grafik tren = grafik dengan tanggal di sumbu x (grafik 3 dan 6).

### A. Kunci rentang

- `rentang_data = tanggal_terakhir − tanggal_pertama` untuk **marketplace yang dipilih**
  (Blibli dan Tokopedia bisa berbeda karena hari yang hilang berbeda).
- Preset (30 hari, 1 tahun, 5 tahun) **terkunci** kalau `rentang_data` lebih pendek dari preset.
  Tombol abu-abu + pesan, misalnya: "Terbuka setelah 30 hari data (sekarang 6/30)".
- Tahun dihitung dengan **kalender sebenarnya** (365/366 hari; `pd.DateOffset(years=n)`),
  bukan 360 hari. 5 × 360 hari berakhir ±25 hari lebih awal dari 5 tahun.
- **Semua** dan **Kustom** tidak pernah terkunci. Kustom hanya bisa memilih tanggal yang ada datanya.

### B. Kerapatan titik otomatis

| Panjang rentang | Satu titik = |
|---|---|
| ≤ 90 hari | 1 hari |
| ≤ 2 tahun | 1 minggu |
| > 2 tahun | 1 bulan |

Cara menggabungkan bergantung pada ukurannya:

| Ukuran | Digabung dengan |
|---|---|
| harga, rasio harga | **median** periode |
| jumlah toko yang melonjak | **jumlah** (bukan median) |
| hari lonjakan pasar | periode ditandai kalau **minimal satu hari** di dalamnya lonjakan |

### C. Hari yang hilang

- Hari tanpa data tetap kosong (garis putus), tidak diisi atau disambung.
- Di bawah grafik: cakupan, misalnya "30 hari, 27 berdata", supaya hari yang hilang tidak
  dikira penurunan harga.

### D. Hitung dulu, saring kemudian

Perhitungan yang butuh riwayat (jendela 7 hari lonjakan, indeks berantai) dihitung pada
**seluruh data**, baru kemudian disaring ke rentang yang dipilih. Kalau disaring dulu,
7 hari pertama setiap rentang selalu kosong.

## Aturan grafik potret (1 dan 2)

- Memakai **hari terakhir** rentang yang dipilih, bukan seluruh rentang. Alasan: dalam 30 hari
  satu toko yang muncul setiap hari akan terhitung 30 kali, toko lain sekali; satu hari = satu
  toko satu hitungan.
- Kalau hari itu tidak ada data untuk marketplace terpilih: pakai tanggal terakhir yang ada di
  dalam rentang, dan tampilkan tanggalnya.

## Rumus

### Grafik 3: harga produk yang sama

- **Prototipe sekarang**: `rasio = harga / median harga produk itu selama seluruh periode`;
  garis = median rasio per hari × median harga normal. Benar untuk rentang pendek.
- **Untuk bertahun-tahun (keputusan saya, belum dibahas)**: ganti dengan **indeks berantai**:
  `indeks(t) = indeks(t−1) × median( harga(t) / harga sebelumnya )` untuk produk yang punya
  dua pengamatan berturut-turut. "Normal" seluruh periode menjadi basi kalau periodenya 10 tahun.

### Grafik 6: lonjakan

| Parameter | Nilai awal | Arti |
|---|---|---|
| `JENDELA_HARI` | 7 | jendela pembanding, hari kalender, hari ini tidak ikut |
| `AMBANG_TOKO` | 10% | lonjakan satu produk |
| `AMBANG_PASAR` | 5% | lonjakan median semua produk |
| `MIN_DATA` | 3 | minimal hari berdata dalam jendela sebelum produk dinilai |

- `rasio = harga hari ini / median harga produk itu dalam jendela`.
- **Lonjakan toko**: `|rasio − 1| ≥ AMBANG_TOKO` **dan** harganya berbeda dari pengamatan
  sebelumnya (satu perubahan ditandai sekali, pada harinya).
- **Lonjakan pasar**: `|median rasio semua produk − 1| ≥ AMBANG_PASAR` (lebih dari separuh
  produk bergerak searah).
- Bukan aturan Hampel 3 × MAD: harga Manalagi jarang berubah, MAD sering 0, sehingga setiap
  perubahan kecil ikut ditandai.
- Nilai awal adalah tebakan; setel ulang setelah ±1 bulan data (perubahan harga mangga
  bukan nol: median 7,5%, 90% di bawah 28,3%, data 7–13 Nov).

## Jalur data (diputuskan 13 Nov)

**Laptop mendorong baris Mangga Manalagi ke Supabase** sebagai langkah ke-4 Task Scheduler
(sesudah `run.py`). Halaman `/admin/pasar` membaca tabel itu seperti tabel lain.

- Ukuran: ±27 baris/hari × ±400 byte (termasuk overhead Postgres) ≈ 11 KB/hari, ±4 MB/tahun,
  ±39 MB dalam 10 tahun = ±8% dari batas database paket gratis (500 MB; proyek menjadi
  read-only kalau terlewati).
- Hanya Manalagi. Semua buah (±7.150 baris/hari) akan memenuhi 500 MB dalam ±175 hari.
- **Kalau nanti semua buah perlu tampil**: simpan Parquet di Cloudflare R2 (gratis 10 GB, tanpa
  biaya unduh; semua buah ±91 MB/tahun) dan baca lewat S3 wrapper Supabase. Belum dicek apakah
  wrapper tersedia di paket gratis. Bonus: R2 sekaligus menjadi cadangan data di luar laptop.
- Pilihan lain yang dipertimbangkan: MotherDuck (10 GB gratis; klien DuckDB di Vercel belum
  diuji), BigQuery (sandbox menghapus tabel setelah 60 hari).

### Hitungan dalam SQL

Langkah 1 (`baris` dan `harian`) ditulis dalam **SQL DuckDB** (pengguna paling mudah membaca SQL)
dan membaca **langsung dari gudang**. Prototipe: `data-science/dashboard_contoh.ipynb`, sel
"Langkah 1a" dan "Langkah 1b". Skrip kirim ke Supabase memakai SQL yang sama.

- Hasilnya identik dengan versi pandas sebelumnya (data asli 7 hari dan data sintetis 3 tahun).
- Kecepatan, 950.862 baris (median 7 hari per produk + median harian): DuckDB langsung dari
  tabel 0,37 s, Polars 0,37 s, pandas 0,49 s; Polars SQL tidak bisa (median bergulir belum didukung).
  Data sebenarnya: semua buah ±214.000 baris/bulan, Manalagi ±810 baris/bulan.

### Tabel Supabase (disetujui 13 Nov)

Hanya kolom yang dibaca grafik dan filter. Dibaca hanya oleh admin (sesudah login), ditulis
hanya oleh laptop (kunci rahasia).

**`pasar_manalagi`**: satu baris per produk per hari. Kunci: (`tanggal`, `produk_key`).

| Kolom | Dipakai untuk |
|---|---|
| `tanggal`, `sumber`, `produk_key` | kunci, filter marketplace |
| `nama_toko`, `kota` | tabel lonjakan toko |
| `harga_per_kg` | grafik 1, histogram |
| `terjual_min` | rata-rata tertimbang terjual (grafik 1) |
| `median_jendela`, `rasio_jendela`, `lonjak_toko` | grafik 6 dan tabel lonjakan |

**`pasar_manalagi_harian`**: satu baris per tanggal per pasar (`semua`, `blibli`, `tokopedia`).
Kunci: (`tanggal`, `pasar`).

| Kolom | Dipakai untuk |
|---|---|
| `jumlah_produk` | cakupan ("N hari, M berdata") dan kunci rentang |
| `median`, `indeks_berantai` | grafik 3 (indeks digeser ke median hari terakhir saat digambar) |
| `median_rasio`, `lonjak_pasar`, `naik`, `turun` | grafik 6 |

Tetap di laptop (hanya langkah antara): `harga_sebelumnya`, `faktor`, `jumlah_jendela`,
`faktor_median`, `dinilai`, `rata_rata`, `tertimbang`.

## Belum diputuskan

1. **Harga Ibuk**: sekarang angka contoh `HARGA_IBUK = 30_000`. Perlu harga asli, dan untuk
   bertahun-tahun perlu **riwayat** harganya (mungkin sudah ada di database website).
2. **Cara mengirim ulang**: indeks berantai dan jendela 7 hari bergantung pada hari-hari
   sebelumnya, jadi tanggal yang dimuat terlambat (misalnya 11 Nov lewat cadangan VPS)
   mengubah baris sesudahnya. Pilihan untuk rencana: kirim ulang N hari terakhir setiap hari,
   atau kirim ulang semua (Manalagi kecil).
3. **Tren wilayah**: ditunda (lihat tabel "Tidak dipakai").
4. **Penjualan Blibli per minggu/bulan**: bisa dari selisih `blibli_produk.total_terjual`,
   layak dilihat lagi setelah ±3 bulan data.
