# Filter wilayah — sisi data dan Supabase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Setiap baris harga mendapat kode kabupaten/kota dan provinsi resmi; dashboard menghitung deret harian per wilayah; Supabase menyimpan kode, deret per wilayah, dan daftar wilayah untuk kotak cari.

**Architecture:** Daftar resmi Kepmendagri 2025 disimpan sebagai CSV di repo. `transform/wilayah.py` mencocokkan `kota` ke kode; `transform/model.py` menaruh kode di `fakta_harga`; cek I menyalin kota yang tak dikenal ke karantina. `dashboard_manalagi.hitung()` menghitung `harian` per (wilayah, pasar); `kirim_supabase.py` mengirimnya di belakang saklar `KIRIM_PER_WILAYAH`.

**Tech Stack:** Python 3.11 (venv `data-science/.venv`), Polars 2.0, DuckDB 1.5.6, Pandera, pytest; Supabase Postgres + pgTAP (`npx supabase test db`, CLI 3.1.0, Docker hidup).

**Spec:** `docs/superpowers/specs/2026-11-14-filter-wilayah-design.md`. Bagian web dikerjakan sesi `/admin/pasar` sesudah halamannya selesai; rencana ini tidak menyentuh `src/`.

## Global Constraints

- Kerja di folder utama, cabang yang sedang aktif; **bukan worktree**. Commit dengan `git add <berkas>` yang tepat, **tidak pernah `git commit -am`** (folder berisi perubahan lain yang belum di-commit).
- Perintah Python dijalankan dari `data-science/` dengan `.venv/Scripts/python.exe`.
- `.env.local` = Supabase **PRODUKSI**. Uji kirim hanya dengan **kedua** env var lokal (`NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321`, `SUPABASE_SERVICE_ROLE_KEY` dari `npx supabase status`); log harus menulis `tujuan: 127.0.0.1:54321`.
- Kunci wilayah: `semua`; kelompok `jabodetabek`; provinsi = kode 2 digit (`35`); kab/kota = `NN.NN` (`35.78`).
- Jabodetabek = `31.01, 31.71, 31.72, 31.73, 31.74, 31.75, 32.01, 32.16, 32.71, 32.75, 32.76, 36.03, 36.71, 36.74`.
- Nama tampil = nama resmi tanpa kata `Administrasi` dan tanpa spasi di ujung.
- Cek I: alasan karantina persis `cek_I_kota_tidak_dikenal`; baris disalin, **tetap dimuat**. `kota` kosong tidak dicek.
- Baris `harian` dengan `wilayah = 'semua'` harus **sama persis** dengan `harian` sebelum perubahan ini.
- `KIRIM_PER_WILAYAH = False` sampai web membaca `.eq("wilayah", "semua")` (langkah urutan spec).
- Sumber daftar: `cahyadsn/wilayah` `db/wilayah.sql` (Kepmendagri No 300.2.2-2138 Tahun 2025, MIT); atribusi di kepala CSV.

## Review Focus

1. **Nama kota yang sama di dua provinsi** (Banjar tanpa awalan) — harus kosong dan masuk cek I, bukan ditebak. Diuji di Task 1 dan 2.
2. **Payload lama tanpa `wilayah`** setelah migrasi — `ganti_pasar_manalagi` harus mengisi `'semua'`, bukan gagal NOT NULL (`jsonb_populate_recordset` mengisi kunci yang hilang dengan NULL, bukan default kolom). Diuji di Task 5: `pasar_manalagi.test.sql` lama lulus tanpa diubah.
3. **Produk tanpa kode** (kota kosong / tak dikenal) — hanya muncul di deret `semua`, tidak membuat deret wilayah `NULL`. Diuji di Task 3.
4. **Saklar mati** — `kirim_supabase.py` tidak mengirim baris non-`semua` dan tidak memanggil `ganti_pasar_wilayah`. Diuji di Task 4.
5. **Salinan terkirim berkolom lama** (produksi sekarang) — jalan terjadwal berikutnya harus mengirim ulang semua, bukan gagal. Diuji di Task 4 (`test_salinan_kolom_lama_kirim_semua`). Gudang lama tanpa kolom kode diuji di Task 2.

---

### Task 1: Daftar resmi dan pencocokan nama

