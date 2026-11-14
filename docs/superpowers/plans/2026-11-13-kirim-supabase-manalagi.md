# Kirim Data Dashboard Manalagi ke Supabase — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Setiap hari, sesudah `run.py`, laptop menghitung baris dashboard Mangga Manalagi dari
gudang DuckDB dan mengirim **hanya tanggal yang berubah** ke dua tabel Supabase yang hanya bisa
dibaca pengelola.

**Architecture:** `dashboard_manalagi.py` memegang satu-satunya salinan SQL hitungan (dipakai
notebook dan skrip kirim). `kirim_supabase.py` membandingkan hasil hitungan dengan salinan lokal
"yang terakhir terkirim" (Parquet), lalu mengganti tanggal yang berbeda lewat satu fungsi Postgres
(`ganti_pasar_manalagi`, satu transaksi per kelompok tanggal) dengan kunci service role.
Salinan lokal hanya diperbarui sesudah kiriman berhasil.

**Tech Stack:** Python 3.11, duckdb ≥ 1.1, polars ≥ 1.0, curl_cffi ≥ 0.7 (sudah ada; tanpa
dependensi baru), pytest; Supabase Postgres + PostgREST, pgTAP (`npx supabase test db`).

**Spec:** `docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md` (bagian "Jalur data",
"Hitungan dalam SQL", "Tabel Supabase"). Prototipe SQL: `data-science/dashboard_contoh.ipynb`,
sel "Sumber data Langkah 1a" (`SUMBER_SQL`), "Langkah 1a", "Langkah 1b".

## Global Constraints

