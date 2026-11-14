"""Hitungan dashboard harga Mangga Manalagi dalam SQL DuckDB: satu-satunya salinan SQL-nya.

Dipakai `dashboard_contoh.ipynb` (prototipe grafik) dan `kirim_supabase.py` (kirim ke Supabase).
Aturan dan alasannya: docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md.

    with duckdb.connect("warehouse/harga_buah.duckdb", read_only=True) as con:
        baris, harian = hitung(con)

- `baris`: satu baris per produk per hari (16 kolom).
- `harian`: satu baris per tanggal per pasar (`semua`, `blibli`, `tokopedia`).
Semua dihitung pada seluruh data; penyaringan rentang waktu dilakukan sesudahnya.
"""
from datetime import date

import duckdb
import polars as pl

from run import MULAI_GUDANG

# Detektor lonjakan: tebakan awal, setel ulang setelah ±1 bulan data
JENDELA_HARI = 7         # jendela pembanding, hari kalender, hari ini tidak ikut
AMBANG_TOKO = 0.10       # lonjakan satu produk
AMBANG_PASAR = 0.05      # lonjakan median semua produk
MIN_DATA = 3             # minimal hari berdata dalam jendela sebelum produk dinilai
MAKS_JEDA_HARI = 30      # indeks berantai: pengamatan sebelumnya paling lama sekian hari


def _sql_sumber(mulai: dict[str, date]) -> str:
    return f"""
SELECT tanggal, sumber, produk_key, nama, nama_toko, kota,
       harga, berat_gram, harga_per_kg, terjual_min
FROM v_produk
WHERE jenis_buah = 'mangga' AND nama ILIKE '%manalagi%'
  AND opsi_default AND NOT olahan AND harga_per_kg IS NOT NULL
  AND ((sumber = 'blibli'    AND tanggal >= DATE '{mulai['blibli']}')
    OR (sumber = 'tokopedia' AND tanggal >= DATE '{mulai['tokopedia']}'))
"""


def _sql_baris(mulai: dict[str, date]) -> str:
    """Langkah 1a: tabel `baris` (satu baris per produk per hari)."""
    return f"""
CREATE TEMP TABLE baris AS
WITH df AS ({_sql_sumber(mulai)}),
w AS (
    SELECT *,
        lag(harga_per_kg) OVER per_produk                   AS harga_sebelumnya,
        date_diff('day', lag(tanggal) OVER per_produk, tanggal) AS jeda_hari,
        median(harga_per_kg) OVER jendela                   AS median_jendela,
        count(*) OVER jendela                               AS jumlah_jendela
    FROM df
    WINDOW per_produk AS (PARTITION BY produk_key ORDER BY tanggal),
           -- {JENDELA_HARI} hari kalender sebelum hari ini; hari ini tidak ikut
           jendela AS (PARTITION BY produk_key ORDER BY tanggal
                       RANGE BETWEEN INTERVAL {JENDELA_HARI} DAYS PRECEDING
                                 AND INTERVAL 1 DAY PRECEDING)
)
SELECT * EXCLUDE (jeda_hari),
    CASE WHEN jeda_hari <= {MAKS_JEDA_HARI}
         THEN harga_per_kg / harga_sebelumnya END           AS faktor,
    CASE WHEN jumlah_jendela >= {MIN_DATA}
         THEN harga_per_kg / median_jendela END             AS rasio_jendela,
    coalesce(jumlah_jendela >= {MIN_DATA}
             AND abs(harga_per_kg / median_jendela - 1) >= {AMBANG_TOKO}
             AND harga_per_kg <> harga_sebelumnya, false)   AS lonjak_toko
FROM w
"""


_SQL_HARIAN = f"""
CREATE TEMP TABLE harian AS
WITH b AS (
    SELECT 'semua' AS pasar, * FROM baris
    UNION ALL
    SELECT sumber AS pasar, * FROM baris
),
h AS (
    SELECT pasar, tanggal,
        count(*)                                            AS jumlah_produk,
        median(harga_per_kg)                                AS median,
        avg(harga_per_kg)                                   AS rata_rata,
        sum(harga_per_kg * terjual_min) FILTER (WHERE terjual_min > 0)
          / sum(terjual_min) FILTER (WHERE terjual_min > 0) AS tertimbang,
        median(faktor)                                      AS faktor_median,
        count(rasio_jendela)                                AS dinilai,
        median(rasio_jendela)                               AS median_rasio,
        count(*) FILTER (WHERE lonjak_toko AND rasio_jendela > 1) AS naik,
        count(*) FILTER (WHERE lonjak_toko AND rasio_jendela < 1) AS turun
    FROM b
    GROUP BY pasar, tanggal
),
f AS (
    SELECT *,
        -- hari pertama tiap pasar = 1; hari tanpa produk berpasangan = 1 (indeks tidak bergerak)
        CASE WHEN tanggal = min(tanggal) OVER (PARTITION BY pasar) THEN 1.0
             ELSE coalesce(faktor_median, 1.0) END          AS faktor_hari,
        first_value(median) OVER (PARTITION BY pasar ORDER BY tanggal) AS median_awal
    FROM h
)
SELECT * EXCLUDE (faktor_hari, median_awal),
    -- perkalian berantai: exp(jumlah ln(faktor)) = faktor_1 × faktor_2 × ...
    median_awal * exp(sum(ln(faktor_hari)) OVER (PARTITION BY pasar ORDER BY tanggal)) AS indeks_berantai,
    coalesce(abs(median_rasio - 1) >= {AMBANG_PASAR}, false) AS lonjak_pasar
FROM f
"""


def hitung(con: duckdb.DuckDBPyConnection,
           mulai: dict[str, date] = MULAI_GUDANG) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(baris, harian) dari `v_produk`. Tabel temp: boleh di koneksi read_only."""
    con.execute("DROP TABLE IF EXISTS temp.harian; DROP TABLE IF EXISTS temp.baris")
    con.execute(_sql_baris(mulai))
    con.execute(_SQL_HARIAN)
    baris = con.sql("FROM baris ORDER BY produk_key, tanggal").pl()
    harian = con.sql("FROM harian ORDER BY pasar, tanggal").pl()
    return baris, harian