**Files:**
- Create: `data-science/referensi/buat_wilayah_kabkota.py`, `data-science/referensi/wilayah_kabkota.csv` (keluaran skrip)
- Create: `data-science/transform/wilayah.py`
- Test: `data-science/tests/test_wilayah.py`

**Interfaces:**
- Produces:
  ```python
  # transform/wilayah.py
  CSV: Path                                   # referensi/wilayah_kabkota.csv
  ALIAS_KOTA: dict[str, str]                  # kunci_nama(alias) -> kabkota_kode; awalnya kosong
  KELOMPOK: dict[str, tuple[str, frozenset[str]]]   # {"jabodetabek": ("Jabodetabek", {kode,...})}
  KATA_KUNCI_PROVINSI: dict[str, str]         # provinsi_kode -> "jatim jawa timur" dst.
  def kunci_nama(nama: str) -> str
  def cocokkan(kota: str | None) -> tuple[str | None, str | None]   # (kabkota_kode, provinsi_kode)
  def kabkota() -> pl.DataFrame               # kode, nama, jenis, provinsi_kode, provinsi (514 baris, cache)
  def anggota() -> pl.DataFrame               # kabkota_kode, wilayah: kode sendiri, provinsinya, kelompoknya
  ```
- CSV kolom: `kode, nama, jenis, provinsi_kode, provinsi`; `jenis` ∈ `kota | kabupaten`; baris komentar atribusi diawali `#`.

- [ ] **Step 1: Buat CSV.** Unduh `https://raw.githubusercontent.com/cahyadsn/wilayah/master/db/wilayah.sql` ke scratchpad. `buat_wilayah_kabkota.py <wilayah.sql>` membaca pasangan `('kode','nama')`, kode 2 digit = provinsi, `NN.NN` = kab/kota, lalu menulis CSV. Jalankan; Expected: 514 baris data, 38 provinsi berbeda.
- [ ] **Step 2: Tulis tes yang gagal** (`tests/test_wilayah.py`):
  ```python
  @pytest.mark.parametrize("kota,hasil", [
      ("Kota Surabaya", ("35.78", "35")), ("Surabaya", ("35.78", "35")),
      ("Kab.Ciamis", ("32.07", "32")), ("Kota Palangka Raya", ("62.71", "62")),
      ("Kota Pematang Siantar", ("12.72", "12")), ("Kota Banjar", ("32.79", "32")),
      ("Kab. Banjar", ("63.03", "63")), ("Banjar", (None, None)),
      ("Kota Antah Berantah", (None, None)), (None, (None, None)), ("  ", (None, None)),
      ("Jakarta Timur", ("31.75", "31")),
  ])
  def test_cocokkan(kota, hasil): assert cocokkan(kota) == hasil

  def test_alias(monkeypatch):
      monkeypatch.setitem(ALIAS_KOTA, kunci_nama("Kota Antah Berantah"), "35.78")
      assert cocokkan("Kota Antah Berantah") == ("35.78", "35")

  def test_daftar_lengkap():
      k = kabkota()
      assert k.height == 514 and k["provinsi_kode"].n_unique() == 38
      assert "Administrasi" not in " ".join(k["nama"]) and all(n == n.strip() for n in k["nama"])
      assert len(KELOMPOK["jabodetabek"][1]) == 14

  def test_anggota_surabaya():
      a = anggota().filter(pl.col("kabkota_kode") == "35.78")["wilayah"].to_list()
      assert sorted(a) == ["35", "35.78"]
      assert "jabodetabek" in anggota().filter(pl.col("kabkota_kode") == "36.74")["wilayah"].to_list()
  ```
- [ ] **Step 3:** `.venv/Scripts/python.exe -m pytest tests/test_wilayah.py -q` → FAIL (modul belum ada).
- [ ] **Step 4: Tulis `transform/wilayah.py`.** `kunci_nama`: huruf kecil, buang isi kurung, buang awalan `kabupaten administrasi|kota administrasi|kabupaten|kab\.|kota` (diikuti `\s*`), buang semua spasi. `cocokkan`: alias dulu; awalan kota/kabupaten di masukan memilih `jenis`; hasil >1 provinsi atau 0 → `(None, None)`.
- [ ] **Step 5:** pytest file itu → PASS.
- [ ] **Step 6: Commit** — `git add data-science/referensi data-science/transform/wilayah.py data-science/tests/test_wilayah.py && git commit -m "Daftar wilayah Kepmendagri 2025 dan pencocokan kota"`

