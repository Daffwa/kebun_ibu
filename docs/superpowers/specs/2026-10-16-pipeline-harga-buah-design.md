# Desain: Pipeline ETL Harga Buah Marketplace

Tanggal: 16 Oktober 2026 · **Diperbarui: 7 November 2026**
Status: menunggu tinjauan pembaruan 7 November
Latar belakang: [`rencana-data-science.md`](../../rencana-data-science.md),
[`keputusan-data-science-2026-10-13.md`](../../keputusan-data-science-2026-10-13.md),
[`catatan-scraping-vps-2026-11-07.md`](../../catatan-scraping-vps-2026-11-07.md)

## 0. Yang berubah pada 7 November 2026

Hasil eksplorasi data mentah 26 Oktober – 7 November (notebook
`data-science/eksplor.ipynb`):

1. **Penarikan harian otomatis sudah jalan** (laptop + VPS). Tidak lagi di
   luar lingkup (bagian 1, 4.4).
2. **Blibli: harga semua opsi varian ikut ditarik** sejak 8 November
   (bagian 4.1). Lapisan 1 Blibli jadi **satu baris per opsi**
   (`item_sku`), bukan per produk (bagian 5.1).
3. **Kolom Blibli: 29 kolom sumber** + 3 kolom turunan (bagian 5.1).
4. **Aturan berat diperbarui** dari profil ±9.400 nama asli: pecahan
   "1/2 kg" sekarang **dibaca** (menggantikan aturan lama "dilewati"),
   ditambah berat cadangan dari `variant` Blibli dan URL Tokopedia
   (bagian 5.2).
5. **Lima cek perbandingan kolom Blibli** yang gagal masuk karantina
   (bagian 6).
6. **Target utama analisis: harga Mangga Manalagi.** Penarikan tetap
   per kategori buah (konteks pasar).
7. **(8 Nov) Tinjauan lewat `transform.ipynb`:** logika tetap di `.py`
   (supaya bisa dites pytest dan dijalankan terjadwal), tetapi setiap
   langkah transform punya bagian di notebook yang menampilkan **kode
   fungsinya dan hasilnya**. Pengguna meninjau kode + hasil di sana
   (bagian 2, 11).
8. **(8 Nov) `sku` Blibli disimpan** dan dibandingkan dengan `id` (cek G).

Tanda **[usulan Claude]** = keputusan kecil oleh Claude, bukan pengguna.
Periksa saat membaca.

## 1. Tujuan dan lingkup

Membangun pipeline **ETL** yang mengambil produk buah dari **Blibli** dan
**Tokopedia**, membersihkan dan menyeragamkannya di Python, lalu memuatnya
ke **DuckDB** sebagai **star schema**. Hasilnya menjadi dasar analisis dan
model di tahap berikutnya. **Target utama: harga Mangga Manalagi**
(diputuskan 4 November).

Diperlakukan sebagai proyek data engineering yang serius:
- pemuatan yang aman diulang;
- data mentah tidak pernah diubah atau dihapus;
- validasi data berupa kode;
- baris yang gagal dikarantina, tidak dibuang;
- setiap run tercatat;
- ada tes dan CI.

**Di luar lingkup:**
- model harga per kg (didesain setelah pipeline ini jadi);
- dashboard (usulan dashboard `/admin/pasar` 26 Oktober belum diputuskan,
  bagian 13);
- halaman produk Tokopedia (hanya di notebook, bagian 4.2);
- Shopee.

## 2. Keputusan yang dikunci

