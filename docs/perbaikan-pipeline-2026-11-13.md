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
   With `--tanggal` it behaves exactly as before.

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