---

### Task 2: Kode wilayah di fakta, cek I, v_produk

**Files:**
- Modify: `data-science/transform/model.py` (`KOLOM_FAKTA`, `_fakta`)
- Modify: `data-science/transform/skema.py` (`CEK_I`, `pisahkan`, docstring modul)
- Test: `data-science/tests/test_model.py`, `tests/test_skema.py`, `tests/test_loader.py`

**Interfaces:**
- Consumes: `cocokkan` (Task 1).
- Produces: `fakta_harga` + `kabkota_kode: Utf8`, `provinsi_kode: Utf8` (sesudah `kota`); `skema.CEK_I = "cek_I_kota_tidak_dikenal"`; `v_produk` membawa kedua kolom (otomatis lewat `f.*`).

- [ ] **Step 1: Tes yang gagal:**
  - `test_model.py::test_fakta_kode_wilayah`: `df_blibli` dengan `lokasi` = `"Kota Surabaya"` untuk satu SKU dan `"Kota Antah"` untuk lainnya → baris itu `("35.78", "35")`, lainnya `(None, None)`.
  - `test_skema.py::test_cek_I_disalin_tetap_lolos`: fakta tiga baris (`kota` = `"Kota Antah"`, `"Kota Surabaya"`, `None`, kode sesuai `cocokkan`) → `pisahkan(..., SkemaFakta, "blibli")`: `lolos.height == 3`; karantina tepat satu baris, `alasan == "cek_I_kota_tidak_dikenal"`.
  - `test_loader.py::test_v_produk_kode_wilayah`: muat `mentah_blibli` dengan `lokasi="Kota Surabaya"` → `SELECT DISTINCT kabkota_kode, provinsi_kode FROM v_produk` = `[("35.78", "35")]`; dan versi gudang lama (pola `test_siapkan_menambah_kolom_baru_ke_gudang_lama`, buang baris `kabkota_kode`/`provinsi_kode` dari `_buat_tabel`) tetap bisa `siapkan` + `muat`.
- [ ] **Step 2:** pytest ketiga berkas → FAIL karena kolom/cek belum ada.
- [ ] **Step 3: Implementasi.** `_fakta`: petakan setiap `kota` unik sekali lewat `cocokkan` (bukan per baris). `pisahkan`: kalau df punya `kota` dan `kabkota_kode`, baris `kota` terisi (setelah strip) dan `kabkota_kode` null → tambahkan alasan `CEK_I`, seperti cek H (disalin, tetap lolos).
- [ ] **Step 4:** `.venv/Scripts/python.exe -m pytest -q` → semua lulus (sebelumnya 376 + tes baru).
- [ ] **Step 5: Commit** — `git add` keempat berkas kode/tes → `git commit -m "fakta_harga: kode kab/kota dan provinsi; cek I kota tidak dikenal"`

---

### Task 3: `harian` per wilayah dan daftar wilayah

**Files:**
- Modify: `data-science/dashboard_manalagi.py` (`_sql_sumber`, `_sql_baris`, `_SQL_HARIAN`, `hitung`, docstring)
- Create function: `daftar_wilayah` di `dashboard_manalagi.py`
- Modify: `data-science/tests/conftest.py` (`_KOLOM_V_PRODUK` + `kabkota_kode`, `provinsi_kode` VARCHAR, bawaan `None`)
- Modify: `data-science/dashboard_contoh.ipynb` (sel yang memanggil `hitung`), `data-science/ekspor_uji_web.py` (pemanggil `hitung`)
- Test: `data-science/tests/test_dashboard_manalagi.py`

