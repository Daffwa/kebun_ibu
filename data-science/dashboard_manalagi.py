"""Hitungan dashboard harga Mangga Manalagi dalam SQL DuckDB: satu-satunya salinan SQL-nya.

Dipakai `dashboard_contoh.ipynb` (prototipe grafik) dan `kirim_supabase.py` (kirim ke Supabase).
Aturan dan alasannya: docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md.

    with duckdb.connect("warehouse/harga_buah.duckdb", read_only=True) as con:
        baris, harian = hitung(con)

- `baris`: satu baris per produk per hari (18 kolom, termasuk kode wilayah).
- `harian`: satu baris per tanggal per pasar (`semua`, `blibli`, `tokopedia`) per wilayah
  (`semua`, kelompok, provinsi, kab/kota; transform/wilayah.py). Produk tanpa kode wilayah hanya
  ikut `semua`. Baris `wilayah = 'semua'` sama dengan `harian` sebelum ada wilayah.
- `daftar_wilayah(baris)`: wilayah yang punya data, untuk kotak cari di web.
Semua dihitung pada seluruh data; penyaringan rentang waktu dilakukan sesudahnya.
"""
from datetime import date

import duckdb
import polars as pl

from run import MULAI_GUDANG
from transform import wilayah

# Detektor lonjakan: tebakan awal, setel ulang setelah ±1 bulan data
JENDELA_HARI = 7         # jendela pembanding, hari kalender, hari ini tidak ikut
AMBANG_TOKO = 0.10       # lonjakan satu produk
AMBANG_PASAR = 0.05      # lonjakan median semua produk
MIN_DATA = 3             # minimal hari berdata dalam jendela sebelum produk dinilai
MAKS_JEDA_HARI = 30      # indeks berantai: pengamatan sebelumnya paling lama sekian hari


def _sql_sumber(mulai: dict[str, date]) -> str:
    return f"""
SELECT tanggal, sumber, produk_key, nama, nama_toko, kota, kabkota_kode, provinsi_kode,
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
WITH p AS (
    SELECT 'semua' AS pasar, * FROM baris
    UNION ALL
    SELECT sumber AS pasar, * FROM baris
),
b AS (   -- setiap baris sekali untuk `semua`, sekali untuk setiap wilayah kab/kota-nya
    SELECT 'semua' AS wilayah, * FROM p
    UNION ALL
    SELECT a.wilayah, p.* FROM p JOIN anggota a ON a.kabkota_kode = p.kabkota_kode
),
h AS (
    SELECT wilayah, pasar, tanggal,
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
    GROUP BY wilayah, pasar, tanggal
),
f AS (
    SELECT *,
        -- hari pertama tiap pasar = 1; hari tanpa produk berpasangan = 1 (indeks tidak bergerak)
        CASE WHEN tanggal = min(tanggal) OVER (PARTITION BY wilayah, pasar) THEN 1.0
             ELSE coalesce(faktor_median, 1.0) END          AS faktor_hari,
        first_value(median) OVER (PARTITION BY wilayah, pasar ORDER BY tanggal) AS median_awal
    FROM h
)
SELECT * EXCLUDE (faktor_hari, median_awal),
    -- perkalian berantai: exp(jumlah ln(faktor)) = faktor_1 × faktor_2 × ...
    median_awal * exp(sum(ln(faktor_hari)) OVER (PARTITION BY wilayah, pasar ORDER BY tanggal))
        AS indeks_berantai,
    coalesce(abs(median_rasio - 1) >= {AMBANG_PASAR}, false) AS lonjak_pasar
FROM f
"""


def hitung(con: duckdb.DuckDBPyConnection,
           mulai: dict[str, date] = MULAI_GUDANG) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(baris, harian) dari `v_produk`. Tabel temp: boleh di koneksi read_only."""
    con.execute("DROP TABLE IF EXISTS temp.harian; DROP TABLE IF EXISTS temp.baris")
    con.execute(_sql_baris(mulai))
    con.register("anggota", wilayah.anggota())
    try:
        con.execute(_SQL_HARIAN)
    finally:
        con.unregister("anggota")
    baris = con.sql("FROM baris ORDER BY produk_key, tanggal").pl()
    harian = con.sql("FROM harian ORDER BY wilayah, pasar, tanggal").pl()
    return baris, harian


KOLOM_DAFTAR = ["wilayah", "pasar", "nama", "tingkat", "provinsi_kode", "kata_kunci", "jumlah_toko"]


def _nama_wilayah() -> pl.DataFrame:
    """wilayah, nama, tingkat, provinsi_kode, kata_kunci untuk setiap kelompok, provinsi, kab/kota."""
    k = wilayah.kabkota()
    teks = pl.Utf8
    kabkota = k.select(wilayah="kode", nama="nama", tingkat=pl.lit("kabkota"),
                       provinsi_kode="provinsi_kode", kata_kunci=pl.lit(None, teks))
    provinsi = (k.select(wilayah="provinsi_kode", nama="provinsi").unique("wilayah")
                .with_columns(tingkat=pl.lit("provinsi"), provinsi_kode=pl.lit(None, teks),
                              kata_kunci=pl.col("wilayah").replace_strict(
                                  wilayah.KATA_KUNCI_PROVINSI, default=None, return_dtype=teks)))
    kelompok = pl.DataFrame(
        [(kunci, nama, "kelompok", None, None) for kunci, (nama, _) in wilayah.KELOMPOK.items()],
        schema={c: teks for c in KOLOM_DAFTAR[:1] + KOLOM_DAFTAR[2:6]}, orient="row")
    return pl.concat([kabkota, provinsi.select(kabkota.columns), kelompok])


def daftar_wilayah(baris: pl.DataFrame) -> pl.DataFrame:
    """Satu baris per (wilayah, pasar) yang punya data; jumlah_toko sepanjang seluruh `baris`."""
    b = (baris.select("sumber", "nama_toko", "kabkota_kode").drop_nulls("kabkota_kode")
         .join(wilayah.anggota(), on="kabkota_kode"))
    per_pasar = pl.concat([b.with_columns(pasar=pl.lit("semua")), b.with_columns(pasar=pl.col("sumber"))])
    jumlah = per_pasar.group_by("wilayah", "pasar").agg(
        jumlah_toko=pl.col("nama_toko").drop_nulls().n_unique().cast(pl.Int64))
    return jumlah.join(_nama_wilayah(), on="wilayah").select(KOLOM_DAFTAR).sort("wilayah", "pasar")
