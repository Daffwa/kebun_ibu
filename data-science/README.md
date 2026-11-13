# Pipeline harga buah

Pipeline **ETL** yang menarik produk buah dari **Blibli** dan **Tokopedia**
setiap hari, membersihkan dan menyeragamkannya di Python (Polars + Pandera),
lalu memuatnya ke **DuckDB** sebagai **star schema**. Target utama: harga
**Mangga Manalagi**. Hasilnya menjadi dasar model harga per kg di tahap
berikutnya.

Folder ini bagian dari repo `kebun-ibu`, tetapi berdiri sendiri. Venv, tes,
dan CI-nya terpisah dari situs Next.js, dan Vercel tidak membangun ulang situs
kalau yang berubah hanya folder ini.

Desain lengkap: `docs/superpowers/specs/2026-10-16-pipeline-harga-buah-design.md`.

## Alur

```
EXTRACT (harian)                TRANSFORM (Polars)                 LOAD (DuckDB)
                                                                   lapisan 1 (per platform)
extract/blibli.py    ─┐         transform/blibli.py    ─┐          ├─ blibli_produk
extract/tokopedia.py ─┤         transform/tokopedia.py ─┤          ├─ tokopedia_produk
                      ▼           ↓ parser bersama      │          lapisan 2 (star schema)
data_lake/raw/                    ↓ Pandera ── gagal ───┼────────► ├─ produk_karantina
  <sumber>/date=YYYY-MM-DD/       ↓ lolos               │          ├─ dim_produk
    <kategori>_page_NNN.json    transform/model.py      │          ├─ dim_toko
    varian/*.json   (Blibli)    (dimensi + fakta)  ─────┴────────► ├─ dim_tanggal
    halaman/*.json  (Tokopedia)                                    ├─ fakta_harga
    _SUKSES                                                        ├─ v_produk (view)
  (tidak pernah diubah)                                            └─ pipeline_runs
```

- **Data mentah tidak pernah diubah atau dihapus**, jadi transform dan load
  bisa diulang kapan saja tanpa menarik lagi.
- **Muat aman diulang**: dalam satu transaksi, data (sumber, tanggal) yang
  lama dihapus lalu diganti. Jalan dua kali = hasil sama.
- **Baris gagal validasi dikarantina, tidak dibuang**, lengkap dengan
  alasannya.
- **Setiap run tercatat** di `pipeline_runs` dan di `logs/run_<run_id>.log`.

## Star schema

```
                       dim_toko
            toko_key, sumber, toko_id, nama_toko,
            kota, region, jenis_toko
                          │
dim_produk ──────── fakta_harga ──────── dim_tanggal
produk_key, sumber,   tanggal, produk_key, toko_key,   tanggal, tahun,
produk_id, nama,      item_sku, opsi_default, variant,  bulan, minggu, hari
jenis_buah, asal,     harga, harga_coret, diskon_persen,
asal_sumber, olahan   berat_gram, sumber_berat, jenis_satuan,
                      harga_per_kg, harga_per_buah, rating, terjual_min
```

- **Grain `fakta_harga`**: satu **opsi** produk di satu marketplace pada satu
  tanggal. Untuk "satu harga per produk", filter `opsi_default = true`.
- Kunci pengganti: `md5(sumber || '|' || id)`. Dimensi SCD tipe 1.
- `harga_per_kg` hanya terisi kalau berat diketahui; `harga_per_buah` hanya
  kalau jumlah buah diketahui.

## Tabel di `warehouse/harga_buah.duckdb`

Gudang hanya berisi tanggal yang **lengkap**, yaitu yang punya harga semua opsi:
Blibli mulai **7 Nov 2026**, Tokopedia mulai **8 Nov 2026**. Tanggal sebelumnya
(27 Sep, 18 Okt – 6/7 Nov) hanya punya harga opsi bawaan, jadi tidak dimuat
(keputusan pengguna 9 Nov). Data mentahnya tetap di `data_lake/raw/` dan bisa
dimuat lagi dengan `run.py --tahap transform,load --tanggal <tanggal>`.

| Tabel | Isi |
|---|---|
| `blibli_produk`, `tokopedia_produk` | lapisan 1: satu baris per opsi, kolom asli + turunan |
| `produk_karantina` | baris yang ditahan validasi, dengan `alasan` |
| `fakta_harga` | harga per opsi per tanggal |
| `dim_produk`, `dim_toko`, `dim_tanggal` | dimensi |
| `pipeline_runs` | satu baris per run per sumber: jumlah baris, status, pesan galat |
| `v_produk` (view) | fakta + ketiga dimensi, datar |
| `v_opsi_berubah` (view) | produk yang opsi default-nya berganti dari tanggal sebelumnya |

