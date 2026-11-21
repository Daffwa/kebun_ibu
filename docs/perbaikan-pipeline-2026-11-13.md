# Pipeline fix — 13 Nov 2026

**Result:** 11 Nov Tokopedia recovered (5,675 rows, 23 Manalagi products). The Manalagi
daily series now has no gap from 7 to 13 Nov. 346 of 346 tests pass.

## What went wrong on 11 Nov

The laptop was off at 06:00 and 12:00, so the only run was the catch-up at 19:01.
At 19:01 there was no internet (`getaddrinfo failed`, `Could not resolve host`), so
both pulls failed. Then `run.py --tahap transform,load` ran and made two mistakes:

| Source | What happened | Bug |
|---|---|---|
| Blibli | The pull created the empty folder `date=2026-11-11`, then failed. `run.py` read the empty folder and logged **`berhasil`, 0 rows**. | A failed day was reported as a success. |
| Tokopedia | The pull failed before making a folder → `gagal` (correct). But the VPS **did** pull 11 Nov, and `sinkron_vps.py` copied it to `data_lake_vps/` on 12 Nov. | Nothing ever loads `data_lake_vps/`, so the backup was useless. `run.py` also only loads *today*, so a late copy is never picked up. |

## What changed (`data-science/run.py`)

1. **Empty raw data = `gagal`.** If a folder gives 0 rows, the run fails with
   `data mentah kosong: <folder>` instead of saying `berhasil`.
2. **VPS backup.** If the laptop folder has no `_SUKSES` marker but the VPS copy does,
   the VPS copy is loaded. The VPS runs older code without variant pages (`halaman/`),
   so that day is recorded as **`sebagian`** with the message
   `data dari data_lake_vps (tanpa halaman varian)`.
3. **Catch-up.** `run.py` without `--tanggal` (what Task Scheduler runs) first loads
   every past date that has a `_SUKSES` folder (laptop or VPS) but no loaded run yet,
   then today. It never goes before the warehouse start dates (Blibli 7 Nov,
   Tokopedia 8 Nov), so your 9 Nov "complete dates only" decision still holds.
   With `--tanggal` it behaves exactly as before. *(Changed 20 Nov: `--tanggal` also uses the
   VPS copy now; see the 20 Nov section.)*

Task Scheduler needs no change: it already runs `run.py --tahap transform,load`.

Tests added in `tests/test_pipeline.py`: empty folder → `gagal`, VPS used when the
laptop failed, laptop wins over VPS, missed dates get loaded, no catch-up before the
start dates. `test_baca_argumen_bawaan` now expects `tanggal is None` (= today + catch-up).

## My calls (check these)

1. **I loaded 11 Nov Tokopedia from the VPS even though it lacks variant prices.**
   Every product's default price is there (5,675 of 5,675 rows are `opsi_default`); only
   the extra options of about 23 variant products are missing. The dashboard uses
   `opsi_default` only, so it is not affected. To undo:
   `DELETE FROM fakta_harga WHERE sumber='tokopedia' AND tanggal='2026-11-11'`.
2. **I left the old wrong row in `pipeline_runs`** (Blibli, 11 Nov, `berhasil`, 0 rows)
   because it is a history log. Filter it with `baris_dimuat > 0`, or fix it:
   `UPDATE pipeline_runs SET status='gagal', pesan_galat='data mentah kosong (diperbaiki 13 Nov)' WHERE sumber='blibli' AND tanggal='2026-11-11'`.

## Still lost

- **Blibli 11 Nov**: gone. The VPS does not pull Blibli (Blibli blocks server IPs),
  and a marketplace only shows today's price.

## Not fixed (your decision later)

- **No retry after a failed run.** If the one run of the day fails (no internet), nothing
  tries again until tomorrow. A third trigger (for example 18:00) would give a second chance.
- **The VPS runs old code** (no variant pages). Updating it would make VPS backups complete.

---

# Pipeline fix — 14 Nov 2026: city per day

**Result:** each price row now keeps its own day's city. Ranch Market's Manalagi shows
Surabaya (was Jakarta Selatan), and Segari's and BlibliFresh's show Bekasi (were Jakarta Utara).
Prices, medians and indexes did not change. 376 of 376 tests pass. Commit `21fdf47`.

## What went wrong

The 16:15 push on 14 Nov resent 7 dates instead of 1. Only `kota` had changed (16 rows).

| Cause | Detail |
|---|---|
| City was stored per **shop** | `dim_toko` keeps one row per shop with the latest value (SCD type 1), and `v_produk` took `kota` from it. |
| On Blibli the location belongs to the **product** | It is the warehouse the item ships from. Ranch Market lists items from Surabaya, Jakarta Pusat, Jakarta Selatan and Malang on the same day. |
| So the city flipped | The shop's city became whichever of its items happened to come last that day. Every flip rewrote all past dates of that shop and resent them to Supabase. |

## What changed

1. **`fakta_harga.kota`** (`transform/model.py`): the city is stored on every price row.
2. **Old warehouses get the column automatically** (`load/duckdb_loader.py`, `_tambah_kolom_baru`
   in `siapkan`). It stays empty until a date is reloaded.
3. **`v_produk.kota` = the row's own city**, or the shop's city when the row is still empty
   (rows loaded before this fix).
4. 4 new tests: city per row in the model, per-day city in `v_produk`, fallback for empty
   rows, and adding the column to an old warehouse.

## How it was applied

1. Backup: `warehouse/harga_buah.sebelum-kota-2026-11-14.duckdb`.
2. Reloaded 7–14 Nov (14 runs, 0 failed, row counts unchanged: 13,108 Blibli,
   39,134 Tokopedia). 11 Nov Tokopedia came from the VPS copy again (`sebagian`).