| Hal | Keputusan |
|---|---|
| Pola | ETL: transformasi di Python **sebelum** dimuat |
| Ambil data | `urllib` (Blibli), `curl_cffi` `impersonate="chrome"` (Tokopedia), dua-duanya API JSON tersembunyi |
| Transformasi | **Polars** |
| Validasi | **Pandera** (backend Polars) |
| Gudang data | **DuckDB**, satu berkas |
| Bentuk tabel akhir | **Star schema** + view datar `v_produk` |
| Penarikan | **Harian otomatis**: `tarik_harian.py` (bagian 4.4) |
| Transform + load | `run.py`, dijalankan manual dari laptop |
| Tempat meninjau | **`transform.ipynb`**: satu bagian per langkah. Sel 1 menampilkan kode fungsi (`IPython.display.Code(inspect.getsource(fungsi))`), sel 2 menjalankannya pada data asli dan menampilkan tabel hasil. Logika tidak ditulis ulang di notebook (8 Nov) |
| Tes | pytest + GitHub Actions |
| Tidak dipakai | Airflow, Kafka, dbt, Selenium. Selenium **diuji 7 Nov dan gagal** di VPS (catatan scraping) |

## 3. Arsitektur

```
EXTRACT (harian)               TRANSFORM (Polars)                LOAD (DuckDB)
                                                                 lapisan 1 (per platform)
extract/blibli.py    ─┐        transform/blibli.py ──┐           ├─ blibli_produk
extract/tokopedia.py ─┤        transform/tokopedia.py┤           ├─ tokopedia_produk
                      │          ↓ parser bersama    │           lapisan 2 (star schema)
data_lake/raw/        │          ↓ Pandera ──gagal──►│──────────►├─ dim_produk
 <sumber>/            │          ↓ lolos             │           ├─ dim_toko
 date=YYYY-MM-DD/     │        transform/model.py    │           ├─ dim_tanggal
  <kat>_page_NNN.json ◄┤        (bangun dim + fakta)  │           ├─ fakta_harga
  varian/*.json (Blibli)                             │           ├─ v_produk (view)
  _SUKSES                                            └──────────►├─ produk_karantina
 (tidak pernah diubah)                                           └─ pipeline_runs
data_lake_vps/raw/tokopedia/...  (salinan dari VPS)
```

## 4. Extract

### 4.1 Blibli (hanya dari laptop)

- **Dua kategori:** `BU-1000190` (Buah Lokal) dan `BU-1000191` (Buah
  Impor), masing-masing maksimal 20 halaman × 40 produk. Halaman 21 →
  HTTP 422 = selesai, bukan galat.
- Berkas: `<kategori>_page_NNN.json`.
- **Varian (sejak 8 November):** setiap produk dengan `hasVariants = true`
  (±168 per hari):
  - `GET /backend/product-detail/products/ps--<id>/_summary` → disimpan
    `varian/ps--<id>.json`. Isinya daftar opsi (`data.options[]`) dan
    harga opsi default.
  - Untuk setiap opsi yang `selected = false`:
    `GET .../is--<itemSku>/_summary` → `varian/is--<itemSku>.json`.
    Isinya harga opsi itu (`data.price.offered`, `listed`,
    `listDiscount`).
  - Satu produk gagal (misalnya 404) → dilewati, tarikan tetap
    `berhasil`, log: `varian: N produk, M gagal`. **Semua** gagal →
    `sebagian`.
- **Blibli memblokir IP VPS** (HTTP 403 Cloudflare), jadi Blibli hanya
  ditarik dari laptop.
- Tanggal sebelum 8 November tidak punya folder `varian/`. Harga opsi
  lain untuk tanggal itu **tidak ada** dan tidak bisa diambil mundur.

### 4.2 Tokopedia (laptop + VPS)

- `POST https://gql.tokopedia.com/graphql/SearchProductV5Query`.
- Parameter: `source=directory`,
  `identifier=makanan-minuman_buah_buah-buahan`, `sc=2705`, `q=""`,
  `rows=60`, `page=N`, `start=(N-1)*60`, `ob=23`.
- Kunjungi beranda dulu dalam sesi yang sama untuk mendapat cookie Akamai.
- Halaman 1 sampai halaman kosong pertama atau halaman 100 (sekitar
  6.000 baris; ±5.500 produk unik karena halaman tumpang tindih).
- Query GraphQL hanya meminta 13 field. Berat, stok, dan jumlah terjual
  pasti **tidak ada** di hasil cari.