## Menjalankan

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

python tarik_harian.py                    # tarik hari ini (dijadwalkan Task Scheduler)
                                          # lalu Task Scheduler juga menjalankan run.py --tahap transform,load
python run.py                             # extract + transform + load, kedua sumber, hari ini
                                          # (extract dilewati kalau hari itu sudah _SUKSES)
                                          # tanpa --tanggal: juga menyusulkan tanggal tertinggal
                                          # (folder _SUKSES belum dimuat; salinan VPS dipakai kalau
                                          # tarikan laptop gagal, status `sebagian` tanpa halaman varian)
python run.py --tahap transform,load --tanggal 2026-11-08   # proses ulang tanpa menarik
python run.py --sumber tokopedia
python evaluasi_asal.py --tanggal 2026-11-08                 # nilai aturan asal (lihat di bawah)

.venv\Scripts\python -m pytest -q         # semua tes, tanpa internet
```

Gudang DuckDB hanya bisa ditulis kalau tidak ada program lain yang membukanya
(notebook, DBeaver, Python lain, bahkan yang `read_only`). Tutup koneksi sesudah
membaca, supaya muat terjadwal 06:00/12:00 tidak gagal.

`run.py` keluar dengan kode 1 kalau ada sumber yang `gagal`. Satu sumber gagal
tidak menghentikan sumber lain.

Tempat meninjau setiap langkah: `transform/transform.ipynb` (kode fungsi +
hasilnya pada data asli).

## Susunan folder

| Folder / berkas | Isi |
|---|---|
| `extract/` | penarik Blibli (`urllib`) dan Tokopedia (`curl_cffi`), coba ulang |
| `transform/` | JSON mentah → lapisan 1, parser bersama, skema Pandera, star schema |
| `load/duckdb_loader.py` | tabel, view, dan muat idempoten |
| `run.py` | merangkai extract → transform → load |
| `evaluasi_asal.py` | ketepatan aturan asal lokal/impor |
| `tests/` | pytest; `tests/fixtures/` berisi JSON asli kecil |
| `data_lake/`, `warehouse/`, `logs/` | data lokal, **tidak masuk git** |
| `arsip/` | skrip dan data awal 27 September (datanya tidak masuk git) |

## Aturan asal lokal/impor

Tokopedia tidak memberi label lokal/impor, jadi asalnya ditebak dari kata di
nama produk (`transform/parser.py`, `asal_dari_nama`). Aturan itu dinilai
dengan produk Blibli, yang labelnya diketahui dari kategori:

| Tanggal | Produk | Ketepatan (yang dijawab) | Cakupan |
|---|---|---|---|
| 27 Sep 2026 | 1.723 | 95,6% | 39,2% |
| 9 Nov 2026 | 1.599 | 94,1% | 38,5% |

Ketepatannya di atas ambang 90%, tetapi sekitar 61% produk tidak bisa ditebak
(`tidak_diketahui`).

## Batasan

1. **Jangkauan terbatas.** Blibli sekitar 800 produk per kategori, Tokopedia
   sekitar 6.000 dari 85.846. Urutannya urutan bawaan situs, bukan acak, jadi
   condong ke produk populer. Produk juga bisa hilang dari hasil pencarian
   pada satu hari (9 Nov: 3 produk Mangga Manalagi Blibli), jadi deret
   harganya bolong. Data yang sudah ditarik dibiarkan apa adanya sebagai
   riwayat, tidak ditambal.
2. **Berat tidak selalu ditulis.** Sekitar 40% produk tidak menyebut berat,
   jadi harga per kg-nya kosong. Produknya tetap disimpan.
3. **Kolom tidak seragam.** Terjual Tokopedia berupa rentang ("60+
   terjual"), Blibli angka pasti (diseragamkan jadi batas bawah). Asal
   Tokopedia hanya tebakan (lihat di atas).
4. **Shopee tidak masuk.**
5. **Harga marketplace bukan harga pasar.** Sudah termasuk kemasan, ongkos
   kirim tersembunyi, dan komisi platform.
6. **API tidak resmi.** Marketplace umumnya melarang penarikan otomatis, dan
   API yang dipakai bisa berubah tanpa pemberitahuan.