**Interfaces:**
- Consumes: `wilayah.anggota()`, `wilayah.kabkota()`, `wilayah.KELOMPOK`, `wilayah.KATA_KUNCI_PROVINSI` (Task 1); `v_produk.kabkota_kode/provinsi_kode` (Task 2).
- Produces:
  - `hitung(con, mulai) -> (baris, harian)`: `baris` + `kabkota_kode`, `provinsi_kode`; `harian` + kolom `wilayah`, urut `wilayah, pasar, tanggal`.
  - `daftar_wilayah(baris: pl.DataFrame) -> pl.DataFrame` kolom `wilayah, pasar, nama, tingkat, provinsi_kode, kata_kunci, jumlah_toko`; `tingkat` ∈ `kelompok | provinsi | kabkota`; `pasar` ∈ `semua | blibli | tokopedia`; tanpa baris `semua`-wilayah; `jumlah_toko` = `nama_toko` berbeda sepanjang seluruh `baris`; `provinsi_kode` hanya untuk `kabkota`; `kata_kunci` dari `KATA_KUNCI_PROVINSI` untuk provinsi, kosong lainnya.

- [ ] **Step 1: Tes yang gagal** (pakai `buat_gudang`; isi `kabkota_kode`/`provinsi_kode` langsung):
  - `test_semua_tidak_terpengaruh_kode`: data yang sama dengan dan tanpa kode → `harian.filter(wilayah == "semua").drop("wilayah")` sama persis.
  - `test_deret_provinsi_sama_dengan_dihitung_sendiri`: produk di `35.78` dan `32.75` → deret `wilayah == "35"` sama dengan `harian` `semua` dari gudang yang hanya berisi produk `35.78`.
  - `test_kelompok_jabodetabek`: produk `31.75` dan `36.74` ada di `jabodetabek`; produk `35.78` tidak.
  - `test_tanpa_kode_hanya_di_semua`: produk tanpa kode → tidak ada `wilayah` NULL; hanya ikut `semua`.
  - `test_daftar_wilayah`: dua toko di `35.78` (satu Blibli, satu Tokopedia, beda tanggal) → baris (`35`, `semua`) `jumlah_toko == 2`, (`35`, `blibli`) `== 1`, (`35.78`, `semua`) `tingkat == "kabkota"`, `nama == "Kota Surabaya"`, `provinsi_kode == "35"`; (`35`, …) `nama == "Jawa Timur"`, `kata_kunci` memuat `"jatim"`.
- [ ] **Step 2:** pytest berkas itu → FAIL.
- [ ] **Step 3: Implementasi.** `hitung` mendaftarkan `wilayah.anggota()` sebagai tabel `anggota`. Di `_SQL_HARIAN`, CTE `b` = setiap baris `baris` sekali per pasar (`semua`, `sumber`) × wilayah (`semua` ∪ `anggota.wilayah` untuk `kabkota_kode`-nya); semua `GROUP BY`/`PARTITION BY pasar` menjadi `wilayah, pasar`. Notebook dan `ekspor_uji_web.py`: tepat sesudah `hitung`, saring `wilayah == "semua"` lalu buang kolom `wilayah`.
- [ ] **Step 4:** pytest seluruh suite → PASS; notebook sel 1 dijalankan ulang tanpa galat (`jupyter nbconvert --execute` atau jalankan sel di VS Code).
- [ ] **Step 5: Commit** — `git add data-science/dashboard_manalagi.py data-science/tests/conftest.py data-science/tests/test_dashboard_manalagi.py data-science/dashboard_contoh.ipynb data-science/ekspor_uji_web.py && git commit -m "dashboard_manalagi: harian per wilayah, daftar wilayah"`

---

### Task 4: `kirim_supabase.py` — kolom baru, saklar, daftar wilayah

**Files:**
- Modify: `data-science/kirim_supabase.py`
- Test: `data-science/tests/test_kirim_supabase.py`

