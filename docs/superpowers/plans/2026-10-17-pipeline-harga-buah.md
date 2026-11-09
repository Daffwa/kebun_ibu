# Pipeline ETL Harga Buah — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline ETL yang menarik produk buah dari Blibli dan Tokopedia,
membersihkannya di Polars, memvalidasinya dengan Pandera, lalu memuatnya
ke DuckDB sebagai star schema, lengkap dengan karantina, log run, tes,
dan CI.

**Architecture:** `extract/` menyimpan jawaban API mentah per halaman ke
`data_lake/raw/`. `transform/` mengubahnya menjadi tabel lapisan 1 per
platform, memvalidasinya (baris gagal → karantina), lalu membangun
dimensi + fakta. `load/` memuat semuanya ke DuckDB dalam satu transaksi
yang aman diulang. `run.py` merangkai tahapnya dan mencatat setiap run.

**Tech Stack:** Python 3.11, polars ≥ 1.0, pandera[polars] ≥ 0.24, duckdb ≥ 1.1,
pyarrow, curl_cffi ≥ 0.7, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-pipeline-harga-buah-design.md`
(di repo kebun-ibu). Executor membaca spec dan plan ini.

## Global Constraints

- **Lokasi: subfolder `data-science/` di repo kebun-ibu**
  (`C:\Users\Abraham\Documents\SMT5\Manpro\kebun-ibu\data-science`).
  Diputuskan pengguna pada 17 Oktober 2026, menggantikan usulan repo
  terpisah di spec bagian 11 dan 13.2. Semua path di plan ini relatif
  terhadap `data-science/`, kecuali yang diawali `kebun-ibu/` (akar repo).
  - `data-science/` punya `.venv`, `requirements.txt`, `pyproject.toml`,
    dan `.gitignore` sendiri.
  - Kode situs Next.js tidak boleh tersentuh, kecuali penyesuaian
    konfigurasi di Task 1 Step 1 dan Task 10 Step 6.
- **Executor tidak menjalankan git sama sekali** (tidak `init`, `add`,
  `commit`, atau `push`). Pengguna melakukan git sendiri untuk belajar.
  Setiap tugas diakhiri usulan pesan commit untuk pengguna.
- Python 3.11. Semua perintah dijalankan lewat `.venv\Scripts\python`.
- Pola ETL: transformasi di Python **sebelum** dimuat. Tidak memakai dbt,
  Airflow, Kafka, Selenium, atau BeautifulSoup.
- Data mentah **tidak pernah diubah** setelah ditulis. Tarik ulang pada
  tanggal yang sama mengganti isi folder tanggal itu secara utuh.
- **Tidak ada baris yang dibuang diam-diam.** Baris gagal validasi masuk
  `produk_karantina` dengan `alasan`.
- Kunci pengganti: `produk_key = md5(sumber || '|' || produk_id)`,
  `toko_key = md5(sumber || '|' || toko_id)`, sebagai heksadesimal
  huruf kecil (sama dengan `hashlib.md5(...).hexdigest()` dan `md5()`
  di DuckDB).
- Dimensi memakai SCD tipe 1 (nilai terbaru menimpa).
- Jeda acak 1,5–3 detik antar-halaman. Coba ulang 3 kali dengan jeda
  2, 4, 8 detik untuk galat jaringan, `429`, dan `5xx`.
- Tes **tidak boleh** mengakses internet. Pemanggilan HTTP selalu lewat
  fungsi yang bisa disuntikkan (parameter), dan tes memberi fungsi palsu.
- Nama kode, kolom, dan pesan dalam bahasa Indonesia, mengikuti spec.

## Review Focus

1. **Toko tanpa kota atau tanpa ID.** Produknya tetap masuk fakta. Join
   biasa tidak mencocokkan NULL, dan kasus ini sempat hilang di demo.
   Tes: Task 7 `test_toko_tanpa_kota_tetap_masuk_fakta`.
2. **Halaman di luar batas.** Blibli halaman 21 menjawab `HTTP 422`;
   Tokopedia halaman 150 menjawab daftar kosong. Keduanya berarti
   "selesai", bukan galat. Tes: Task 2
   `test_422_setelah_halaman_terakhir_berarti_selesai`, Task 3
   `test_berhenti_di_halaman_kosong`.
3. **Run diulang pada tanggal yang sama.** Jumlah baris harus tetap
   sama, dan baris lama tanggal itu diganti, bukan ditambah. Tes: Task 8
   `test_muat_dua_kali_jumlah_sama`.
4. **Bentuk JSON berubah** (kolom wajib hilang). Transform harus gagal
   dengan pesan yang menyebut kolomnya, bukan menghasilkan kolom NULL
   diam-diam. Tes: Task 4 `test_kolom_hilang_gagal_jelas`, Task 5 idem.
5. **Label terjual Tokopedia di luar pola yang sudah dilihat** ("1,5rb+",
   "10rb+", label kosong). Hasilnya angka yang benar atau `None`, tidak
   pernah crash. Tes: Task 1 `test_terjual_dari_label`.

## Status dan perubahan (7 November 2026)

| Task | Status |
|---|---|
| 2 Blibli extract | ✅ selesai, + tarikan varian (`07ddbff`) |
| 3 Tokopedia extract | ✅ selesai |
| di luar plan | ✅ `tarik_harian.py` (Task Scheduler + cron VPS), `sinkron_vps.py`, `eksplor.ipynb` |
| 1, 4, 5, 6, 7 | **diperbarui hari ini** mengikuti spec bagian 0 (berat, kolom Blibli, satu baris per opsi, cek A–G) |
| 1A berat (8 Nov) | ✅ kode + tes (`berat_gram`, `berat_dari_slug`, `pilih_berat`, `jumlah_buah`, `jenis_satuan`, `mangga_manalagi`, `satuan_baris` [A1]), + aturan rentang dua satuan ("900g - 1 Kg" → 950, dari data Tokopedia asli). Bagian di `transform/transform.ipynb`; **menunggu tinjauan pengguna** |
| 1B (8 Nov) | ✅ kode + tes: `jenis_buah`, `olahan` (tanpa `sale`/`pohon`), `asal_dari_nama`, `terjual_dari_label`, `ember_terjual`, `region` (+ semua kota Jawa yang ada di data), multipack `berat_dikali`. **Menunggu tinjauan pengguna** di notebook |
| 4 Blibli transform (8 Nov) | ✅ `transform/blibli.py` + 21 tes + fixture asli (8 Nov dengan varian, 6 Nov tanpa). Semua 15 tanggal asli: 24.648 baris, 2,5 detik. Opsi tanpa harga → harga NULL (B). URL tanpa pelacak + `?ds=` [usulan Claude]. **Menunggu tinjauan pengguna** |
| 5a halaman produk Tokopedia (8 Nov, keputusan 13 #11 = a) | ✅ `extract/tokopedia.py`: `cache_dari_html`, `ambil_produk_http` (sesi baru per percobaan), `tarik_halaman_produk` → `halaman/<id>.json` untuk produk `mangga_manalagi`; 9 tes baru, suite 225 lulus. Uji nyata 8 Nov: 25 produk, 23 berhasil, 2 gagal, 25 dari 48 percobaan halaman kosong, 591 detik, 1,4 MB. **Menunggu keputusan aturan berat halaman vs nama** |
| 5 Tokopedia transform (8 Nov) | ✅ `transform/tokopedia.py` (22 kolom: + `induk_id`, `opsi_default`, `variant`, `jumlah_buah`, `berat_dikali`), **satu baris per opsi** (keputusan pengguna: opsi lain dari halaman produk Manalagi), berat opsi → halaman (bersyarat) → nama → URL; 17 tes + fixture asli 8 Nov (`tests/fixtures/tokopedia/date=2026-11-08`, halaman dipangkas). Suite 242 lulus. 14 tanggal asli: 77.810 baris, 9 detik; 8 Nov Manalagi 36 baris (opsi 18, nama 16, halaman 2). **Menunggu tinjauan pengguna** |
| 8–11 | belum, tidak berubah |

**Aturan tinjauan (8 November):** setiap task 1, 4, 5, 6, 7, 8 diakhiri
dengan menambah satu bagian di `data-science/transform/transform.ipynb`: sel kode
fungsi baru (`tampilkan_kode(fungsi)` dari sel Persiapan: pygments
`github-dark`) lalu sel yang menjalankannya pada data asli terbaru
dan menampilkan hasilnya. Notebook hanya memanggil fungsi dari `.py`,
tidak menulis ulang logika. Task belum dianggap selesai sebelum
pengguna meninjau bagian itu.

Urutan berikutnya: **Task 1 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11.**
Task 5 punya tiga hal terbuka (spec 13 #1–3); kerjakan bagian yang sudah
pasti dulu.

## Urutan pengerjaan (diubah 17 Oktober 2026)

Pengguna membangun sendiri dengan bimbingan, dan memilih urutan ini:
1. Task 2, lalu Task 3 (extract dulu), supaya ada data segar.
2. **Profil data dengan Polars** atas data mentah segar dari kedua sumber:
   satuan berat, label terjual, kota, tier toko, dan nama yang tidak
   cocok pola. Ini langkah eksplorasi, bukan kode produksi.
3. Task 1 (parser), dengan aturan yang disesuaikan hasil profil.
4. Task 4 dan seterusnya sesuai urutan.

Task 2–3 tidak bergantung pada parser, jadi urutan ini aman.

## Fakta yang sudah diverifikasi (17 Oktober 2026)

- **Blibli kategori:** `GET https://www.blibli.com/backend/search/products`
  dengan `category=<id>&page=N&start=(N-1)*40&itemPerPage=40&channelId=web`
  dan header browser dari `kebun-ibu/skrip/tarik_blibli.py` (`KEPALA`)
  ditambah `Referer: https://www.blibli.com/cari?category=<id>`.
  - `BU-1000190` (Buah Lokal): 3.346 produk. `BU-1000191`: Buah Impor.
  - `data.paging.total_page` maksimal **20**. Halaman 21 → **HTTP 422**.