- **Halaman produk** (berat, stok, terjual pasti, varian) bisa diambil
  dengan `curl_cffi` dari laptop dan VPS (diuji 7 Nov, 22/22 dengan coba
  ulang), tetapi **tidak** masuk penarik harian. Hanya ada di notebook
  bagian 5 untuk Mangga Manalagi.

### 4.3 Aturan bersama

- Jeda acak **1,5–3 detik** antar-permintaan.
- Coba ulang 3 kali dengan jeda makin panjang (2, 4, 8 detik) untuk galat
  jaringan, `429`, atau `5xx`.
- Setiap jawaban disimpan **apa adanya**. Kalau folder tanggal itu sudah
  ada, isinya ditimpa utuh.
- Kalau satu halaman tetap gagal setelah 3 kali coba, penarikan berhenti
  di situ. Halaman yang sudah tersimpan tetap dipakai, dan run dicatat
  `sebagian` (bagian 9).

### 4.4 Jadwal harian (sudah jalan)

| Mesin | Jadwal | Sumber |
|---|---|---|
| Laptop | Task Scheduler `KebunIbu-TarikHarian`, 06:00 + 12:00 (cadangan), jalan saat laptop menyala kalau terlewat | Blibli + Tokopedia, lalu `sinkron_vps.py` |
| VPS (DomaiNesia, Jakarta, 1 GB) | cron 06:00 + 12:00 WIB | Tokopedia saja |

- Sumber yang sudah sukses hari itu (`_SUKSES`) dilewati. `--ulang
  <sumber>` memaksa tarik ulang. `--sumber` memilih sumber.
- `sinkron_vps.py` menyalin folder VPS yang sudah `_SUKSES` ke
  `data_lake_vps/raw/tokopedia/` di laptop.

## 5. Transform

### 5.1 Lapisan 1: tabel per platform

Setiap modul platform membaca semua berkas mentah satu tanggal dan
menghasilkan satu DataFrame.

#### `blibli_produk`: satu baris per opsi (`item_sku`) per tanggal

**Baris default** (`opsi_default = true`) berasal dari kartu hasil cari.
**Baris opsi lain** (`opsi_default = false`) berasal dari
`varian/is--<itemSku>.json`. Tanggal tanpa `varian/` hanya punya baris
default.

| # | Kolom | Baris default (kartu cari) | Baris opsi lain (`is--` file) |
|---|---|---|---|
| 1 | `tanggal` | tanggal folder | sama |
| 2 | `produk_id` | `id` | `data.productSku` |
| 3 | `item_sku` | `itemSku` | `data.itemSku` |
| 4 | `opsi_default` | `true` | `false` |
| 5 | `nama` | `name` | salin dari baris default |
| 6 | `variant` | `variant` | `data.options[selected].attributes[0].value` |
| 7 | `harga` | `price.salePrice` | `data.price.offered` |
| 8 | `harga_coret` | `price.listPrice` | `data.price.listed` |
| 9 | `diskon_persen` | `price.discount` | `data.price.listDiscount` |
| 10 | `harga_voucher` | `contextualPrice.priceDisplay` ("Rp39.100" → 39100) | NULL |
| 11 | `harga_coret_voucher` **[usulan Claude]** | `contextualPrice.strikeThroughPriceDisplay` → angka | NULL |
| 12 | `diskon_voucher_persen` | `contextualPrice.discount` | NULL |
| 13 | `kampanye` | `campaignInfo.name` | NULL |
| 14 | `harga_sebelum_kampanye` | `price.offerPriceDisplay` → angka | NULL |
| 15 | `merchant_code` | `merchantCode` | salin |
| 16 | `penjual` | `merchantName` | salin |
| 17 | `resmi` | `official` | salin |
| 18 | `lokasi` | `location` | salin |
| 19 | `lencana_toko` | `badge.merchantBadge` | salin |
| 20 | `rating_toko` | `review.sellerRating` | salin |
| 21 | `merek` | `brand` | salin |
| 22 | `kategori` | `" > ".join(categoryNameHierarchy)` | salin |
| 23 | `kategori_tarik` | awalan nama berkas (`BU-1000190`/`BU-1000191`) | salin |
| 24 | `rating` | `review.absoluteRating`, **NULL kalau `review.count = 0`** | salin |
| 25 | `jumlah_ulasan` | `review.count` | salin |
| 26 | `total_terjual` | `soldCountTotal` (NULL tetap NULL) | salin |
| 27 | `terjual_bulan_ini_min` | angka dari `monthlySoldCountLabel` ("Dibeli 100+ kali bulan ini" → 100) | NULL |
| 28 | `url` | `"https://www.blibli.com" + url` | salin |
| 29 | `sku` | `sku` | NULL (berkas `is--` tidak punya `sku`) |