**Interfaces:**
- Consumes: `hitung`, `daftar_wilayah` (Task 3).
- Produces:
  - `KIRIM_PER_WILAYAH = False` (konstanta modul).
  - `KOLOM_BARIS` + `"kabkota_kode", "provinsi_kode"`; `KOLOM_HARIAN` + `"wilayah"`; `KUNCI[1] = ["tanggal", "pasar", "wilayah"]`.
  - `untuk_dikirim(baris, harian, per_wilayah: bool = KIRIM_PER_WILAYAH) -> Data` (tidak per wilayah → hanya `wilayah == "semua"`).
  - `buat_pengirim(url, kunci, post=requests.post, fungsi: str = "ganti_pasar_manalagi")`.
  - `kirim_daftar_wilayah(daftar: pl.DataFrame, kirim: Callable[[dict], None]) -> int` → `kirim({"p_baris": daftar.to_dicts()})`, mengembalikan jumlah baris.
  - `baca_terkirim(folder)`: kalau salah satu berkas tidak punya semua kolom `KOLOM_BARIS`/`KOLOM_HARIAN`, kembalikan `None` dan log `"salinan terkirim berkolom lama: kirim semua"`. Tanpa ini, jadwal 06:00 sesudah commit Task 4 gagal di `tanggal_berubah` (salinan produksi berkolom lama).
  - `main`: kalau `KIRIM_PER_WILAYAH` dan bukan `--coba`, sesudah `jalankan` panggil `kirim_daftar_wilayah(daftar_wilayah(baris_penuh), buat_pengirim(url, kunci, fungsi="ganti_pasar_wilayah"))` dan log `"daftar wilayah: N baris"`.

- [ ] **Step 1: Tes yang gagal:**
  - `test_saklar_mati_hanya_semua`: `untuk_dikirim(..., per_wilayah=False)[1]["wilayah"].unique() == ["semua"]`; `per_wilayah=True` memuat wilayah lain.
  - `test_kolom_baru_terkirim`: `muatan(...)["p_baris"][0]` punya `kabkota_kode`, `provinsi_kode`; `p_harian[0]` punya `wilayah`.
  - `test_pengirim_fungsi_lain`: `buat_pengirim(..., fungsi="ganti_pasar_wilayah")` memanggil URL berakhiran `/rest/v1/rpc/ganti_pasar_wilayah`.
  - `test_kirim_daftar_wilayah`: daftar 3 baris → satu panggilan berisi `p_baris` 3 dict, kembali 3.
  - `test_salinan_kolom_lama_kirim_semua`: tulis salinan dengan kolom lama (tanpa `wilayah`, `kabkota_kode`) → `baca_terkirim` = `None`; `jalankan` mengirim semua tanggal tanpa galat.
  - Tes lama yang membandingkan kolom (`test_untuk_dikirim_hanya_kolom_disetujui`) diperbarui ke daftar kolom baru.
- [ ] **Step 2:** pytest berkas itu → FAIL.
- [ ] **Step 3:** Implementasi sesuai Interfaces.
- [ ] **Step 4:** pytest seluruh suite → PASS.
- [ ] **Step 5: Commit** — `git add data-science/kirim_supabase.py data-science/tests/test_kirim_supabase.py && git commit -m "kirim_supabase: kode wilayah, saklar KIRIM_PER_WILAYAH, daftar wilayah"`

---

### Task 5: Migrasi Supabase dan pgTAP

**Files:**
- Create: `supabase/migrations/20261115000000_wilayah_pasar.sql`
- Create: `supabase/tests/pasar_wilayah.test.sql`
- Unchanged and must still pass: `supabase/tests/pasar_manalagi.test.sql`

**Interfaces:**
- Produces:
  - `pasar_manalagi` + `kabkota_kode text`, `provinsi_kode text`.
  - `pasar_manalagi_harian` + `wilayah text not null default 'semua'`; PK `(tanggal, pasar, wilayah)`.
  - `pasar_wilayah(wilayah text, pasar text check in ('semua','blibli','tokopedia'), nama text not null, tingkat text check in ('kelompok','provinsi','kabkota'), provinsi_kode text, kata_kunci text, jumlah_toko integer not null)`, PK `(wilayah, pasar)`.
  - `ganti_pasar_wilayah(p_baris jsonb) returns void`: hapus semua lalu isi, satu transaksi.
  - `ganti_pasar_manalagi` dibuat ulang: baris harian tanpa `wilayah` diisi `'semua'`.