- **Bentuk produk Blibli:** `id`, `sku`, `merchantCode`, `name`,
  `price{salePrice, listPrice, minPrice, discount}`,
  `review{absoluteRating, count}`, `location`, `merchantName`,
  `official` (bool), `soldCountTotal`, `categoryNameHierarchy` (list),
  `url` (relatif, diawali `/p/`).
- **Tokopedia kategori:** spec bagian 4.2. Jawabannya berupa list:
  `[0].data.searchProductV5.data.products`. Setiap produk punya `id`
  (int), `name`, `url`, `price{number, original ("Rp29.500" atau ""),
  discountPercentage}`, `shop{id, name, city, tier}`, `rating`
  (string, bisa ""), `category{breadcrumb}`, dan `labelGroups[]`. Label
  terjual ada di elemen dengan `position == "ri_product_credibility"`.
- **Label terjual yang terlihat:** angka pasti di bawah 30 ("23 terjual"),
  lalu "30+" sampai "80+" per puluhan, "100+", "250+", "500+", "750+",
  "1rb+", "2rb+", "3rb+".
- **Pandera (polars backend):** `SchemaErrors.failure_cases` punya kolom
  `index` (nomor baris) dan `check`. Diuji di pandera 0.34.1 + polars 2.0.
- **DuckDB membaca DataFrame Polars lewat Arrow dan butuh `pyarrow`.**
  Tanpa pyarrow: `ModuleNotFoundError`.

## Susunan berkas

```
kebun-ibu/data-science/
  requirements.txt, pyproject.toml, .gitignore, README.md
  run.py                         CLI: tahap extract/transform/load + pipeline_runs
  transform/transform.ipynb      tinjauan pengguna: kode + hasil tiap langkah
  evaluasi_asal.py               ketepatan aturan asal vs label Blibli
  extract/__init__.py
  extract/http.py                jeda, coba ulang, simpan halaman, HasilTarik
  extract/blibli.py              tarik kategori Blibli
  extract/tokopedia.py           tarik kategori Tokopedia
  transform/__init__.py
  transform/parser.py            fungsi murni: berat, jenis, asal, olahan, terjual, region
  transform/blibli.py            mentah → blibli_produk
  transform/tokopedia.py         mentah → tokopedia_produk
  transform/skema.py             skema Pandera + pisahkan()
  transform/model.py             lapisan 1 → dim_produk, dim_toko, dim_tanggal, fakta_harga
  load/__init__.py
  load/duckdb_loader.py          DDL, muat idempoten, view v_produk, pipeline_runs
  tests/fixtures/blibli/date=2026-09-27/*.json
  tests/fixtures/tokopedia/date=2026-10-13/*.json
  tests/test_parser.py, test_http.py, test_extract_blibli.py,
  tests/test_extract_tokopedia.py, test_transform_blibli.py,
  tests/test_transform_tokopedia.py, test_skema.py, test_model.py,
  tests/test_loader.py, test_pipeline.py, test_evaluasi_asal.py
  .github/workflows/ci.yml
```

---

### Task 1: Kerangka proyek + parser bersama

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `.gitignore`,
  `extract/__init__.py`, `transform/__init__.py`, `load/__init__.py`,
  `transform/parser.py`
- Test: `tests/test_parser.py`

> **Diperbarui 7 November:** aturan berat mengikuti spec 5.2 (pecahan
> dibaca, cari di seluruh nama, desimal/ribuan, per kilo, kata bilangan,
> dua berat berbeda → `None`). Step 1 sudah selesai (folder, venv,
> requirements ada). `tests/test_parser.py` yang lama ditulis ulang.

**Interfaces:**
- Consumes: `POLA_OLAHAN` dari `kebun-ibu/skrip/bersihkan_blibli.py`.
  Logika berat **tidak** disalin lagi; aturannya dari spec 5.2.
- Produces (`transform/parser.py`):
  - `berat_gram(teks: str | None) -> int | None`: dipakai untuk nama,
    `variant`, `uniqueSellingPoint`, dan slug URL.
  - `berat_dari_slug(url: str | None) -> int | None`: slug Tokopedia
    (bagian setelah nama toko, tanpa ID panjang, `-` → spasi). Slug
    ambigu (`\b\d+ \d+ ?<satuan>`) → `None`.
  - `pilih_berat(kandidat: list[tuple[str, str | None]]) -> tuple[int | None, str | None]`:
    `kandidat` = daftar (`sumber_berat`, teks) urut prioritas; hasilnya
    berat pertama yang terbaca dan sumbernya, atau `(None, None)`.
  - `jumlah_buah(nama: str) -> int | None`: angka sebelum `pcs`, `pc`,
    `buah`, `sisir`, `butir`, `biji`, `btr`.
  - `jenis_satuan(nama: str, berat: int | None) -> str`: `berat` /
    `jumlah` / `kemasan` / `lain` (spec 5.2).
  - `jenis_buah(nama: str) -> str`
  - `olahan(nama: str) -> bool`
  - `asal_dari_nama(nama: str) -> str`, hasilnya `"lokal"`, `"impor"`,
    atau `"tidak_diketahui"`
  - `terjual_dari_label(label: str | None) -> int | None`
  - `ember_terjual(n: int | None) -> int | None`
  - `region(kota: str | None) -> str`, hasilnya `"jabodetabek"`,
    `"jawa_lain"`, `"luar_jawa"`, atau `"tidak_diketahui"`

- [ ] **Step 1: Buat folder dan venv**

```
cd C:\Users\Abraham\Documents\SMT5\Manpro\kebun-ibu
mkdir data-science
cd data-science
python -m venv .venv
```

Supaya alat situs tidak ikut memindai folder Python, ubah dua berkas di
akar kebun-ibu:
- `kebun-ibu/tsconfig.json`: `"exclude": ["node_modules", "data-science"]`
- `kebun-ibu/eslint.config.mjs`: tambahkan `"data-science/**"` ke
  `globalIgnores`

Run (dari akar kebun-ibu): `npx tsc --noEmit` lalu `npm run lint`
Expected: keduanya bersih, sama seperti sebelum diubah.

`requirements.txt`: `polars>=1.0`, `pandera[polars]>=0.24`,
`duckdb>=1.1`, `pyarrow`, `curl_cffi>=0.7`, `pytest>=8`.

`pyproject.toml`: hanya `[tool.pytest.ini_options]` dengan
`pythonpath = ["."]` dan `testpaths = ["tests"]`.

`.gitignore`: `.venv/`, `data_lake/`, `warehouse/`, `logs/`,
`__pycache__/`, `.pytest_cache/`.

Run: `.venv\Scripts\python -m pip install -r requirements.txt`
Expected: selesai tanpa galat.

- [ ] **Step 2: Tulis tes yang gagal**