Catatan:
- `sku` **disimpan** (keputusan pengguna 8 Nov) walaupun sama dengan `id`
  di 24.000 dari 24.000 baris (18 Okt – 8 Nov): datanya bisa berubah,
  jadi dibandingkan lewat cek G (bagian 6.1). Yang punya kode tambahan
  adalah `itemSku` (`id` + `-00001`), disimpan sebagai `item_sku`.
- Kolom 10–14 dan 27 hanya ada di kartu cari, yang hanya memuat opsi
  default. Untuk opsi lain nilainya NULL, bukan ditebak.
- `harga_coret_voucher` ditambahkan **[usulan Claude]** supaya cek D
  (bagian 6) bisa dijalankan sebagai kolom.
- `itemCode` di berkas varian **tidak dipakai**: penomorannya terbalik
  terhadap `itemSku` (500 gr = `MTA-…-00002`). Hanya `itemSku` yang
  cocok dengan halaman.
- Kunci unik: (`item_sku`, `tanggal`). Kalau satu `item_sku` muncul di
  dua kategori, yang pertama dipertahankan.

#### `tokopedia_produk`: satu baris per produk per tanggal

`tanggal`, `produk_id`, `nama`, `harga` (`price.number`), `harga_asli`
(`price.original` → angka, "" → NULL), `diskon_persen`, `toko_id`,
`nama_toko`, `kota`, `tier_toko`, `rating` ("" → NULL), `terjual_label`
(label `ri_product_credibility`), `kategori` (`category.breadcrumb`),
`url` (tanpa query string). Kunci unik: (`produk_id`, `tanggal`).

Tiga hal Tokopedia masih terbuka (bagian 13): arti `harga_asli`, cara
mengisi `diskon_persen`, dan pilihan salinan laptop vs VPS.

#### Kolom turunan (kedua platform)

`berat_gram`, `sumber_berat` (`nama` / `variant` / `usp` / `url`), dan
`jenis_satuan` (`berat` / `jumlah` / `kemasan` / `lain`). Dihitung di
lapisan 1 karena butuh field mentah yang bukan kolom
(`uniqueSellingPoint` Blibli). Aturannya di bagian 5.2.

### 5.2 Parser bersama (`transform/parser.py`)

Semua berupa fungsi Python murni, masing-masing dengan unit test.

#### Berat (`berat_gram`), aturan 4 November