- Path relatif terhadap `data-science/`, kecuali yang diawali `kebun-ibu/` (akar repo).
- Tes Python: `.venv\Scripts\python -m pytest` dari `data-science/`. Sekarang 346 lulus; tidak boleh ada yang merah.
- Tes database: `npx supabase test db` dari `kebun-ibu/` (Docker Desktop harus jalan; lihat jebakan port WinNAT di memori `local-supabase-testing`).
- **Pengguna yang commit.** Langkah "Commit" = beri pengguna perintah `git add`/`git commit`; jangan commit sendiri.
- Gudang dibuka `read_only=True` dan langsung ditutup (`with duckdb.connect(...)`), supaya muat terjadwal 06:00/12:00 tidak terhalang.
- Kunci service role hanya di laptop: dibaca dari env var atau `kebun-ibu/.env.local` (sudah di `.gitignore`), **tidak pernah ditulis ke log**. Kuncinya JWT lama (`eyJ…`): dikirim di header `apikey` dan `Authorization: Bearer`.
- `kebun-ibu/.env.local` menunjuk ke Supabase **produksi**. Uji coba ujung-ke-ujung pertama ke Supabase lokal dengan env var `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (env var mengalahkan berkas).
- Parameter (dari spec, nilai persis): `JENDELA_HARI = 7`, `AMBANG_TOKO = 0.10`, `AMBANG_PASAR = 0.05`, `MIN_DATA = 3`, `MAKS_JEDA_HARI = 30`; mulai = `MULAI_GUDANG` di `run.py` (Blibli 2026-11-07, Tokopedia 2026-11-08).
- Kolom yang dikirim **persis** daftar "Tabel Supabase (disetujui 13 Nov)" di spec; kolom langkah antara tetap di laptop.
- Nama, komentar, dan pesan log dalam bahasa Indonesia, mengikuti gaya `sinkron_vps.py`.

## Review Focus

1. **Gudang mengembalikan 0 baris Manalagi** (gudang baru/kosong, filter rusak) padahal salinan terkirim ada → semua tanggal akan terlihat "berubah" dan Supabase dikosongkan. Harus berhenti dengan galat, tidak mengirim apa pun. Tes: Task 5 `test_jalankan_menolak_hasil_kosong`.
2. **Jalan ulang tanpa data baru** (12:00 sesudah 06:00) → 0 tanggal dikirim; hitungan float harus identik bit-per-bit dari hari ke hari. Tes: Task 4 `test_hitungan_sama_tidak_ada_yang_berubah`.
3. **Kiriman putus di tengah** (kelompok 2 dari 3 gagal) → salinan terkirim hanya memuat kelompok 1; jalan berikutnya mengirim sisanya. Tes: Task 5 `test_gagal_di_tengah_salinan_hanya_kelompok_yang_berhasil`.
4. **Tanggal hilang dari gudang** (misalnya MULAI diubah) → baris tanggal itu dihapus di Supabase, bukan dibiarkan. Tes: Task 4 `test_tanggal_yang_hilang_ikut_berubah`, Task 1 pgTAP "kirim kosong menghapus tanggal".
5. **Supabase dikosongkan/di-reset tetapi salinan lokal masih ada** → tidak ada yang terkirim ulang tanpa campur tangan. Jalan keluar: `--semua` mengabaikan salinan. Tes: Task 5 `test_semua_mengirim_semua_tanggal`.

---

### Task 1: Migrasi Supabase — dua tabel, RLS pengelola, fungsi ganti

**Files:**
- Create: `kebun-ibu/supabase/migrations/20261113000000_pasar_manalagi.sql`
- Test: `kebun-ibu/supabase/tests/pasar_manalagi.test.sql`

**Interfaces:**
- Produces:
  - `public.pasar_manalagi` (PK `tanggal, produk_key`): `tanggal date not null`, `sumber text not null check (sumber in ('blibli','tokopedia'))`, `produk_key text not null`, `nama_toko text`, `kota text`, `harga_per_kg bigint not null`, `terjual_min bigint`, `median_jendela double precision`, `rasio_jendela double precision`, `lonjak_toko boolean not null`.
  - `public.pasar_manalagi_harian` (PK `tanggal, pasar`): `tanggal date not null`, `pasar text not null check (pasar in ('semua','blibli','tokopedia'))`, `jumlah_produk integer not null`, `median double precision not null`, `indeks_berantai double precision not null`, `median_rasio double precision`, `lonjak_pasar boolean not null`, `naik integer not null`, `turun integer not null`.
  - `public.ganti_pasar_manalagi(p_tanggal jsonb, p_baris jsonb, p_harian jsonb) returns void`: dalam satu transaksi menghapus baris kedua tabel yang `tanggal` ada di `p_tanggal` (array string ISO), lalu menyisipkan `p_baris`/`p_harian` (array objek, kunci = nama kolom) lewat `jsonb_populate_recordset`. Dipanggil lewat `POST /rest/v1/rpc/ganti_pasar_manalagi`.

- [ ] **Step 1: Tulis tes pgTAP** di `supabase/tests/pasar_manalagi.test.sql`, gaya `templat.test.sql` (dua akun: pengelola `…a1`, orang asing `…b2`). Sisipkan data lewat `ganti_pasar_manalagi` sebagai `service_role` (dua tanggal, 2 baris produk + 3 baris harian per tanggal). Asersi:
  - anon `select` kedua tabel → `throws_ok … '42501'`;
  - anon dan akun biasa memanggil `ganti_pasar_manalagi` → `throws_ok … '42501'`;
  - akun biasa (bukan pengelola) → `is_empty` di kedua tabel;
  - pengelola → `results_eq` jumlah baris (4 dan 6); pengelola `insert` → `throws_ok … '42501'`;
  - service_role memanggil lagi untuk tanggal pertama dengan 1 baris produk → tanggal pertama tinggal 1 baris, tanggal kedua tetap 2 ("ganti, bukan tambah");
  - service_role memanggil dengan `p_tanggal = '["<tanggal kedua>"]'`, `p_baris = '[]'`, `p_harian = '[]'` → tanggal kedua 0 baris ("kirim kosong menghapus tanggal");
  - `pasar = 'shopee'` → `throws_ok … '23514'`.

- [ ] **Step 2: Jalankan, pastikan gagal**
  Run: `npx supabase db reset; npx supabase test db` (dari `kebun-ibu/`)
  Expected: FAIL di `pasar_manalagi.test.sql` (tabel/fungsi belum ada); `lelang` dan `templat` tetap lulus.

- [ ] **Step 3: Tulis migrasi**, gaya `20261012000000_templat_pesan.sql` (kepala komentar, aman diulang: `if not exists`, `drop policy if exists`, `create or replace`). Isi:
  - kedua tabel seperti Interfaces;
  - `revoke all … from anon, authenticated`; `grant select … to authenticated`; `grant select, insert, delete … to service_role` (eksplisit: GRANT otomatis Supabase mati sejak 30 Okt 2026);
  - RLS aktif; satu policy `for select to authenticated using (public.is_pengelola())` per tabel; tanpa policy tulis;
  - fungsi: `language plpgsql`, **bukan** security definer, `set search_path = public, pg_temp`; `revoke all on function … from public, anon, authenticated`; `grant execute … to service_role`;
  - baris terakhir `notify pgrst, 'reload schema';` supaya PostgREST langsung mengenal fungsinya.

- [ ] **Step 4: Jalankan, pastikan lulus**
  Run: `npx supabase db reset; npx supabase test db`
  Expected: semua berkas tes PASS.

- [ ] **Step 5: Commit** (pengguna)
  ```powershell
  git add supabase/migrations/20261113000000_pasar_manalagi.sql supabase/tests/pasar_manalagi.test.sql
  git commit -m "Supabase: tabel pasar_manalagi + harian, baca hanya pengelola, fungsi ganti"
  ```

---

### Task 2: `dashboard_manalagi.py` — satu salinan SQL hitungan

**Files:**
- Create: `data-science/dashboard_manalagi.py`
- Test: `data-science/tests/test_dashboard_manalagi.py`

**Interfaces:**
- Consumes: `run.MULAI_GUDANG: dict[str, date]`; view `v_produk` di gudang.
- Produces:
  - konstanta `JENDELA_HARI, AMBANG_TOKO, AMBANG_PASAR, MIN_DATA, MAKS_JEDA_HARI` (nilai di Global Constraints);
  - `hitung(con: duckdb.DuckDBPyConnection, mulai: dict[str, date] = MULAI_GUDANG) -> tuple[pl.DataFrame, pl.DataFrame]` → `(baris, harian)` dengan kolom persis seperti notebook sekarang (`baris`: 16 kolom; `harian`: `pasar, tanggal, jumlah_produk, median, rata_rata, tertimbang, faktor_median, dinilai, median_rasio, naik, turun, indeks_berantai, lonjak_pasar`), urut `produk_key, tanggal` dan `pasar, tanggal`; `tanggal` bertipe `pl.Date`.

- [ ] **Step 1: Tulis tes.** Helper `gudang_palsu(baris: list[dict]) -> duckdb connection` membuat DuckDB di memori dengan **tabel** `v_produk` berkolom `tanggal, sumber, produk_key, nama, nama_toko, kota, harga, berat_gram, harga_per_kg, terjual_min, jenis_buah, opsi_default, olahan` (nilai bawaan: mangga, "Mangga Manalagi", default, bukan olahan, 1000 g). Pakai `mulai={"blibli": date(2026,1,1), "tokopedia": date(2026,1,1)}`. Tes:
  - `test_filter_hanya_manalagi_default_bukan_olahan_sejak_mulai`: baris "Mangga Harum Manis", `olahan=True`, `opsi_default=False`, `harga_per_kg=None`, dan tanggal sebelum `mulai` tidak muncul di `baris`.
  - `test_lonjak_toko_ditandai_sekali`: produk 10.000 pada 1–3 Jan, 12.000 pada 4 dan 5 Jan → `lonjak_toko` hanya `True` pada 4 Jan; `rasio_jendela` 4 Jan = 1.2.
  - `test_kurang_dari_min_data_tidak_dinilai`: produk dengan 2 hari sebelumnya → `rasio_jendela` null, `lonjak_toko` False.
  - `test_indeks_berantai_abaikan_produk_baru`: A 10.000→11.000, B 20.000→22.000 (1→2 Jan), C muncul 2 Jan 50.000 → `harian` `semua` 1 Jan `indeks_berantai` = 15.000, 2 Jan = 16.500.
  - `test_jeda_lebih_dari_maks_tidak_menggerakkan_indeks`: satu produk 10.000 pada 1 Jan dan 20.000 pada 10 Feb (jeda 40 hari) → `faktor` null; `indeks_berantai` 10 Feb = 10.000.
  - `test_lonjak_pasar_dan_tiga_pasar`: 3 produk (blibli + tokopedia) naik 10% bersamaan sesudah 3 hari datar → `lonjak_pasar` True untuk `semua` pada hari itu, `naik` = 3; `harian` punya baris `semua`, `blibli`, `tokopedia`.

- [ ] **Step 2: Jalankan, pastikan gagal**
  Run: `.venv\Scripts\python -m pytest tests/test_dashboard_manalagi.py -v`
  Expected: FAIL, `ModuleNotFoundError: dashboard_manalagi`.

- [ ] **Step 3: Implementasikan `hitung`.** Pindahkan SQL dari notebook **apa adanya**: `SUMBER_SQL` + "Langkah 1a" menjadi `CREATE TEMP TABLE baris AS …`, "Langkah 1b" menjadi `CREATE TEMP TABLE harian AS … FROM baris` (tabel temp boleh di koneksi `read_only`, sudah dicoba), lalu kembalikan `con.sql("FROM baris ORDER BY …").pl()` dan harian. Satu-satunya perubahan: `MULAI` → parameter `mulai`; `DROP TABLE IF EXISTS` di awal supaya bisa dipanggil dua kali pada koneksi yang sama.

- [ ] **Step 4: Jalankan, pastikan lulus**
  Run: `.venv\Scripts\python -m pytest -q`
  Expected: 352 passed.

- [ ] **Step 5: Commit** (pengguna)
  ```powershell
  git add data-science/dashboard_manalagi.py data-science/tests/test_dashboard_manalagi.py
  git commit -m "dashboard_manalagi.py: SQL hitungan dashboard dalam satu modul"
  ```

---

### Task 3: Notebook memakai `dashboard_manalagi`

**Files:**
- Modify: `data-science/dashboard_contoh.ipynb` (sel setup, `SUMBER_SQL`, "Langkah 1a", "Langkah 1b")

**Interfaces:**
- Consumes: `dashboard_manalagi.hitung`, konstanta parameternya.

- [ ] **Step 1: Simpan hasil lama sebagai pembanding.** Skrip di scratchpad menjalankan sel setup–1b notebook sekarang dan menyimpan `baris`/`harian` (pandas) ke Parquet.
- [ ] **Step 2: Ubah sel.** Setup mengimpor parameter dari modul (tidak mendefinisikannya lagi); hapus sel `SUMBER_SQL`; "Langkah 1a"+"1b" menjadi satu sel `with duckdb.connect(..., read_only=True) as con: baris, harian = (d.to_pandas() for d in hitung(con))` lalu `pd.to_datetime` untuk `tanggal` dan cetakan ringkasan yang sama. Markdown "Langkah 1" menyebut SQL-nya ada di `dashboard_manalagi.py`.
- [ ] **Step 3: Jalankan notebook (nbclient) dan bandingkan.**
  Expected: `baris: 163 baris → SAMA PERSIS`, `harian: 19 baris → SAMA PERSIS` (cara bandingkan = `sama()` di `langsung_gudang.py`), tanpa output `error`.
- [ ] **Step 4: Commit** (pengguna)
  ```powershell
  git add data-science/dashboard_contoh.ipynb
  git commit -m "Notebook dashboard: SQL dari dashboard_manalagi.py"
  ```

---

### Task 4: `kirim_supabase.py` — kolom kirim, tanggal berubah, salinan terkirim

**Files:**
- Create: `data-science/kirim_supabase.py`
- Test: `data-science/tests/test_kirim_supabase.py`

**Interfaces:**
- Consumes: `dashboard_manalagi.hitung`.
- Produces:
  - `KOLOM_BARIS: list[str]` = `tanggal, sumber, produk_key, nama_toko, kota, harga_per_kg, terjual_min, median_jendela, rasio_jendela, lonjak_toko`;
    `KOLOM_HARIAN: list[str]` = `tanggal, pasar, jumlah_produk, median, indeks_berantai, median_rasio, lonjak_pasar, naik, turun`.
  - `Data = tuple[pl.DataFrame, pl.DataFrame]` (baris, harian).
  - `untuk_dikirim(baris: pl.DataFrame, harian: pl.DataFrame) -> Data`: pilih kolom di atas, kolom float dibulatkan 6 desimal.
  - `tanggal_berubah(baru: Data, lama: Data | None) -> list[date]`: tanggal (urut) yang barisnya berbeda di salah satu tabel, termasuk tanggal yang hanya ada di satu sisi; `lama=None` → semua tanggal `baru`. Dihitung dengan DuckDB `EXCEPT` dua arah (NULL dianggap sama; sudah dicoba).
  - `kelompokkan(tanggal: list[date], ukuran: int = 31) -> list[list[date]]`.
  - `muatan(tanggal: list[date], data: Data) -> dict`: `{"p_tanggal": [iso…], "p_baris": [...], "p_harian": [...]}` hanya untuk tanggal itu; tanggal ISO string; lolos `json.dumps(..., allow_nan=False)`.
  - `baca_terkirim(folder: Path) -> Data | None` (None kalau salah satu berkas tidak ada); `simpan_terkirim(folder: Path, lama: Data | None, baru: Data, tanggal: list[date]) -> Data`: salinan = `lama` tanpa `tanggal` + `baru` untuk `tanggal`; ditulis ke `pasar_manalagi.parquet` dan `pasar_manalagi_harian.parquet` lewat berkas `.sementara` lalu ganti nama; mengembalikan salinan baru.

- [ ] **Step 1: Tulis tes** (data kecil dibuat langsung sebagai `pl.DataFrame`; satu tes memakai `gudang_palsu` dari Task 2 — pindahkan helper itu ke `tests/conftest.py`):
  - `test_untuk_dikirim_hanya_kolom_disetujui`: kolom keluaran == `KOLOM_BARIS` / `KOLOM_HARIAN`.
  - `test_tanpa_salinan_semua_tanggal`: `tanggal_berubah(baru, None)` == semua tanggal.
  - `test_hitungan_sama_tidak_ada_yang_berubah`: `hitung` dua kali pada gudang palsu yang sama → `tanggal_berubah` == `[]` (Review Focus 2).
  - `test_tanggal_susulan_mengubah_tanggal_sesudahnya`: gudang palsu 1–5 Jan tanpa 3 Jan sebagai `lama`; tambah 3 Jan dengan harga berbeda → hasil memuat 3, 4, 5 Jan dan tidak memuat 1–2 Jan.
  - `test_tanggal_yang_hilang_ikut_berubah`: tanggal ada di `lama` tetapi tidak di `baru` → ikut dikembalikan (Review Focus 4).
  - `test_kelompokkan`: 65 tanggal → panjang kelompok `[31, 31, 3]`.
  - `test_muatan_hanya_tanggal_diminta_dan_json_aman`: muatan untuk 1 tanggal hanya berisi baris tanggal itu; `json.dumps(m, allow_nan=False)` tidak error; null tetap `None`.
  - `test_simpan_terkirim_mengganti_tanggal_saja`: `lama` 1–3 Jan, `baru` berbeda di 2 Jan, simpan `[2 Jan]` → salinan = 1 & 3 Jan dari `lama`, 2 Jan dari `baru`; `baca_terkirim` mengembalikan isi yang sama; tidak ada berkas `.sementara`.

- [ ] **Step 2: Jalankan, pastikan gagal**
  Run: `.venv\Scripts\python -m pytest tests/test_kirim_supabase.py -v`
  Expected: FAIL, `ModuleNotFoundError: kirim_supabase`.

- [ ] **Step 3: Implementasikan fungsi-fungsi di Interfaces.**

- [ ] **Step 4: Jalankan, pastikan lulus**
  Run: `.venv\Scripts\python -m pytest -q`
  Expected: 360 passed.

- [ ] **Step 5: Commit** (pengguna)
  ```powershell
  git add data-science/kirim_supabase.py data-science/tests/test_kirim_supabase.py data-science/tests/conftest.py data-science/tests/test_dashboard_manalagi.py
  git commit -m "kirim_supabase.py: kolom kirim, tanggal berubah, salinan terkirim"
  ```

---

### Task 5: `kirim_supabase.py` — panggil Supabase, `jalankan`, `main`

**Files:**
- Modify: `data-science/kirim_supabase.py`
- Test: `data-science/tests/test_kirim_supabase.py`

**Interfaces:**
- Consumes: semua fungsi Task 4; `dashboard_manalagi.hitung`.
- Produces:
  - `DASAR = Path(__file__).resolve().parent`; `GUDANG = DASAR / "warehouse" / "harga_buah.duckdb"`; `TERKIRIM = DASAR / "warehouse" / "terkirim"`; `ENV = DASAR.parent / ".env.local"`; `LOG = DASAR / "logs" / "kirim_supabase.log"`.
  - `baca_kunci(env: Path, lingkungan: Mapping[str, str] = os.environ) -> tuple[str, str]`: `(url, kunci)` dari `NEXT_PUBLIC_SUPABASE_URL` dan `SUPABASE_SERVICE_ROLE_KEY`; env var mengalahkan berkas; berkas dibaca sebagai baris `NAMA=nilai` (abaikan kosong dan `#`); tidak ada → `RuntimeError` yang menyebut **nama** variabel, bukan nilainya.
  - `buat_pengirim(url: str, kunci: str, post: Callable = curl_cffi.requests.post) -> Callable[[dict], None]`: POST ke `{url}/rest/v1/rpc/ganti_pasar_manalagi`, header `apikey`, `Authorization: Bearer`, `Content-Type: application/json`, timeout 60 s; status bukan 2xx → `RuntimeError(f"Supabase {status}: {teks[:300]}")`.
  - `jalankan(data: Data, folder: Path, kirim: Callable[[dict], None], semua: bool = False, coba: bool = False) -> int`: jumlah tanggal terkirim. Urutan: `data` kosong → `RuntimeError("hasil hitungan kosong")`; lama = `None` kalau `semua` else `baca_terkirim`; per kelompok: `kirim(muatan(...))` lalu `simpan_terkirim`; `coba=True` → hanya log tanggal, tidak kirim, tidak simpan.
  - `main(argv: list[str] | None = None) -> int`: flag `--semua`, `--coba`; log ke `LOG` + konsol (gaya `sinkron_vps.main`); buka gudang read-only → `hitung` → `untuk_dikirim` → `jalankan`; galat apa pun → `log.exception`, kembali 1; sukses → 0. Log akhir: `"terkirim N tanggal (B baris, H baris harian)"`.