```python
import pytest
from transform.parser import (berat_gram, berat_dari_slug, pilih_berat, jenis_satuan,
                              jenis_buah, olahan, asal_dari_nama,
                              terjual_dari_label, ember_terjual, region)

@pytest.mark.parametrize("nama,gram", [
    # Mangga Manalagi asli (target utama)
    ("MANGGA MANALAGI 170 - 180 G", 175),
    ("Mangga Manalagi 1 kg ( 0.9 - 1.1 kg / pack)", 1000),   # berat sama ditulis dua kali
    ("Mangga Manalagi 500 gram ( 400 - 500 gram / pack)", 500),   # berat tunggal di dalam rentang → berat tunggal
    ("Mangga manalagi segar manis 1/2 kg", 500),              # pecahan DIBACA (aturan baru)
    ("Mangga manalagi madu (Arum )fres & segar  tua pohon 1kg isi 3-5 buah.", 1000),
    ("Mangga Manalagi Super Kiloan Raja Alpukat", 1000),      # kiloan = 1 kg
    ("Mangga Manalagi Potong Manis", None),                   # tanpa berat
    ("Mangga Manalagi Madu", None),
    # aturan umum
    ("PEPAYA CALIFORNIA 1300 - 1500 GR", 1400),
    ("MANGGA HARUMANIS 470 - 500 G", 485),
    ("Avocadron Alpukat Mentega Mini [Paket 2 Kg]", 2000),
    ("Castle Farms Kurma Ajwa 500gr", 500),
    ("Anggur 1,5kg", 1500),
    ("Apel 2.5 kg", 2500),
    ("Jeruk 0,95kg", 950),
    ("Salak Pondoh 1.000 gr", 1000),                          # titik + 3 angka = ribuan
    ("Jeruk songkit ijo 500 grm", 500),
    ("Alpukat Mentega 1 KILO", 1000),
    ("Jeruk Medan 1/4Kg", 250),
    ("Pisang sekilo", 1000),
    ("Anggur setengah kilo", 500),
    ("Mangga isi 3-5/ kg", 1000),
    ("Kelengkeng per kg", 1000),
    ("Apel Fuji 1 Kg 1/2 Kg", None),                          # dua pilihan berbeda
    ("Apel 1 kg isi 6 pcs", 1000),                            # berat menang atas jumlah
    ("Kiwi Green 4s Impor 1 pack", None),
    ("Semangka 30 kg", None),                                 # di atas 20.000 g
    ("Cabe 50 g", None),                                      # di bawah 100 g
    ("Mangga +-0.9g-1kg", None),                              # salah ketik, di luar batas
    (None, None),
])
def test_berat_gram(nama, gram):
    assert berat_gram(nama) == gram

@pytest.mark.parametrize("url,gram", [
    ("https://www.tokopedia.com/toko/mangga-manalagi-madu-1-kg?extParam=x", 1000),
    ("https://www.tokopedia.com/toko/mangga-manalagi-1-2-kg", None),   # ambigu: 1/2? 1.2? 1-2?
    ("https://www.tokopedia.com/toko/mangga-manalagi-500gr-1731543572100384126", 500),
    (None, None),
])
def test_berat_dari_slug(url, gram):
    assert berat_dari_slug(url) == gram

def test_pilih_berat_variant_menang_atas_nama():
    # Blibli NAS-70965-00407: nama "1 Kg", variant "500 gr", harga = harga 500 gr
    assert pilih_berat([("variant", "500 gr"), ("nama", "Apel Fuji Super Fresh 1 Kg")]) == (500, "variant")
    assert pilih_berat([("variant", None), ("nama", "Mangga 1 kg")]) == (1000, "nama")
    assert pilih_berat([("variant", "Standar"), ("nama", "Mangga Potong")]) == (None, None)

@pytest.mark.parametrize("nama,berat,jenis", [
    ("Mangga Manalagi 1 kg", 1000, "berat"),
    ("Buah Naga Merah 1 Buah", None, "jumlah"),
    ("Pisang Cavendish 1 sisir", None, "jumlah"),
    ("Kiwi Green 4s Impor 1 pack", None, "kemasan"),
    ("Jus Jeruk 250 ml", None, "kemasan"),
    ("Mangga Manalagi Madu", None, "lain"),
    ("Apel Fuji 1 Kg 1/2 Kg", None, "lain"),
])
def test_jenis_satuan(nama, berat, jenis):
    assert jenis_satuan(nama, berat) == jenis

@pytest.mark.parametrize("nama,jenis", [
    ("MANGGA HARUMANIS 470 - 500 G", "mangga"),
    ("DRAGON FRUIT RED LOKAL", "buah naga"),
    ("Buah Naga Merah", "buah naga"),
    ("Avocadron Alpukat Mentega", "alpukat"),
    ("PEAR MADU PREMIUM", "pir"),
    ("Apel Fuji", "apel"),
    ("Kurma Ajwa", "lainnya"),
])
def test_jenis_buah(nama, jenis):
    assert jenis_buah(nama) == jenis

def test_olahan():
    assert olahan("Keripik Pisang 250g")
    assert olahan("Bibit Mangga Irwin")
    assert not olahan("Pisang Cavendish 1 kg")

@pytest.mark.parametrize("nama,asal", [
    ("Kiwi Green 4s Impor", "impor"),
    ("Anggur Red Globe Premium Import", "impor"),
    ("Apel Fuji 1 kg", "impor"),
    ("Jeruk Sunkist", "impor"),
    ("Salak Pondoh 1 kg", "lokal"),
    ("Manggis Super", "lokal"),
    ("Mangga Arumanis", "lokal"),
    ("Jeruk Medan Lokal", "lokal"),
    ("Pisang Cavendish", "tidak_diketahui"),
])
def test_asal_dari_nama(nama, asal):
    assert asal_dari_nama(nama) == asal

@pytest.mark.parametrize("label,n", [
    ("23 terjual", 23), ("100+ terjual", 100), ("1rb+ terjual", 1000),
    ("1,5rb+ terjual", 1500), ("10rb+ terjual", 10000),
    ("", None), (None, None), ("Hemat s.d 8%", None),
])
def test_terjual_dari_label(label, n):
    assert terjual_dari_label(label) == n

@pytest.mark.parametrize("n,ember", [
    (0, 0), (23, 23), (29, 29), (30, 30), (47, 40), (99, 90), (100, 100),
    (249, 100), (250, 250), (600, 500), (800, 750), (1499, 1000),
    (6874, 6000), (None, None),
])
def test_ember_terjual(n, ember):
    assert ember_terjual(n) == ember

@pytest.mark.parametrize("kota,hasil", [
    ("Jakarta Barat", "jabodetabek"), ("Kota Jakarta Barat", "jabodetabek"),
    ("Kab. Bogor", "jabodetabek"), ("Bekasi", "jabodetabek"),
    ("Kota Surabaya", "jawa_lain"), ("Kab. Sleman", "jawa_lain"),
    ("Kota Denpasar", "luar_jawa"), (None, "tidak_diketahui"), ("", "tidak_diketahui"),
])
def test_region(kota, hasil):
    assert region(kota) == hasil
```

- [ ] **Step 3: Jalankan, pastikan gagal**

Run: `.venv\Scripts\python -m pytest tests/test_parser.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'transform.parser'`.

- [ ] **Step 4: Tulis `transform/parser.py`**

- `berat_gram` (spec 5.2, diperbarui 7 Nov):
  1. Kata bilangan dulu: `sekilo` → 1000, `setengah kilo` → 500.
  2. Per kilo: `/kg`, `/ kg`, `per kg`, `kiloan` → 1000.
  3. Cari **semua** berat di seluruh teks dengan satuan
     `(kg|kilogram|kilo|gram|grm|gr|g|ons)` (`re.I`, satuan sebagai kata
     utuh). Angka: pecahan `a/b`, rentang `a - b` (titik tengah),
     desimal (`,` atau `.` + 1–2 angka), ribuan (`.` + tepat 3 angka).
     `kg`/`kilo`/`kilogram` ×1000, `ons` ×100.
  4. Semua berat yang ketemu sama → itu hasilnya. Satu berat tunggal
     yang jatuh **di dalam** rentang lain → berat tunggal itu. Selain itu
     berbeda → `None`.
  5. Di luar 100–20.000 g → `None`. Hasil dibulatkan ke `int`.
- `berat_dari_slug`: ambil slug, buang ID angka panjang di ujung
  (`(-\d{15,})+$`), ganti `-` jadi spasi; slug ambigu → `None`; selain
  itu `berat_gram(slug)`.
- `pilih_berat`: kembalikan `(berat_gram(teks), sumber)` pertama yang
  bukan `None`.
- `jumlah_buah` + `jenis_satuan`: lihat Interfaces dan spec 5.2.
- `jenis_buah`: kamus urut, kata kunci huruf kecil yang dicari di
  `nama.lower()`, dan yang pertama cocok menang. Isinya:
  mangga; apel; pisang; jeruk; anggur; melon; semangka; alpukat/avocad;
  pepaya; buah naga/dragon fruit/dragon; pir/pear (sebagai kata utuh);
  kiwi; salak; manggis; durian; lengkeng/kelengkeng; nanas; stroberi/
  strawberry; jambu; sisanya `lainnya`. "pir" harus kata utuh, supaya
  "vampir" tidak cocok.
- `olahan`: `POLA_OLAHAN` dari `bersihkan_blibli.py`.
- `asal_dari_nama`: urutan aturannya:
  1. kata `impor`/`import` → `impor`;
  2. kata `lokal` → `lokal`;
  3. varietas impor (`kiwi`, `fuji`, `red globe`, `sunkist`, `pear`/`pir`,
     `washington`, `envy`, `ponkam`, `shine muscat`, `crimson`) → `impor`;
  4. varietas lokal (`salak`, `manggis`, `arumanis`/`harumanis`,
     `manalagi`, `medan`, `pontianak`, `kepok`, `ambon`, `rambutan`,
     `duku`) → `lokal`;
  5. selain itu `tidak_diketahui`.