| Aturan | Contoh | Hasil |
|---|---|---|
| Satuan berat: `kg`, `kilogram`, `kilo`, `gram`, `gr`, `grm`, `g`, `ons` (100 g); huruf besar/kecil sama | "1 KILO", "500 grm" | 1000, 500 |
| Cari di **seluruh nama**, bukan hanya kata pertama setelah angka | "Mangga Super Fresh Premium 500gr" | 500 |
| Rentang → titik tengah | "470 - 500 G", "170 - 180 G" | 485, 175 |
| **Pecahan dibaca** (menggantikan aturan lama "dilewati") | "1/2 kg", "1/4Kg" | 500, 250 |
| Koma/titik + 1–2 angka = desimal | "1,5 kg", "2.5 kg", "0,95kg" | 1500, 2500, 950 |
| Titik + tepat 3 angka = ribuan | "1.000 gr" | 1000 |
| Per kilo | "/kg", "per kg", "Kiloan", "isi 3-5/ kg" | 1000 |
| Kata bilangan (daftar kecil) | "sekilo", "setengah kilo" | 1000, 500 |
| Dua berat yang **berbeda** (dua pilihan dalam satu nama) | "1 Kg 1/2 Kg" | `None`, `jenis_satuan = lain` |
| Berat yang sama ditulis dua kali | "1 kg ( 0.9 - 1.1 kg / pack)" | 1000 |
| Berat tunggal di dalam rentang lain **[usulan Claude]** | "500 gram ( 400 - 500 gram / pack)" | 500 |
| Di luar 100–20.000 g | "Semangka 30 kg", "+-0.9g-1kg" | `None` |
| Berat **dan** jumlah | "Apel 1 kg isi 6 pcs" | berat menang |

#### Berat cadangan (urutan prioritas)

| Platform | Urutan | Alasan |
|---|---|---|
| Blibli | `variant` → nama → `uniqueSellingPoint` | `variant` = opsi yang harganya tercatat. "Apel Fuji Super Fresh 1 Kg" dengan variant "500 gr" berharga Rp46.000 = harga 500 gr (dicek di halaman, 5 Nov). Berat dari nama akan membagi dua harga per kg. |
| Tokopedia | nama → URL | Slug URL dipakai **hanya** kalau nama tanpa berat. Slug ambigu ("1 2 kg" dari 1/2, 1.2, atau 1-2) dilewati. Kecocokan URL vs nama: 98% (4.528/4.616). |

`sumber_berat` mencatat asalnya. Urutan `uniqueSellingPoint` (paling
akhir) **[usulan Claude]**; usp hanya menambah ±12 nama.

#### Jenis satuan (`jenis_satuan`)

| Nilai | Kapan | Harga turunan |
|---|---|---|
| `berat` | berat terbaca | `harga_per_kg` |
| `jumlah` | tanpa berat, ada jumlah (pcs, buah, sisir, butir, biji) | `harga_per_buah` |
| `kemasan` | tanpa berat/jumlah, ada kemasan (pack, dus, box, paket) atau cairan (ml, liter) | — (disimpan untuk tinjauan, misalnya computer vision nanti) |
| `lain` | tanpa angka, dua berat berbeda, atau tidak cocok pola | — |

Satu tabel dengan kolom `jenis_satuan`, bukan tabel terpisah. Tampilan
per jenis dibuat lewat view.

#### Fungsi lain (tidak berubah)

| Fungsi | Aturan |
|---|---|
| `jenis_buah(nama)` | Kamus kata kunci → jenis (mangga, apel, pisang, jeruk, anggur, melon, alpukat, pepaya, buah naga, pir, …), dengan sinonim. Tidak cocok → `lainnya`. **Perangkap:** "manalagi" juga ada di Apel Manalagi (±40 produk) dan manisan belimbing "simanalagi". Mangga Manalagi = nama memuat **mangga dan manalagi**. |
| `asal(...)` | Blibli: dari kategori, `asal_sumber = 'label'`. Tokopedia: aturan kata + varietas, `asal_sumber = 'aturan'`. |
| `olahan(nama)` | `True` untuk bibit, benih, keripik, sale, jus, dll. Baris tetap disimpan, hanya ditandai. Kata "kulit" dan "daun" sering salah cocok. **Aturan akhir ditunda** (bagian 13). |
| `terjual_min(...)` | Blibli: angka pasti → batas bawah rentang Tokopedia. Tokopedia: "60+ terjual" → 60, "1rb+ terjual" → 1000. |
| `jenis_toko(...)` | Blibli: `resmi`/`biasa`. Tokopedia: `tier_<n>`, arti tier belum diverifikasi. |
| `region(kota)` | Kota → `jabodetabek` / `jawa_lain` / `luar_jawa`. |