3. `kirim_supabase.py --coba` → 7 dates; push → 192 rows, 22 daily rows; the next `--coba` → 0 dates.
4. Read back from production: Ranch Market Surabaya 7/7, Segari Bekasi 6/6.

## Not fixed

- **`region`** (jabodetabek / jawa_lain / luar_jawa) still comes from the shop's latest city in
  `dim_toko`. Fix it before any analysis by region. The planned region filter
  (`docs/superpowers/specs/2026-11-14-filter-wilayah-design.md`) uses province and city codes
  instead.

---

# Change — 14 Nov 2026: region codes (filter wilayah, data side)

**Result:** every price row has an official kabupaten/kota and province code (Kepmendagri 2025).
147 of 147 city names in the warehouse match; 0 rows quarantined by the new check I. The
dashboard's daily table is now computed per region (21 regions so far); its `semua` rows are
identical to what production holds (22 of 22). Design:
`docs/superpowers/specs/2026-11-14-filter-wilayah-design.md`.

## What changed

1. `referensi/wilayah_kabkota.csv` (514 kab/kota, 38 provinces, from cahyadsn/wilayah, MIT) and
   `transform/wilayah.py` (name matching, Jabodetabek group, search keywords).
2. `fakta_harga.kabkota_kode`, `fakta_harga.provinsi_kode`; check I copies an unknown city to
   `produk_karantina` and still loads the row.
3. `dashboard_manalagi.hitung()`: `harian` per (wilayah, pasar); `daftar_wilayah()` for the web's
   search box.
4. `kirim_supabase.py`: new columns, the `KIRIM_PER_WILAYAH` switch (**off**), and an old-column
   snapshot now means "send everything" instead of a crash.
5. Supabase migration `20261115000000_wilayah_pasar.sql` (applied locally; **not yet in
   production**).

## How it was applied

1. Backup: `warehouse/harga_buah.sebelum-wilayah-2026-11-14.duckdb`.
2. Reloaded 7–14 Nov: 0 failed runs, row counts unchanged (13,108 Blibli, 39,134 Tokopedia).
3. Local Supabase: migration + pgTAP 50/50; push with the switch on → 8 dates, 318 daily rows,
   49 region-list rows. Production: `--coba` only.

## Still to do (in this order)

1. Run the migration in the **supabase.com** dashboard.
2. Web: read `.eq("wilayah", "semua")` by default, add the search box; deploy.
3. Set `KIRIM_PER_WILAYAH = True`, commit, run `python kirim_supabase.py --semua` once.

Until step 3 the scheduled run resends all dates once (the production snapshot has the old
columns); the new columns are ignored by production until step 1.

---

# Pipeline fix — 20 Nov 2026: partial pull loaded, VPS copy skipped

**Result:** 16 Nov Tokopedia reloaded from the VPS copy: **3,936 → 5,680 rows** (15 Nov had
5,592, 17 Nov had 5,569). Production updated: 362 → 366 spike rows, 40 daily rows. 416 of 416
tests pass. Commit `67ea945`.

## What went wrong on 16 Nov

The laptop lost internet around 09:00–12:30 (`Could not resolve host`).

| Step | What happened | Bug |
|---|---|---|
| `tarik_harian.py` | Tokopedia stopped at page 68 of 100 → status `sebagian`, no `_SUKSES` marker. | None: correct. |
| `run.py` (11:09, 12:15) | Loaded the partial laptop folder: **`berhasil`, 3,936 rows**. | A partial pull counted as a full day. |
| `sinkron_vps.py`, `kirim_supabase.py` | Failed (no internet), then recovered on 17 Nov. | None. |
| Catch-up on 17 Nov | The full VPS copy (100 pages, `_SUKSES`) arrived, but 16 Nov already had a loaded run, so it was skipped. | The complete copy was never used. |

## What changed (`data-science/run.py`)

1. **Catch-up reloads from the VPS copy.** When the laptop folder has no `_SUKSES` but the VPS
   copy does, the date only counts as loaded if a run loaded it **from the VPS copy**
   (`pesan_galat` starts with `data dari data_lake_vps`). Otherwise the next scheduled run
   reloads it.
2. **`--tanggal` uses the VPS copy too.** Before, `python run.py --tanggal X` never looked at
   `data_lake_vps/`, so a manual reload would have read the partial laptop folder again.

Tests: `test_harian_memuat_ulang_dari_vps_kalau_yang_dimuat_tarikan_laptop_sebagian`,
`test_tanggal_manual_memakai_salinan_vps` (both failed before the fix). On the real warehouse
the new rule flags no other date.

## How it was applied

1. Backups in `data-science/data_lake/cadangan/` (ignored by git):
   `tokopedia_date=2026-11-16_sebagian/` (the 68-page laptop folder) and
   `harga_buah.sebelum-16nov-ulang.duckdb` (the warehouse before the reload).
2. Reloaded 16 Nov Tokopedia from `data_lake_vps/` → `sebagian`,
   `data dari data_lake_vps (tanpa halaman varian)`, 5,680 rows loaded, 6 quarantined.
3. `kirim_supabase.py --coba` → only 16 Nov changes; then `kirim_supabase.py` to **production**
   (with the user's OK); `--coba` afterwards → 0 dates waiting.

To undo: copy the warehouse backup over `warehouse/harga_buah.duckdb`, then run
`python kirim_supabase.py`.

## Still open

- **No retry after a failed run** (from 13 Nov): both 16 Nov runs fell inside the outage.
- **The VPS runs old code** (no variant pages), so VPS backups are always `sebagian`. The VPS
  rental ends around 27 Nov.