- `terjual_dari_label`: regex `(\d+(?:,\d+)?)\s*(rb)?\+?\s*terjual`.
  Koma berarti desimal. `rb` dikali 1000. Tidak cocok → `None`.
- `ember_terjual`: kalau `n < 30` hasilnya `n`. Kalau `n < 100`,
  dibulatkan ke bawah per 10. Kalau `n < 1000`, ambil yang terbesar dari
  {100, 250, 500, 750} yang `≤ n`. Kalau `n ≥ 1000`, dibulatkan ke bawah
  per 1000.
- `region`: hilangkan awalan `Kota `/`Kab. `, lalu cocokkan dengan
  himpunan `JABODETABEK` = {Jakarta Pusat/Barat/Timur/Selatan/Utara,
  Bogor, Depok, Tangerang, Tangerang Selatan, Bekasi} dan `JAWA_LAIN`
  (kota/kabupaten di Banten, Jawa Barat, Jawa Tengah, DIY, dan Jawa Timur
  di luar Jabodetabek; minimal Surabaya, Malang, Semarang, Bandung,
  Yogyakarta, Sleman, Bantul, Solo/Surakarta, Kendal, Kediri, Sidoarjo,
  Cirebon, Serang, Cilegon). Tidak kosong tapi tidak cocok → `luar_jawa`.
  Kosong atau `None` → `tidak_diketahui`.

- [ ] **Step 5: Jalankan, pastikan lulus**

Run: `.venv\Scripts\python -m pytest tests/test_parser.py -q`
Expected: semua lulus.

- [ ] **Step 6: Usulan commit untuk pengguna**

`feat: kerangka proyek dan parser bersama`

---

### Task 2: Alat HTTP bersama + penarik Blibli

**Files:**
- Create: `extract/http.py`, `extract/blibli.py`
- Test: `tests/test_http.py`, `tests/test_extract_blibli.py`

**Interfaces:**
- Produces (`extract/http.py`):
  - `class KesalahanSementara(Exception)`: dilempar pemanggil untuk galat
    jaringan, `429`, atau `5xx`. Inilah yang memicu coba ulang.
  - `class AmbilGagal(Exception)`: dilempar setelah 3 kali coba gagal.
  - `ambil_dengan_coba_ulang(fungsi: Callable[[], T], *, tidur: Callable[[float], None] = time.sleep) -> T`.
    Total 4 percobaan (1 + 3 ulang), jeda 2, 4, 8 detik. Hanya
    `KesalahanSementara` yang diulang; galat lain langsung diteruskan.
  - `jeda_sopan(tidur=time.sleep, acak=random.uniform) -> None`: tidur
    `acak(1.5, 3.0)` detik.
  - `siapkan_folder(akar: Path, sumber: str, tanggal: date) -> Path`:
    menghasilkan `akar/"raw"/sumber/f"date={tanggal:%Y-%m-%d}"`. Kalau
    sudah ada, isinya dihapus dulu, lalu folder dibuat.
  - `simpan_json(folder: Path, nama_berkas: str, isi: object) -> Path`:
    UTF-8, `ensure_ascii=False`.
  - `@dataclass class HasilTarik: halaman: int; status: str; pesan: str | None = None`.
    `status` ∈ {`"berhasil"`, `"sebagian"`, `"gagal"`}.
- Produces (`extract/blibli.py`):
  - `KATEGORI: dict[str, str] = {"BU-1000190": "lokal", "BU-1000191": "impor"}`
  - `class HalamanHabis(Exception)`: `ambil_halaman_http` melemparnya
    untuk HTTP 422.
  - `ambil_halaman_http(kategori: str, halaman: int) -> dict`: `urllib`
    dengan header `KEPALA` (disalin dari `tarik_blibli.py`) plus
    `Referer`. HTTP 422 → `HalamanHabis`. 429/5xx/`URLError`/timeout →
    `KesalahanSementara`.
  - `tarik(tanggal: date, akar: Path, ambil_halaman: Callable[[str, int], dict] = ambil_halaman_http, tidur=time.sleep) -> HasilTarik`

Berkas mentah Blibli bernama `<kategori>_page_NNN.json`, misalnya
`BU-1000190_page_001.json`. **Ruling:** spec menulis `page_NNN.json`, tapi
Blibli ditarik dari dua kategori, jadi nama kategori jadi awalan supaya
berkasnya tidak saling timpa.

- [ ] **Step 1: Tulis tes yang gagal**

`tests/test_http.py`:
- `test_coba_ulang_sampai_berhasil`: fungsi palsu melempar
  `KesalahanSementara` 2 kali lalu mengembalikan `"ok"`. Hasilnya
  `"ok"`, dan `tidur` dipanggil dengan `[2, 4]`.
- `test_menyerah_setelah_tiga_kali_ulang`: selalu melempar. Hasilnya
  `AmbilGagal`, dan `tidur` dipanggil dengan `[2, 4, 8]`.
- `test_galat_lain_tidak_diulang`: `ValueError` diteruskan langsung, dan
  `tidur` tidak dipanggil.
- `test_siapkan_folder_mengosongkan_isi_lama`: berkas lama di folder
  tanggal itu hilang setelah dipanggil.

`tests/test_extract_blibli.py` memakai `ambil_halaman` palsu yang
mengembalikan `{"data": {"products": [...], "paging": {"total_page": T}}}`
dan `tidur=lambda s: None`:
- `test_menarik_semua_halaman_kedua_kategori`: `T=2` untuk kedua
  kategori. Hasilnya 4 berkas, `status == "berhasil"`, `halaman == 4`.
- `test_422_setelah_halaman_terakhir_berarti_selesai`: palsu
  mengembalikan `total_page=25`, tapi halaman 21 melempar `HalamanHabis`.
  Hasilnya `status == "berhasil"`, 20 berkas per kategori.
- `test_halaman_pertama_gagal_berarti_gagal`: halaman 1 kategori pertama
  `AmbilGagal`. Hasilnya `status == "gagal"`.
- `test_gagal_di_tengah_berarti_sebagian`: kategori kedua gagal di
  halaman 2. Hasilnya `status == "sebagian"`, dan berkas yang sudah
  tersimpan tetap ada.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `.venv\Scripts\python -m pytest tests/test_http.py tests/test_extract_blibli.py -q`
Expected: FAIL, modul belum ada.

- [ ] **Step 3: Tulis `extract/http.py` dan `extract/blibli.py`**

Alur `tarik`:
1. `siapkan_folder(akar, "blibli", tanggal)`.
2. Untuk setiap kategori di `KATEGORI`, halaman 1 sampai
   `min(total_page, 20)`. Setiap halaman diambil lewat
   `ambil_dengan_coba_ulang(lambda: ambil_halaman(kat, n))`.
3. Berhenti di kategori itu kalau dapat `HalamanHabis` atau `products`
   kosong. Ini bukan galat.
4. `jeda_sopan(tidur)` antar-halaman.
5. `AmbilGagal` di halaman 1 kategori pertama → `gagal`. Di tempat lain
   → `sebagian` dan berhenti total.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: perintah Step 2.
Expected: semua lulus.

- [ ] **Step 5: Usulan commit**

`feat: alat HTTP bersama dan penarik kategori Blibli`

---

### Task 3: Penarik Tokopedia

**Files:**
- Create: `extract/tokopedia.py`
- Test: `tests/test_extract_tokopedia.py`

**Interfaces:**
- Consumes: semua dari `extract/http.py` (Task 2).
- Produces (`extract/tokopedia.py`):
  - `URL = "https://gql.tokopedia.com/graphql/SearchProductV5Query"`
  - `PARAM_DASAR = {"source": "directory", "identifier": "makanan-minuman_buah_buah-buahan", "sc": 2705, "q": "", "rows": 60, "ob": 23, "device": "desktop", "st": "product", "safe_search": "false", "user_id": 0, "related": "true"}`
  - `HALAMAN_MAKS = 100`
  - `buat_sesi() -> curl_cffi.requests.Session`: `impersonate="chrome"`,
    lalu `GET https://www.tokopedia.com/` untuk cookie.
  - `ambil_halaman_http(sesi, halaman: int) -> list`: POST dengan header
    (`Content-Type: application/json`,
    `Origin`, `Referer: https://www.tokopedia.com/p/makanan-minuman/buah/buah-buahan`,
    `X-Source: tokopedia-lite`, `X-Tkpd-Lite-Service: zeus`,
    `X-Device: desktop-0.0`). Badan berupa list satu objek dengan
    `operationName`, `variables.params` (urlencode dari `PARAM_DASAR` +
    `page` + `start=(halaman-1)*60`), dan `query`. Query memilih kolom
    yang dibaca Task 5: `id name url price{number original discountPercentage}
    shop{id name city tier} category{breadcrumb} rating labelGroups{position title}`
    plus `header{totalData}`. Timeout atau 429/5xx →
    `KesalahanSementara`. Kalau jawabannya punya `errors`, lempar
    `RuntimeError` berisi pesan GraphQL-nya.
  - `produk_dari_jawaban(jawaban: list) -> list[dict]`: mengambil
    `[0]["data"]["searchProductV5"]["data"]["products"]`.
  - `tarik(tanggal: date, akar: Path, ambil_halaman: Callable[[int], list] | None = None, tidur=time.sleep) -> HasilTarik`.
    Kalau `ambil_halaman` None, buat sesi lalu pakai
    `ambil_halaman_http`.