**Aturan asal diuji terhadap Blibli,** yang label aslinya diketahui
(tidak berubah).

### 5.3 Lapisan 2: star schema (`transform/model.py`)

```
                    dim_toko
         toko_key, sumber, toko_id, nama_toko,
         kota, region, jenis_toko
                       │
dim_produk ───── fakta_harga ───── dim_tanggal
produk_key, sumber,   tanggal, produk_key, toko_key,   tanggal, tahun,
produk_id, nama,      item_sku, opsi_default, variant,  bulan, minggu, hari
jenis_buah, asal,     harga, harga_coret, diskon,
asal_sumber, olahan   berat_gram, sumber_berat, jenis_satuan,
                      harga_per_kg, harga_per_buah, rating, terjual_min
```

- **Grain `fakta_harga`:** satu baris = satu **opsi** produk di satu
  marketplace pada satu tanggal tarik. Tokopedia: satu opsi per produk
  (`item_sku` = `produk_id`, `opsi_default = true`).
- `berat_gram` pindah dari `dim_produk` ke fakta, karena tiap opsi punya
  berat sendiri (500 gr vs 1 kg).
- **Kunci pengganti berbasis hash:** `produk_key = md5(sumber || '|' ||
  produk_id)`, `toko_key = md5(sumber || '|' || toko_id)`.
- **Kunci alami toko:** Blibli `merchant_code`, Tokopedia `shop.id`.
- **SCD tipe 1** untuk dimensi.
- `harga_per_kg = round(harga / berat_gram * 1000)` kalau `jenis_satuan =
  berat`; `harga_per_buah = round(harga / jumlah)` kalau `jumlah`. Selain
  itu NULL.
- `v_produk`: view datar fakta + tiga dimensi.
- Untuk analisis "satu harga per produk", filter `opsi_default = true`.

## 6. Validasi dan karantina

Skema Pandera untuk setiap DataFrame **sebelum dimuat**:

| Cek | Berlaku untuk |
|---|---|
| `produk_id`, `nama`, `tanggal` tidak kosong | lapisan 1 |
| `harga > 0` | lapisan 1, fakta |
| `rating` di antara 0–5, atau kosong | lapisan 1 |
| `diskon_persen` di antara 0–100 | lapisan 1 |
| `harga_per_kg` di antara 3.000–500.000, atau kosong (**batas ditinjau ulang**, bagian 13) | fakta |
| `sumber` ∈ {blibli, tokopedia} | dimensi, fakta |
| Blibli (`item_sku`, `tanggal`) unik; Tokopedia (`produk_id`, `tanggal`) unik | lapisan 1 |
| `produk_key` unik di `dim_produk`; `toko_key` unik di `dim_toko` | dimensi |
| setiap `produk_key`/`toko_key` di fakta ada di dimensinya | fakta |

### 6.1 Cek perbandingan kolom Blibli (diputuskan 7 November)

Kolom yang mirip dibandingkan, karena ini data, bukan algoritma: polanya
bisa berubah kapan saja. Baris yang gagal **masuk karantina** untuk
ditinjau manual.

| Cek | Aturan | Hasil di 22.400 baris (14 tanggal) |
|---|---|---|
| A | `harga_voucher < harga ≤ harga_coret` (bagian kiri hanya kalau `harga_voucher` ada) | 0 gagal |
| B | `diskon_persen` berbeda ≤ 1 poin dari `(1 − harga/harga_coret) × 100` | 0 gagal |
| D | `harga_coret_voucher = harga_coret` (kalau ada) | 0 gagal |
| E | `diskon_voucher_persen` berbeda ≤ 1 poin dari `(1 − harga_voucher/harga_coret) × 100` | 0 gagal |
| F | `harga_sebelum_kampanye ≥ harga`, dan berbeda dari `harga` hanya kalau `kampanye` terisi | **8 gagal** (2 produk mangga Rp10.000, diskon 60–75%, tanpa nama kampanye) |
| G | `sku = produk_id` (kalau `sku` ada; ditambahkan 8 Nov) | 0 gagal di 24.000 baris (18 Okt – 8 Nov) |
| C | `item_sku` opsi default berbeda dari kemarin | **Tanda saja, bukan karantina** (117 kali). Dibuat sebagai view DuckDB dengan `LAG` **[usulan Claude]**. |