- [ ] **Step 1: Tulis tes** (pengirim palsu = fungsi yang mencatat muatan; bisa dibuat melempar pada panggilan ke-k):
  - `test_baca_kunci_env_mengalahkan_berkas` dan `test_baca_kunci_tidak_ada_menyebut_nama`: pesan galat memuat `SUPABASE_SERVICE_ROLE_KEY` dan tidak memuat isi kunci palsu.
  - `test_pengirim_header_dan_galat`: `post` palsu menerima URL `…/rest/v1/rpc/ganti_pasar_manalagi` dan kedua header; status 401 → `RuntimeError` memuat `"401"`.
  - `test_jalankan_pertama_mengirim_semua_lalu_tidak_ada`: jalan 1 mengirim semua tanggal; jalan 2 dengan data sama → 0, pengirim tidak dipanggil.
  - `test_jalankan_menolak_hasil_kosong`: data kosong + salinan ada → `RuntimeError`, pengirim tidak dipanggil, salinan tidak berubah (Review Focus 1).
  - `test_gagal_di_tengah_salinan_hanya_kelompok_yang_berhasil`: 40 tanggal (2 kelompok), pengirim melempar di panggilan ke-2 → galat naik; `baca_terkirim` hanya memuat 31 tanggal pertama; jalan berikutnya mengirim 9 sisanya (Review Focus 3).
  - `test_semua_mengirim_semua_tanggal`: salinan lengkap ada, `semua=True` → semua tanggal dikirim (Review Focus 5).
  - `test_coba_tidak_mengirim_tidak_menyimpan`.