- [ ] **Step 1: Tes pgTAP yang gagal** (`pasar_wilayah.test.sql`, pola `pasar_manalagi.test.sql`): service_role mengisi `pasar_wilayah` lewat fungsi (lives_ok); isi ulang mengganti, bukan menambah; anon 42501 di tabel dan fungsi; non-pengelola melihat 0 baris; pengelola melihat isi dan 42501 saat insert langsung; `tingkat='negara'` → 23514; dua baris harian sama `(tanggal, pasar)` beda `wilayah` lewat `ganti_pasar_manalagi` → keduanya tersimpan.
- [ ] **Step 2:** `npx supabase test db` → FAIL (tabel/fungsi belum ada).
- [ ] **Step 3:** Tulis migrasi. Aman diulang: `add column if not exists`; `drop constraint if exists pasar_manalagi_harian_pkey` lalu `add primary key`; `create table if not exists`; revoke-lalu-grant dan RLS seperti `20261113000000_pasar_manalagi.sql`; akhiri `notify pgrst, 'reload schema';`. Terapkan lokal: `npx supabase migration up` (atau `db reset`).
- [ ] **Step 4:** `npx supabase test db` → semua lulus, **termasuk `pasar_manalagi.test.sql` tanpa diubah** (payload lamanya tidak punya `wilayah`). Jalankan migrasi dua kali → tanpa galat.
- [ ] **Step 5: Commit** — `git add supabase/migrations/20261115000000_wilayah_pasar.sql supabase/tests/pasar_wilayah.test.sql && git commit -m "Supabase: kode wilayah, harian per wilayah, pasar_wilayah"`

---

### Task 6: Terapkan ke gudang, uji di Supabase lokal, serah terima

**Files:** tidak ada kode baru; perbarui `docs/perbaikan-pipeline-2026-11-13.md` (bagian baru) dan `data-science/README.md` (kolom `fakta_harga`, cek I).

- [ ] **Step 1: Cadangan + muat ulang gudang.** Salin `warehouse/harga_buah.duckdb` ke `warehouse/harga_buah.sebelum-wilayah-<tanggal>.duckdb`. Muat ulang setiap tanggal sejak `MULAI_GUDANG` lewat `run.jalankan(sumber, t, {"transform","load"}, DASAR/"data_lake", db, folder_log=DASAR/"logs", akar_vps=run.AKAR_VPS)` (lewati Blibli 11 Nov). Expected: 0 run `gagal`, jumlah baris fakta per sumber sama seperti sebelum.
- [ ] **Step 2: Cek data asli.**
  - `SELECT count(*) FROM fakta_harga WHERE kota IS NOT NULL AND kabkota_kode IS NULL` → 0 (147/147 cocok).
  - `produk_karantina` tanpa baris `cek_I_kota_tidak_dikenal` baru.
  - `harian` `wilayah == "semua"` dari `hitung` sama persis dengan `warehouse/terkirim/kbcuayymasafndgbcjjb.supabase.co/pasar_manalagi_harian.parquet` (kolom `KOLOM_HARIAN` lama, dibulatkan seperti `untuk_dikirim`).
  - Cetak 5 provinsi teratas `daftar_wilayah` pasar `semua` (harapan kasar: DKI Jakarta, Jawa Barat, Jawa Timur, Banten, Bali).
- [ ] **Step 3: Supabase lokal.** Migrasi sudah lokal (Task 5). Set **kedua** env var lokal, ubah `KIRIM_PER_WILAYAH` sementara ke `True` **tanpa commit**, jalankan `kirim_supabase.py --semua`. Expected log: `tujuan: 127.0.0.1:54321`, `terkirim N tanggal`, `daftar wilayah: N baris`. Periksa di Studio lokal (127.0.0.1:54323): `pasar_manalagi_harian` punya beberapa `wilayah`; `pasar_wilayah` terisi. Kembalikan saklar ke `False` (`git diff kirim_supabase.py` kosong).
- [ ] **Step 4: Dokumentasi + commit** — bagian baru di `perbaikan-pipeline-2026-11-13.md` (apa, cara menerapkan, cadangan) dan README → `git add` kedua berkas → commit.
- [ ] **Step 5: Serah terima ke pengguna** (bukan dijalankan pelaksana):
  1. Jalankan `20261115000000_wilayah_pasar.sql` di **dashboard supabase.com** (bukan Studio 127.0.0.1).
  2. Jadwal 06:00/12:00 tetap aman: saklar mati, payload `wilayah='semua'`.
  3. Sesi web: kotak cari + `.eq("wilayah", w)` (bawaan `semua`), deploy.
  4. Sesudah web live: `KIRIM_PER_WILAYAH = True`, commit, lalu `python kirim_supabase.py --semua` sekali (mengirim kode yang tadinya diabaikan server).