Berkas mentah: `page_NNN.json`, berisi jawaban utuh.

- [ ] **Step 1: Tulis tes yang gagal**

`ambil_halaman` palsu mengembalikan
`[{"data": {"searchProductV5": {"data": {"products": [...]}}}}]`.

- `test_berhenti_di_halaman_kosong`: halaman 1–3 berisi, halaman 4
  kosong. Hasilnya 3 berkas, `status == "berhasil"`, `halaman == 3`.
- `test_berhenti_di_halaman_100`: selalu berisi. Hasilnya 100 berkas.
- `test_halaman_pertama_gagal_berarti_gagal` dan
  `test_gagal_di_tengah_berarti_sebagian`: sama seperti Task 2.
- `test_produk_dari_jawaban`: mengambil list produk dari bentuk di atas.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `.venv\Scripts\python -m pytest tests/test_extract_tokopedia.py -q`
Expected: FAIL, modul belum ada.

- [ ] **Step 3: Tulis `extract/tokopedia.py`** sesuai Interfaces.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: perintah Step 2. Expected: lulus.

- [ ] **Step 5: Uji sungguhan sekali (butuh internet, bukan bagian pytest)**

Run: `.venv\Scripts\python -c "from extract.tokopedia import *; s=buat_sesi(); print(len(produk_dari_jawaban(ambil_halaman_http(s,1))))"`
Expected: `60`. Kalau galat, berhenti dan laporkan; jangan lanjut ke
Task 5 dengan data tebakan.

- [ ] **Step 6: Usulan commit**

`feat: penarik kategori buah Tokopedia`

---

### Task 4: Fixture uji + transform Blibli (lapisan 1)

**Files:**
- Create: `tests/fixtures/blibli/date=<tanggal varian pertama>/` (dua
  halaman + `varian/`), `tests/fixtures/blibli/date=2026-11-07/` (tanpa
  varian), `transform/blibli.py`
- Test: `tests/test_transform_blibli.py`

> **Diperbarui 7–8 November:** 29 kolom sumber (`sku` disimpan 8 Nov) + 3 turunan, satu baris per
> opsi (`item_sku`), baris opsi lain dari `varian/is--*.json` (spec 5.1).

**Interfaces:**
- Consumes: `pilih_berat`, `jenis_satuan` (Task 1).
- Produces (`transform/blibli.py`):
  - `KOLOM_BLIBLI: dict[str, pl.DataType]`, urut sesuai tabel spec 5.1
    (kolom 1–29), lalu `berat_gram` Int64, `sumber_berat` Utf8,
    `jenis_satuan` Utf8, `jumlah_buah` Int64, `berat_dikali` Boolean. Tipe: `tanggal` Date; `opsi_default`, `resmi`
    Boolean; `harga`, `harga_coret`, `diskon_persen`, `harga_voucher`,
    `harga_coret_voucher`, `diskon_voucher_persen`,
    `harga_sebelum_kampanye`, `jumlah_ulasan`, `total_terjual`,
    `terjual_bulan_ini_min` Int64; `rating`, `rating_toko` Float64;
    sisanya Utf8.
  - `angka_rupiah(teks: str | None) -> int | None`: "Rp39.100" → 39100,
    `None`/"" → `None`.
  - `ubah(folder: Path, tanggal: date) -> pl.DataFrame`:
    1. Baca semua `*_page_*.json` → baris default (`opsi_default=True`).
       `kategori_tarik` dari awalan nama berkas.
    2. Kalau `folder/varian/` ada: untuk setiap `is--*.json`, buat baris
       opsi (`opsi_default=False`) dengan pemetaan kolom kanan spec 5.1;
       kolom "salin" diambil dari baris default `produk_id` yang sama.
       `is--` tanpa baris default (produk hilang dari hasil cari) →
       dilewati.
    3. Berat: Blibli `satuan_baris(nama, variant, banyak_opsi=hasVariants,
       usp=uniqueSellingPoint)` → `berat_gram`, `sumber_berat`, `jenis_satuan`,
       `jumlah_buah`, `berat_dikali` (A1, 8 Nov: produk beberapa opsi hanya
       membaca `variant`).
    4. Buang ganda per (`item_sku`), yang pertama dipertahankan.

**Wajib ada:** `id`, `name`, `price`, `itemSku` di kartu; `data.itemSku`,
`data.price` di berkas `is--`. Hilang → `ValueError` yang menyebut nama
kolom dan nama berkasnya. Kolom lain boleh tidak ada (jadi NULL).

- [ ] **Step 1: Buat fixture dari data asli**

Fixture **dengan** varian: dari tarikan sungguhan tanggal pertama yang
punya `varian/` (8 November atau sesudahnya), di
`tests/fixtures/blibli/date=<tanggal>/`:
- satu `BU-1000190_page_001.json` dan satu `BU-1000191_page_001.json`
  masing-masing 15 produk, termasuk **Apel Fuji Super Fresh
  `NAS-70965-00407`** (500 gr default + 1 kg) dan **Mangga Manalagi
  `DOD-70072-00076`** (1/2 kg + 1 kg) kalau ada di tanggal itu;
- folder `varian/` berisi `ps--`/`is--` milik produk bervarian di
  fixture saja;
- satu produk ganda di dua berkas; satu produk dengan `location: null`.

Fixture **tanpa** varian: 10 produk dari `date=2026-11-06` (7 Nov ternyata
sudah punya `varian/` dari uji tarik).

- [ ] **Step 2: Tulis tes yang gagal**

- `test_kolom_dan_tipe_tepat`: `df.schema == KOLOM_BLIBLI`.
- `test_satu_baris_per_opsi`: `NAS-70965-00407` punya 2 baris; baris
  `…-00002` punya `harga 84900`, `harga_coret 90000`, `diskon_persen 6`,
  `variant "1 kg"`, `opsi_default False`.
- `test_opsi_lain_menyalin_kolom_produk`: `penjual`, `kategori`,
  `rating_toko` baris opsi = baris default.
- `test_opsi_lain_kolom_kartu_null`: `harga_voucher`, `kampanye`,
  `terjual_bulan_ini_min` NULL di baris opsi lain.
- `test_tanpa_folder_varian_hanya_baris_default`.
- `test_rating_null_kalau_tanpa_ulasan`: `review.count = 0` → `rating`
  NULL.
- `test_angka_rupiah`: "Rp39.100" → 39100, "" → None.
- `test_berat_variant_menang`: `NAS-70965-00407-00001` →
  `berat_gram 500`, `sumber_berat "variant"`.
- `test_kategori_tarik_dari_nama_berkas`.
- `test_baris_ganda_dibuang`: `item_sku` unik.
- `test_kolom_hilang_gagal_jelas`: produk tanpa `price` →
  `pytest.raises(ValueError, match="price")`.

- [ ] **Step 3: Jalankan, pastikan gagal**

Run: `.venv\Scripts\python -m pytest tests/test_transform_blibli.py -q`
Expected: FAIL, modul belum ada.

- [ ] **Step 4: Tulis `transform/blibli.py`**

Bangun list dict (baris default, lalu baris opsi lain) dengan pemetaan
spec 5.1, lalu `pl.DataFrame(baris, schema=KOLOM_BLIBLI)`, lalu
`.unique("item_sku", keep="first", maintain_order=True)`.

- [ ] **Step 5: Jalankan, pastikan lulus.** Expected: lulus.

- [ ] **Step 6: Usulan commit**

`feat: transform Blibli ke tabel lapisan 1`

---

### Task 5: Transform Tokopedia (lapisan 1)

**Files:**
- Create: `tests/fixtures/tokopedia/date=2026-10-13/page_001.json`,
  `tests/fixtures/tokopedia/date=2026-10-13/page_002.json`,
  `transform/tokopedia.py`
- Test: `tests/test_transform_tokopedia.py`

**Interfaces:**
- Consumes: `extract.tokopedia.produk_dari_jawaban`,
  `transform.parser.terjual_dari_label` (tidak dipanggil di sini;
  lapisan 1 menyimpan labelnya apa adanya).
- Produces (`transform/tokopedia.py`):
  - `KOLOM_TOKOPEDIA: dict[str, pl.DataType]`, urut: `tanggal` Date,
    `produk_id` Utf8, `nama` Utf8, `harga` Int64, `harga_asli` Int64,
    `diskon_persen` Int64, `toko_id` Utf8, `nama_toko` Utf8, `kota` Utf8,
    `tier_toko` Int64, `rating` Float64, `terjual_label` Utf8,
    `kategori` Utf8, `url` Utf8.
  - `ubah(folder: Path, tanggal: date) -> pl.DataFrame`, dengan sifat
    yang sama seperti Task 4.