- [ ] **Step 2: Jalankan, pastikan gagal**
  Run: `.venv\Scripts\python -m pytest tests/test_kirim_supabase.py -v`
  Expected: tes baru FAIL (`ImportError`/`AttributeError`), tes Task 4 tetap lulus.

- [ ] **Step 3: Implementasikan fungsi-fungsi di Interfaces.**

- [ ] **Step 4: Jalankan, pastikan lulus**
  Run: `.venv\Scripts\python -m pytest -q`
  Expected: 368 passed.

- [ ] **Step 5: Uji ujung-ke-ujung ke Supabase lokal** (bukan produksi).
  Run (PowerShell, dari `data-science/`, sesudah `npx supabase db reset` di Task 1; kunci dari `npx supabase status`):
  `$env:NEXT_PUBLIC_SUPABASE_URL="http://127.0.0.1:54321"; $env:SUPABASE_SERVICE_ROLE_KEY="<service_role lokal>"; .venv\Scripts\python kirim_supabase.py --semua`
  Expected: log `terkirim <hari> tanggal (163+ baris, 19+ baris harian)`; jumlah baris di Studio lokal sama; jalan kedua tanpa `--semua` → `terkirim 0 tanggal`. Hapus berkas `warehouse/terkirim/` sesudahnya (salinan ini milik Supabase lokal, bukan produksi).