### 6.2 Karantina

Baris yang gagal masuk ke `produk_karantina` (`sumber`, `tanggal`,
`produk_id`, `data` berupa JSON baris aslinya, `alasan`). **Tidak ada
baris yang dibuang diam-diam.** Jumlahnya dicatat di `pipeline_runs`.

## 7. Load

- Berkas: `warehouse/harga_buah.duckdb`.
- **Aman diulang (idempoten)**: dalam satu transaksi, hapus semua baris
  (`sumber`, `tanggal`) di lapisan 1, fakta, dan karantina, lalu sisipkan
  yang baru. Dimensi di-*upsert* per kunci.
- Tabel `pipeline_runs`: `run_id`, `mulai`, `selesai`, `sumber`,
  `tanggal`, `halaman_ditarik`, `baris_mentah`, `baris_dimuat`,
  `baris_karantina`, `status` (`berhasil` / `sebagian` / `gagal`),
  `pesan_galat`.

## 8. Menjalankan

```
python tarik_harian.py                              # dijalankan Task Scheduler / cron
python run.py --sumber blibli,tokopedia --tahap transform,load --tanggal 2026-11-08
```

`--tahap` bisa `extract`, `transform`, `load`, atau gabungannya. Proses
ulang tanpa menarik lagi dimungkinkan karena data mentah disimpan. Log
ditulis ke layar dan ke `logs/run_<run_id>.log`.

## 9. Penanganan galat

| Kejadian | Perilaku |
|---|---|
| Halaman gagal setelah 3 kali coba | Penarikan berhenti; halaman tersimpan diproses; status `sebagian` |
| Halaman pertama gagal (API berubah atau diblokir) | Status `gagal`, tidak ada yang dimuat, pesan galat dicatat |
| Satu ringkasan varian Blibli gagal | Produk itu hanya punya baris default; status tetap `berhasil` |
| Bentuk JSON berubah (kolom wajib hilang) | Transform gagal dengan pesan yang menyebut kolomnya; status `gagal` |
| Baris melanggar skema atau cek A/B/D/E/F | Dikarantina, run tetap jalan |
| Load gagal di tengah | Transaksi dibatalkan, DuckDB kembali ke keadaan sebelum run |

## 10. Pengujian

1. **Unit test parser** dengan nama produk asli, **termasuk nama Mangga
   Manalagi sungguhan**: "MANGGA MANALAGI 170 - 180 G", "Mangga Manalagi
   1 kg ( 0.9 - 1.1 kg / pack)", "Mangga manalagi segar manis 1/2 kg",
   "Mangga manalagi madu (Arum) … 1kg isi 3-5 buah", "Mangga Manalagi
   Potong Manis" (tanpa berat), "Mangga Manalagi Kiloan Raja Alpukat".
2. **Tes skema Pandera:** baris rusak buatan masuk karantina; satu tes per
   cek A, B, D, E, F, G.
3. **Tes integrasi** atas cuplikan kecil data mentah asli
   (`tests/fixtures/`), termasuk satu folder Blibli **dengan** `varian/`
   dan satu **tanpa**:
   - jumlah baris fakta = jumlah baris yang lolos validasi;
   - tidak ada kunci fakta tanpa pasangan di dimensi;
   - **menjalankan dua kali menghasilkan jumlah baris yang sama**;
   - produk yang tokonya tanpa kota tetap masuk fakta;
   - produk bervarian menghasilkan satu baris per opsi.
4. **Aturan asal vs label Blibli:** tingkat ketepatan dihitung dan
   dicetak.