> **Diperbarui 7 November:** tambah kolom turunan `berat_gram`,
> `sumber_berat`, `jenis_satuan` (berat: `pilih_berat([("nama", nama),
> ("url", slug)])`, slug lewat `berat_dari_slug`). Tiga hal **menunggu
> keputusan pengguna** (spec 13 #1–3): arti `harga_asli`, cara mengisi
> `diskon_persen`, dan salinan laptop vs VPS.
>
> **Diputuskan 8 Nov:** `harga_asli` disimpan, tidak dipakai di fakta;
> `diskon_persen` selalu NULL; **hanya salinan laptop**
> (`data_lake/raw/tokopedia/`), `data_lake_vps/` diabaikan. `ubah()`
> hanya membaca satu folder yang diberikan.

Pemetaan kolom:
- `harga` ← `price.number`
- `harga_asli` ← angka dari `price.original` ("Rp29.500" → 29500; ""
  → NULL)
- `diskon_persen` ← `price.discountPercentage` (selalu 0 di data asli;
  spec 13 #2)
- `rating` ← `float(rating)`, atau NULL kalau `""`
- `terjual_label` ← `title` dari label `ri_product_credibility`, atau NULL
- `kategori` ← `category.breadcrumb`
- `url` ← `url` tanpa query string (potong di `?`)

**Wajib ada:** `id`, `name`, `price`, `shop`.

- [ ] **Step 1: Buat fixture**

Sumber: `C:/Users/Abraham/AppData/Local/Temp/claude/c--Users-Abraham-Documents-SMT5-Manpro-kebun-ibu/c222cd77-e972-4989-aad0-aa8c6ee3cae9/scratchpad/tokped_kategori_sample.json`
(420 produk asli, 13 Oktober). Kalau berkas itu sudah tidak ada, tarik
2 halaman sungguhan lewat `extract.tokopedia` (Task 3 Step 5) sebagai
gantinya.

- Ambil 20 produk per berkas.
- Bungkus jadi `[{"data": {"searchProductV5": {"data": {"products": [...]}}}}]`.
- Masukkan setidaknya satu produk dengan `rating == ""` dan satu dengan
  `price.original` berisi harga.
- Buat satu produk muncul di kedua halaman (uji buang ganda).
- Ubah satu produk supaya `shop.city` = `null` (dipakai Task 7).

- [ ] **Step 2: Tulis tes yang gagal**

- `test_kolom_dan_tipe_tepat`
- `test_baris_ganda_dibuang`: `df.height == 39`
- `test_rating_kosong_jadi_null`
- `test_harga_asli_diurai`
- `test_url_tanpa_query`
- `test_label_terjual_diambil_dari_credibility`
- `test_kolom_hilang_gagal_jelas`: produk tanpa `shop` → `ValueError`
  yang menyebut `shop`.

- [ ] **Step 3–5:** jalankan (gagal), tulis kode, jalankan (lulus).

Run: `.venv\Scripts\python -m pytest tests/test_transform_tokopedia.py -q`

- [ ] **Step 6: Usulan commit**

`feat: transform Tokopedia ke tabel lapisan 1`

---

### Task 6: Skema Pandera + pemisahan karantina

**Files:**
- Create: `transform/skema.py`
- Test: `tests/test_skema.py`

**Interfaces:**
- Consumes: `KOLOM_BLIBLI`, `KOLOM_TOKOPEDIA` (Task 4, 5).
- Produces (`transform/skema.py`):
  - `SkemaBlibli`, `SkemaTokopedia`, `SkemaFakta`, `SkemaDimProduk`,
    `SkemaDimToko`: `pandera.polars.DataFrameModel`, dengan cek dari spec
    bagian 6:
    - `produk_id`/`nama`/`tanggal` tidak kosong;
    - `harga > 0`;
    - `rating` 0–5 atau NULL;
    - `diskon_persen` 0–100 atau NULL;
    - di fakta, `harga_per_kg` 3.000–500.000 atau NULL;
    - `sumber` ∈ {blibli, tokopedia};
    - `produk_key` unik di `SkemaDimProduk`, `toko_key` unik di
      `SkemaDimToko`.
  - `KOLOM_KARANTINA = {"sumber": Utf8, "tanggal": Date, "produk_id": Utf8, "data": Utf8, "alasan": Utf8}`
  - `pisahkan(df: pl.DataFrame, skema: type[pa.DataFrameModel], sumber: str) -> tuple[pl.DataFrame, pl.DataFrame]`.
    Hasilnya `(lolos, karantina)`.
    - Validasi `lazy=True`. Nomor baris yang gagal diambil dari
      `SchemaErrors.failure_cases["index"]`.
    - `alasan` = gabungan unik `"<column>: <check>"` per baris, dipisah
      `"; "`.
    - `data` = baris asli sebagai JSON.
    - Kegagalan tingkat skema (kolom hilang, tipe salah, `index` NULL)
      **tidak** dikarantina. Lempar ulang `SchemaErrors`, karena itu
      tanda kode atau bentuk data berubah.

Cek keterkaitan "setiap kunci fakta ada di dimensinya" **tidak** ada di
skema ini. Itu diuji di Task 7.

**Diperbarui 7 November:**
- `SkemaBlibli` unik per (`item_sku`, `tanggal`), bukan `produk_id`.
- `SkemaBlibli` mendapat cek perbandingan A, B, D, E, F, G (spec 6.1),
  sebagai cek tingkat baris (`pa.Check` atas beberapa kolom) supaya
  baris yang gagal punya `index` dan ikut dikarantina. Nama cek dipakai
  di `alasan`: `cek_A_harga_urut`, `cek_B_diskon`, `cek_D_coret_voucher`,
  `cek_E_diskon_voucher`, `cek_F_kampanye`, `cek_G_sku_sama_id`. Kolom yang NULL membuat cek
  itu dilewati untuk baris tersebut.
- Cek C (opsi default berubah) **bukan** di sini; jadi view
  `v_opsi_berubah` di Task 8.
- **Harga kosong (8 Nov, keputusan B):** baris dengan `harga` NULL (opsi
  Blibli yang tidak tersedia, ±43/hari) gagal skema → karantina dengan
  `alasan` yang menyebut `harga`. Tes: `test_harga_null_dikarantina`.
- **Cek H (8 Nov):** baris dengan `berat_dikali = true` **disalin** ke
  karantina dengan `alasan = "cek_H_berat_dikali"` tetapi **tetap lolos** ke
  fakta. Berlaku untuk Blibli dan Tokopedia. Bukan `pa.Check` (yang
  membuang baris), tetapi langkah terpisah di `pisahkan()`.

Tes tambahan:
- `test_cek_A_voucher_lebih_mahal_dikarantina`: `harga_voucher = harga + 1`.
- `test_cek_B_diskon_tidak_cocok_dikarantina`: `diskon_persen` +5.
- `test_cek_D_coret_voucher_beda_dikarantina`.
- `test_cek_E_diskon_voucher_tidak_cocok_dikarantina`.
- `test_cek_F_harga_turun_tanpa_kampanye_dikarantina`: salin kasus asli
  `FRX-60021-01718` (sebelum kampanye 15000, harga 10000, `kampanye`
  NULL).
- `test_cek_G_sku_beda_dari_id_dikarantina`: `sku = produk_id + "X"`.
- `test_cek_H_berat_dikali_dicatat_tetapi_tetap_lolos`: satu baris
  "8x125GR" ada di karantina **dan** di hasil lolos.
- `test_cek_dilewati_kalau_kolom_null`: baris opsi lain (kolom voucher
  NULL) lolos.

- [ ] **Step 1: Tulis tes yang gagal**

- `test_baris_bagus_lolos_semua`: fixture Blibli lewat `transform.blibli.ubah`
  → karantina kosong.
- `test_harga_negatif_dikarantina`: satu baris diubah `harga = -1`.
  Hasilnya lolos `n-1`, karantina 1, dan `alasan` memuat
  `"harga"` dan `"greater_than"`.
- `test_rating_di_luar_batas_dikarantina`: `rating = 9.0`.
- `test_dua_masalah_satu_baris_satu_entri`: `harga=-1` dan `rating=9`
  di baris yang sama. Hasilnya karantina 1 baris, `alasan` memuat
  keduanya.
- `test_kolom_hilang_tidak_dikarantina_tapi_dilempar`: kolom `harga`
  dihapus → `pytest.raises(pa.errors.SchemaErrors)`.
- `test_data_karantina_bisa_dibaca_ulang`: `json.loads(karantina["data"][0])["harga"] == -1`.

- [ ] **Step 2–4:** jalankan (gagal), tulis kode, jalankan (lulus).

Run: `.venv\Scripts\python -m pytest tests/test_skema.py -q`

- [ ] **Step 5: Usulan commit**

`feat: validasi Pandera dan karantina baris gagal`

---

### Task 7: Star schema (dimensi + fakta)

**Files:**
- Create: `transform/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Consumes: semua fungsi `transform/parser.py` (Task 1), DataFrame
  lapisan 1 yang **sudah lolos** validasi (Task 4–6).
- Produces (`transform/model.py`):
  - `kunci(sumber: str, id_alami: str | None) -> str`: `md5` hex dari
    `f"{sumber}|{id_alami or ''}"`.
  - `@dataclass class Bintang: dim_produk: pl.DataFrame; dim_toko: pl.DataFrame; dim_tanggal: pl.DataFrame; fakta_harga: pl.DataFrame`
  - `bangun(blibli: pl.DataFrame | None, tokopedia: pl.DataFrame | None) -> Bintang`

> **Diperbarui 7 November:** grain fakta = satu **opsi** per produk per
> tanggal. `berat_gram` pindah ke fakta (tiap opsi beratnya sendiri).
> Fakta mendapat `item_sku`, `opsi_default`, `variant`, `sumber_berat`,
> `jenis_satuan`, `harga_per_buah`. Tokopedia: `item_sku = produk_id`,
> `opsi_default = True`, `variant` NULL. Tes `test_jumlah_fakta_sama…`
> tetap berlaku (satu baris lapisan 1 = satu baris fakta).
> Tambah tes `test_harga_per_kg_per_opsi`: `NAS-70965-00407` →
> 92000 (500 gr) dan 84900 (1 kg).

Kolom keluaran:
- `dim_produk`: `produk_key, sumber, produk_id, nama, jenis_buah, asal,
  asal_sumber, olahan`.
- `dim_toko`: `toko_key, sumber, toko_id, nama_toko, kota, region,
  jenis_toko`.
- `dim_tanggal`: `tanggal, tahun, bulan, minggu` (ISO week), `hari`
  (nama hari dalam bahasa Indonesia: Senin…Minggu).
- `fakta_harga`: `tanggal, produk_key, toko_key, sumber, item_sku,
  opsi_default, variant, harga, harga_coret, diskon_persen, berat_gram,
  sumber_berat, jenis_satuan, harga_per_kg, harga_per_buah, rating,
  terjual_min`.

Aturan per sumber:

| Kolom | Blibli | Tokopedia |
|---|---|---|
| `toko_id` | `merchant_code` | `toko_id` |
| `nama_toko` / `kota` | `penjual` / `lokasi` | `nama_toko` / `kota` |
| `asal`, `asal_sumber` | `"lokal"` kalau `kategori` memuat "Buah Lokal" atau `kategori_tarik == "BU-1000190"`; `"impor"` kalau memuat "Buah Impor" atau `kategori_tarik == "BU-1000191"`; `asal_sumber = "label"` | `asal_dari_nama(nama)`, `asal_sumber = "aturan"` |
| `jenis_toko` | `"resmi"` kalau `resmi`, selain itu `"biasa"` | `f"tier_{tier_toko}"` (spec 13.1: belum ditebak) |
| `harga_coret` | `harga_coret` | `harga_asli` |
| `terjual_min` | `ember_terjual(total_terjual)` | `terjual_dari_label(terjual_label)` |

Untuk semua sumber:
- `jenis_buah` dan `olahan` dari parser. `berat_gram`, `sumber_berat`,
  `jenis_satuan` sudah ada di lapisan 1 (Task 4–5).
- `harga_per_kg = round(harga / berat_gram * 1000)` kalau
  `jenis_satuan == "berat"`; `harga_per_buah = round(harga /
  jumlah_buah(nama))` kalau `"jumlah"`; selain itu NULL.
- Dimensi diambil unik per kunci (yang terakhir menang = SCD 1).

**Fakta dibangun dengan menghitung kunci langsung dari kolom ID di
lapisan 1, bukan dengan join ke dimensi.** Itu yang membuat toko tanpa
kota tidak bisa hilang.

- [ ] **Step 1: Tulis tes yang gagal** (memakai fixture Task 4 + 5)

- `test_kunci_stabil`:
  `kunci("tokopedia", "123") == hashlib.md5(b"tokopedia|123").hexdigest()`.
- `test_jumlah_fakta_sama_dengan_baris_lapisan_1`:
  `fakta.height == blibli.height + tokopedia.height`.
- `test_toko_tanpa_kota_tetap_masuk_fakta`: produk dengan `lokasi`/`kota`
  NULL dari fixture ada di fakta, dan toko-nya ada di `dim_toko` dengan
  `region == "tidak_diketahui"`.
- `test_setiap_kunci_fakta_ada_di_dimensi`: anti-join fakta↔dim_produk
  dan fakta↔dim_toko kosong.
- `test_kunci_dimensi_unik`.
- `test_asal_blibli_dari_label`: semua baris Blibli fixture punya
  `asal_sumber == "label"` dan `asal` ∈ {lokal, impor}.
- `test_harga_per_kg_null_kalau_berat_tidak_terbaca`.
- `test_bangun_satu_sumber_saja`: `bangun(blibli, None)` jalan.

- [ ] **Step 2–4:** jalankan (gagal), tulis kode, jalankan (lulus).

Run: `.venv\Scripts\python -m pytest tests/test_model.py -q`

- [ ] **Step 5: Usulan commit**

`feat: bangun star schema dari tabel lapisan 1`

---

### Task 8: Loader DuckDB

**Files:**
- Create: `load/duckdb_loader.py`
- Test: `tests/test_loader.py`

**Interfaces:**
- Consumes: `Bintang` (Task 7), `KOLOM_BLIBLI`, `KOLOM_TOKOPEDIA`,
  `KOLOM_KARANTINA` (Task 4–6).
- Produces (`load/duckdb_loader.py`):
  - `siapkan(con: duckdb.DuckDBPyConnection) -> None`: `CREATE TABLE IF
    NOT EXISTS` untuk `blibli_produk`, `tokopedia_produk`,
    `produk_karantina`, `dim_produk` (PK `produk_key`), `dim_toko`
    (PK `toko_key`), `dim_tanggal` (PK `tanggal`), `fakta_harga`
    (PK `tanggal, produk_key, item_sku`, **diubah 7 Nov**: satu produk
    bisa punya beberapa opsi per tanggal), `pipeline_runs`.
  - **Tambahan 7 Nov:** view `v_opsi_berubah` (cek C, spec 6.1): baris
    `opsi_default = true` yang `item_sku`-nya berbeda dari tanggal
    sebelumnya untuk `produk_id` yang sama
    (`LAG(item_sku) OVER (PARTITION BY sumber, produk_id ORDER BY tanggal)`).
    `CREATE OR REPLACE VIEW v_produk` (fakta join ketiga dimensi, semua
    kolom deskriptif).
  - `muat(con, sumber: str, tanggal: date, lapisan1: pl.DataFrame, karantina: pl.DataFrame, bintang: Bintang) -> None`.
    Satu transaksi:
    1. `DELETE` baris (`tanggal`) di tabel lapisan 1 sumber itu,
       `DELETE` (`sumber`, `tanggal`) di `fakta_harga` dan
       `produk_karantina`.
    2. `INSERT` lapisan 1, karantina, dan fakta.
    3. Dimensi lewat `INSERT ... ON CONFLICT (pk) DO UPDATE SET` semua
       kolom.
    4. Kalau ada galat: `ROLLBACK` lalu lempar ulang.
  - `catat_run(con, run: dict) -> None`: insert satu baris
    `pipeline_runs` (kolom spec bagian 7).

- [ ] **Step 1: Tulis tes yang gagal** (DuckDB `:memory:`, data dari
  Task 4–7 atas fixture)

- `test_siapkan_dua_kali_aman`.
- `test_muat_isi_semua_tabel`: jumlah baris tiap tabel = sumbernya.
- `test_muat_dua_kali_jumlah_sama`: `muat` dipanggil dua kali dengan
  data yang sama → jumlah baris setiap tabel tidak berubah.
- `test_muat_ulang_mengganti_bukan_menambah`: muat ulang dengan satu
  produk dihapus → fakta tanggal itu berkurang satu.
- `test_tanggal_lain_tidak_tersentuh`: muat tanggal A, lalu tanggal B →
  baris tanggal A masih utuh.
- `test_scd1_nama_terbaru_menang`: muat ulang dengan `nama` produk
  diubah → `dim_produk.nama` ikut berubah, jumlah baris tetap.
- `test_galat_di_tengah_dibatalkan`: `bintang.fakta_harga` diberi kolom
  rusak supaya insert fakta gagal → semua tabel kembali ke jumlah
  sebelum `muat`.
- `test_v_produk_satu_baris_per_fakta`.

- [ ] **Step 2–4:** jalankan (gagal), tulis kode, jalankan (lulus).

Run: `.venv\Scripts\python -m pytest tests/test_loader.py -q`

- [ ] **Step 5: Usulan commit**

`feat: loader DuckDB idempoten dengan view v_produk`

---

### Task 9: `run.py` + tes integrasi

**Files:**
- Create: `run.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: semua sebelumnya.
- Produces:
  - `jalankan(sumber: list[str], tanggal: date, tahap: set[str], akar: Path, db: Path, penarik: dict[str, Callable] | None = None) -> list[dict]`.
    Hasilnya satu dict `pipeline_runs` per sumber. `penarik` memetakan
    sumber → fungsi `tarik`, dan tes mengisinya dengan penarik palsu.
  - CLI: `--sumber blibli,tokopedia` (bawaan keduanya),
    `--tanggal YYYY-MM-DD` (bawaan hari ini), `--tahap
    extract,transform,load` (bawaan ketiganya), `--akar data_lake`,
    `--db warehouse/harga_buah.duckdb`.
  - Log ke layar dan `logs/run_<run_id>.log`. `run_id` = UUID4.

Arti angka di `pipeline_runs`:
- `halaman_ditarik` = `HasilTarik.halaman`, atau 0 kalau extract
  dilewati;
- `baris_mentah` = jumlah baris lapisan 1 setelah buang ganda, sebelum
  validasi;
- `baris_dimuat` = baris yang lolos validasi;
- `baris_karantina` = baris yang dikarantina.

Aturan status (spec bagian 9):
- Status extract `gagal` → tidak ada transform/load, run dicatat `gagal`.
- `sebagian` → lanjut, run dicatat `sebagian`.
- Galat di transform/load → `gagal`, dengan `pesan_galat` = `str(galat)`.
- Satu sumber gagal tidak menghentikan sumber lain.

- [ ] **Step 1: Tulis tes yang gagal**

Semua memakai `tmp_path`, dengan fixture disalin ke
`tmp_path/data_lake/raw/...`, tanpa internet.
- `test_transform_load_dari_mentah_yang_ada`: `tahap={"transform","load"}`
  untuk kedua sumber → `pipeline_runs` 2 baris `berhasil`, dan
  `baris_dimuat + baris_karantina == baris_mentah` per sumber.
- `test_jalan_dua_kali_hasil_sama` (spec 10.3).
- `test_extract_gagal_tidak_memuat_apa_pun`: penarik palsu
  mengembalikan `HasilTarik(0, "gagal", "diblokir")` → run `gagal`,
  `fakta_harga` kosong untuk sumber itu.
- `test_satu_sumber_gagal_sumber_lain_jalan`.
- `test_cli_bantuan`: `python run.py --help` keluar dengan kode 0.

- [ ] **Step 2–4:** jalankan (gagal), tulis kode, jalankan (lulus).

Run: `.venv\Scripts\python -m pytest tests/test_pipeline.py -q`

- [ ] **Step 5: Usulan commit**

`feat: run.py merangkai pipeline dan mencatat setiap run`

---

### Task 10: Evaluasi aturan asal + data lama + CI + README

**Files:**
- Create: `evaluasi_asal.py`, `.github/workflows/ci.yml`, `README.md`
- Test: `tests/test_evaluasi_asal.py`

**Interfaces:**
- Consumes: `transform.blibli.ubah`, `transform.parser.asal_dari_nama`.
- Produces:
  - `evaluasi(blibli: pl.DataFrame) -> dict` dengan kunci `n`,
    `tepat`, `ketepatan` (0–1, dihitung hanya dari baris yang aturannya
    **tidak** menjawab `tidak_diketahui`), `cakupan` (porsi baris yang
    terjawab), dan `matriks` (dict label→tebakan→jumlah). Labelnya:
    `lokal` kalau `kategori_tarik == "BU-1000190"`, `impor` kalau
    `"BU-1000191"`.
  - CLI `python evaluasi_asal.py --akar data_lake --tanggal YYYY-MM-DD`:
    mencetak keempat angka. Ketepatan di bawah **0,90** (spec 13.3)
    dicetak dengan peringatan bahwa asal Tokopedia harus dianggap
    `tidak_diketahui` di analisis.

- [ ] **Step 1: Tulis tes yang gagal**

- `test_evaluasi_pada_fixture`: `0 <= ketepatan <= 1`,
  `n == blibli.height`, dan jumlah isi matriks == `n`.
- `test_aturan_sempurna_bernilai_satu`: DataFrame buatan yang nama
  produknya memuat "impor"/"lokal" sesuai labelnya → `ketepatan == 1.0`.

- [ ] **Step 2–4:** jalankan (gagal), tulis kode, jalankan (lulus).

Run: `.venv\Scripts\python -m pytest tests/test_evaluasi_asal.py -q`

- [ ] **Step 5: Pindahkan data lama**

Bungkus `kebun-ibu/data-mentah/blibli_kategori_mentah.json` per kategori
ke `data_lake/raw/blibli/date=2026-09-27/`:
- produk dengan "Buah Lokal" di jenjang kategori → `BU-1000190_page_001.json`;
- "Buah Impor" → `BU-1000191_page_001.json`;
- sisanya tidak ikut, karena di luar dua kategori yang ditarik.

Format bungkusnya sama dengan fixture Task 4. Pindahkan
`kebun-ibu/skrip/` dan `kebun-ibu/data-mentah/` ke `data-science/arsip/`.
Ini memindahkan, bukan menghapus, dan keduanya belum pernah di-commit.
Tambahkan `arsip/*.json`, `arsip/*.csv`, `arsip/*.pdf`, `arsip/*.html`,
`arsip/*.js`, dan `arsip/*.bin` ke `data-science/.gitignore` (sekitar
11 MB data, terlalu besar untuk git).

- [ ] **Step 6: CI dan Vercel**

1. Buat `kebun-ibu/.github/workflows/data-science.yml`:
   - `on: push` dan `pull_request` ke `main`, dengan
     `paths: ["data-science/**"]`;
   - `defaults.run.working-directory: data-science`;
   - Python 3.11, `pip install -r requirements.txt`, lalu
     `python -m pytest -q`;
   - tanpa langkah yang butuh internet.
2. Di `kebun-ibu/vercel.json`, tambahkan
   `"ignoreCommand": "git diff HEAD^ HEAD --quiet -- . ':(exclude)data-science'"`.
   Exit 0 (tidak ada perubahan di luar `data-science/`) berarti Vercel
   melewati build.
   - **Uji dulu di lokal:** buat commit percobaan yang hanya mengubah
     `data-science/`, lalu jalankan perintahnya. Exit code harus `0`.
     Ulangi dengan commit yang mengubah `src/`; exit code harus `1`.
     Laporkan kedua hasilnya.
   - Build yang dilewati tetap dihitung kuota deploy Vercel.
   - Pengguna yang mendorong perubahan ini, karena memengaruhi deploy
     situs produksi.

- [ ] **Step 7: Tulis `README.md`**

- Tujuan proyek.
- Diagram ETL (spec bagian 3).
- Diagram star schema (spec 5.3).
- Cara menjalankan (spec bagian 8).
- Daftar tabel.
- Batasan jujur dari `rencana-data-science.md` bagian 8.
- Catatan bahwa folder ini bagian dari repo kebun-ibu, tapi berdiri
  sendiri (venv, tes, dan CI terpisah dari situs).

- [ ] **Step 8: Jalankan seluruh tes**

Run: `.venv\Scripts\python -m pytest -q`
Expected: semua lulus, tanpa akses internet.

- [ ] **Step 9: Usulan commit**

`feat: evaluasi aturan asal, data lama, CI, dan README`

---

### Task 11: Run sungguhan pertama (verifikasi, bukan kode)

- [ ] **Step 1: Tarik dan muat kedua sumber**

Run: `.venv\Scripts\python run.py`
Expected: dua baris `pipeline_runs`. Blibli sekitar 1.600 produk mentah
(2 kategori × 20 halaman × 40). Tokopedia sekitar 6.000 (100 halaman ×
60). Status `berhasil` atau `sebagian`.

- [ ] **Step 2: Muat data lama 27 September**

Run: `.venv\Scripts\python run.py --sumber blibli --tanggal 2026-09-27 --tahap transform,load`
Expected: `berhasil`.

- [ ] **Step 3: Periksa hasilnya**

Run: `.venv\Scripts\python -c "import duckdb; c=duckdb.connect('warehouse/harga_buah.duckdb'); print(c.sql('select sumber, tanggal, count(*), count(harga_per_kg) from fakta_harga group by all order by all')); print(c.sql('select * from pipeline_runs')); print(c.sql('select alasan, count(*) from produk_karantina group by all'))"`

Expected:
- tiga kelompok (`sumber`, `tanggal`);
- sekitar 60% baris punya `harga_per_kg`;
- isi karantina masuk akal untuk dibaca.

- [ ] **Step 4: Jalankan evaluasi asal**

Run: `.venv\Scripts\python evaluasi_asal.py --akar data_lake --tanggal <tanggal hari ini>`

Catat ketepatan dan cakupannya untuk laporan.

- [ ] **Step 5: Laporkan ke pengguna**

Laporkan:
- jumlah baris per tabel;
- jumlah karantina beserta alasannya;
- ketepatan aturan asal;
- apa pun yang ganjil.