- [ ] **Step 6: Commit** (pengguna)
  ```powershell
  git add data-science/kirim_supabase.py data-science/tests/test_kirim_supabase.py
  git commit -m "kirim_supabase.py: kirim tanggal berubah ke Supabase"
  ```

---

### Task 6: Langkah ke-4 Task Scheduler, dokumen, kiriman pertama ke produksi

**Files:**
- Modify: `data-science/daftar_tugas_harian.ps1` (tambah aksi ke-4, perbarui komentar dan `-Description`)
- Modify: `data-science/README.md` (satu bagian pendek: apa yang dikirim, `--coba`, `--semua`, letak log dan salinan)
- Modify: `docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md` ("Belum diputuskan" no. 2 → keputusan: kirim tanggal yang berubah saja, dibandingkan dengan salinan `warehouse/terkirim/`; `--semua` kalau Supabase di-reset)

- [ ] **Step 1: Tambah aksi** `pythonw.exe "kirim_supabase.py"` dengan `-WorkingDirectory $dasar` sesudah aksi `run.py`; komentar "kirim tanggal yang berubah ke Supabase (dashboard Manalagi)".
- [ ] **Step 2: Pengguna menjalankan migrasi di produksi**: salin isi `20261113000000_pasar_manalagi.sql` ke Supabase SQL Editor → Run. Cek: Table Editor menampilkan kedua tabel (kosong).
- [ ] **Step 3: Kiriman pertama ke produksi** (pengguna, dari `data-science/`, tanpa env var lokal):
  `.venv\Scripts\python kirim_supabase.py --coba` lalu `.venv\Scripts\python kirim_supabase.py`
  Expected: `--coba` menyebut semua tanggal sejak 7 Nov; jalan sungguhan `terkirim … tanggal`; jumlah baris di Table Editor = angka di log.
- [ ] **Step 4: Daftarkan ulang tugas** (pengguna, sekali): `powershell -ExecutionPolicy Bypass -File data-science\daftar_tugas_harian.ps1`
  Expected: `Get-ScheduledTask KebunIbu-TarikHarian | Select -Expand Actions` menampilkan 4 aksi; esok hari `logs/kirim_supabase.log` punya baris 06:xx.
- [ ] **Step 5: Commit** (pengguna)
  ```powershell
  git add data-science/daftar_tugas_harian.ps1 data-science/README.md docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md
  git commit -m "Task Scheduler: langkah ke-4 kirim_supabase.py; dokumen"
  ```

---

**Di luar plan ini:** halaman `/admin/pasar` (teman pengguna) membaca kedua tabel dengan klien Supabase biasa sesudah login; harga Ibuk asli; tren wilayah.