5. **CI** (GitHub Actions): pytest + pipeline penuh atas cuplikan tadi,
   tanpa akses internet.

## 11. Susunan repo

Subfolder `data-science/` di repo kebun-ibu (17 Oktober).

```
kebun-ibu/data-science/
  extract/      blibli.py, tokopedia.py, http.py
  transform/    blibli.py, tokopedia.py, parser.py, model.py, skema.py
  load/         duckdb_loader.py
  tarik_harian.py, sinkron_vps.py, daftar_tugas_harian.ps1
  run.py
  eksplor.ipynb                     (eksplorasi, bukan kode produksi)
  transform.ipynb                   (tinjauan: kode + hasil tiap langkah transform)
  data_lake/raw/...                 (diabaikan git)
  data_lake_vps/raw/tokopedia/...   (salinan VPS, diabaikan git)
  data_lake/halaman_tokopedia/...   (notebook bagian 5, diabaikan git)
  warehouse/                        (diabaikan git)
  tests/
  .github/workflows/ci.yml
  requirements.txt, README.md
```

## 12. Tahapan hasil

1. ✅ Penarik Tokopedia + Blibli (kategori + varian), penarikan harian.
2. Lapisan 1 + validasi + karantina, dimuat ke DuckDB.
3. Star schema + `v_produk` + tes integrasi + CI.

## 13. Hal yang masih terbuka

Pengguna selesai membaca spec pada 8 November. Usulan di bawah dipakai
sebagai bawaan, dan **Claude menanyakan tiap poin saat task yang
memakainya dimulai** (misalnya #1–3 di Task 5, #5–6 di Task 1/7).

| # | Hal | Usulan Claude | Data pendukung |
|---|---|---|---|
| 1 | **`harga_asli` Tokopedia**: kartu cari menulis Rp25.000, halaman produk tidak menampilkan harga coret sama sekali | Simpan apa adanya di lapisan 1, tapi jangan dipakai sebagai harga coret di fakta sampai dicek di kartu hasil cari | Produk 1256380209 dan 8061245026; sama setiap hari 23 Okt – 7 Nov |
| 2 | **`diskon_persen` Tokopedia** selalu 0 dari API | Hitung dari `harga_asli` vs `harga` (tergantung #1) | 0 di semua baris |
| 3 | **Salinan laptop vs VPS** untuk Tokopedia di tanggal yang sama | Pakai salinan VPS; laptop hanya mengisi tanggal yang VPS tidak punya | Keduanya tarik setiap hari sejak 27 Okt |
| 4 | **Label Tokopedia yang belum dipakai**: `nett_price`, `promotion_label` ("Harga Diskon"), `ri_ribbon` ("12%"), `ri_product_offer` | Tidak dipakai dulu; tetap ada di data mentah | 614 / 637 / 640 / 4.356 baris pada 7 Nov |
| 5 | **Olahan** (aturan akhir) dan **batas harga per kg** karantina | Batas 2.000–2.000.000/kg (usulan 4 Nov) supaya anggur Nagano Rp4 jt/kg tidak salah dikarantina | Ditunda pengguna 4 Nov: "filter later" |
| 6 | **Multipack** ("8x125GR", "200 gr×12 Pcs") | Kalikan: 8 × 125 = 1.000 g | Penyebab utama harga per kg yang terlalu tinggi |
| 7 | **URL gambar pertama Blibli** (diterima 4 Nov untuk ide computer vision) | Tambah kolom `gambar` kalau masih diinginkan; tidak ada di daftar 29 kolom | — |
| 8 | **Arti `tier_toko`** Tokopedia | Tetap `tier_<n>` | Halaman produk menampilkan lencana hijau, artinya belum dicek |
| 9 | **Dashboard `/admin/pasar` + 4 insight** (usulan 26 Okt) | Menunggu keputusan pengguna | — |
| 10 | **Batas ketepatan aturan asal** | ≥ 90% terhadap label Blibli | — |
