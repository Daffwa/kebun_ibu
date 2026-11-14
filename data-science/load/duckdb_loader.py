"""Lapisan 1 + karantina + star schema → DuckDB (spec bagian 7).

`muat` aman diulang (idempoten): dalam satu transaksi, baris lama untuk
(sumber, tanggal) itu dihapus lalu diganti; dimensi di-upsert per kunci
(SCD tipe 1). Kalau ada galat di tengah, semuanya dibatalkan.
"""
from datetime import date

import duckdb
import polars as pl

from transform.blibli import KOLOM_BLIBLI
from transform.model import (
    KOLOM_DIM_PRODUK,
    KOLOM_DIM_TANGGAL,
    KOLOM_DIM_TOKO,
    KOLOM_FAKTA,
    Bintang,
)
from transform.skema import KOLOM_KARANTINA
from transform.tokopedia import KOLOM_TOKOPEDIA

KOLOM_RUN: dict[str, pl.DataType] = {
    "run_id": pl.Utf8,
    "mulai": pl.Datetime("us"),
    "selesai": pl.Datetime("us"),
    "sumber": pl.Utf8,
    "tanggal": pl.Date,
    "halaman_ditarik": pl.Int64,
    "baris_mentah": pl.Int64,
    "baris_dimuat": pl.Int64,
    "baris_karantina": pl.Int64,
    "status": pl.Utf8,          # berhasil / sebagian / gagal
    "pesan_galat": pl.Utf8,
}

# nama tabel → (kolom, primary key)
_SKEMA: dict[str, tuple[dict[str, pl.DataType], tuple[str, ...]]] = {
    "blibli_produk": (KOLOM_BLIBLI, ()),
    "tokopedia_produk": (KOLOM_TOKOPEDIA, ()),
    "produk_karantina": (KOLOM_KARANTINA, ()),
    "fakta_harga": (KOLOM_FAKTA, ("tanggal", "produk_key", "item_sku")),   # diubah 7 Nov: per opsi
    "dim_produk": (KOLOM_DIM_PRODUK, ("produk_key",)),
    "dim_toko": (KOLOM_DIM_TOKO, ("toko_key",)),
    "dim_tanggal": (KOLOM_DIM_TANGGAL, ("tanggal",)),
    "pipeline_runs": (KOLOM_RUN, ("run_id",)),
}
TABEL = list(_SKEMA)

# Keputusan 9 Nov (opsi A, terbatas): kartu Tokopedia tanpa induk boleh memakai induk dari
# tanggal lain HANYA sampai tanggal ini (sebelum halaman produk ditarik setiap hari).
# Tanggal sesudahnya hanya memakai halaman produknya sendiri.
BATAS_PETA_INDUK = date(2026, 11, 8)

_CEK_TAMBAHAN = {"pipeline_runs": "CHECK (status IN ('berhasil', 'sebagian', 'gagal'))"}
_DIMENSI = ("dim_produk", "dim_toko", "dim_tanggal")
_LAPISAN1 = {"blibli": "blibli_produk", "tokopedia": "tokopedia_produk"}

_TIPE_SQL = [
    (pl.Date, "DATE"), (pl.Datetime, "TIMESTAMP"), (pl.Utf8, "VARCHAR"), (pl.Boolean, "BOOLEAN"),
    (pl.Int8, "TINYINT"), (pl.Int32, "INTEGER"), (pl.Int64, "BIGINT"), (pl.Float64, "DOUBLE"),
]


def _tipe_sql(tipe: pl.DataType) -> str:
    for tipe_pl, sql in _TIPE_SQL:
        if tipe == tipe_pl:
            return sql
    raise TypeError(f"tipe Polars belum dipetakan ke DuckDB: {tipe}")


def _buat_tabel(nama: str) -> str:
    kolom, pk = _SKEMA[nama]
    isi = [f"{k} {_tipe_sql(t)}" for k, t in kolom.items()]
    if pk:
        isi.append(f"PRIMARY KEY ({', '.join(pk)})")
    if nama in _CEK_TAMBAHAN:
        isi.append(_CEK_TAMBAHAN[nama])
    return f"CREATE TABLE IF NOT EXISTS {nama} (\n    " + ",\n    ".join(isi) + "\n)"


def _kolom_deskriptif(nama: str) -> list[str]:
    """Kolom dimensi selain kunci, `sumber` (sudah ada di fakta), dan `tanggal_terakhir`."""
    kolom, pk = _SKEMA[nama]
    return [k for k in kolom if k not in pk and k not in ("sumber", "tanggal_terakhir")]


def _view_produk() -> str:
    """Fakta + kolom deskriptif dimensi. Kolom yang ada di fakta dan dimensi (kota) diambil dari
    fakta; kalau kosong (baris dimuat sebelum 14 Nov), dari dimensi."""
    fakta = _SKEMA["fakta_harga"][0]
    pilih, ganda = [], []
    for alias, nama in (("p", "dim_produk"), ("t", "dim_toko"), ("d", "dim_tanggal")):
        for k in _kolom_deskriptif(nama):
            if k in fakta:
                ganda.append(k)
                pilih.append(f"COALESCE(f.{k}, {alias}.{k}) AS {k}")
            else:
                pilih.append(f"{alias}.{k}")
    semua_fakta = f"f.* EXCLUDE ({', '.join(ganda)})" if ganda else "f.*"
    return f"""CREATE OR REPLACE VIEW v_produk AS
SELECT {', '.join([semua_fakta, *pilih])}
FROM fakta_harga f
LEFT JOIN dim_produk p USING (produk_key)
LEFT JOIN dim_toko t USING (toko_key)
LEFT JOIN dim_tanggal d USING (tanggal)"""


# Cek C (spec 6.1): opsi default berbeda dari tanggal sebelumnya. Tanda saja, bukan karantina.
_VIEW_OPSI_BERUBAH = """CREATE OR REPLACE VIEW v_opsi_berubah AS
WITH urut AS (
    SELECT sumber, tanggal, produk_key, item_sku,
           LAG(tanggal) OVER w AS tanggal_sebelumnya,
           LAG(item_sku) OVER w AS item_sku_sebelumnya
    FROM fakta_harga
    WHERE opsi_default
    WINDOW w AS (PARTITION BY produk_key ORDER BY tanggal)
)
SELECT u.sumber, u.tanggal, u.tanggal_sebelumnya, p.produk_id, p.nama,
       u.item_sku_sebelumnya, u.item_sku
FROM urut u
LEFT JOIN dim_produk p USING (produk_key)
WHERE u.item_sku_sebelumnya IS NOT NULL AND u.item_sku <> u.item_sku_sebelumnya"""


def _tambah_kolom_baru(con: duckdb.DuckDBPyConnection, nama: str) -> None:
    """Tabel dari gudang versi lama: kolom yang belum ada ditambahkan, isinya NULL sampai dimuat ulang."""
    ada = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ?", [nama]).fetchall()}
    for k, t in _SKEMA[nama][0].items():
        if k not in ada:
            con.execute(f"ALTER TABLE {nama} ADD COLUMN {k} {_tipe_sql(t)}")


def siapkan(con: duckdb.DuckDBPyConnection) -> None:
    """Buat semua tabel (kalau belum ada) dan view. Aman dipanggil berkali-kali."""
    for nama in TABEL:
        con.execute(_buat_tabel(nama))
        _tambah_kolom_baru(con, nama)
    con.execute(_view_produk())
    con.execute(_VIEW_OPSI_BERUBAH)


def _sisip(con: duckdb.DuckDBPyConnection, nama: str, df: pl.DataFrame) -> None:
    kolom, pk = _SKEMA[nama]
    daftar = ", ".join(kolom)
    sql = f"INSERT INTO {nama} ({daftar}) SELECT {daftar} FROM _masuk"
    if nama in _DIMENSI:
        ubah = ", ".join(f"{k} = excluded.{k}" for k in kolom if k not in pk)
        sql += f" ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {ubah}"
        if "tanggal_terakhir" in kolom:
            # keputusan 9 Nov: muat ulang tanggal lama tidak mengembalikan nama lama
            sql += f" WHERE excluded.tanggal_terakhir >= {nama}.tanggal_terakhir"
    con.register("_masuk", df)
    try:
        con.execute(sql)
    finally:
        con.unregister("_masuk")


def _cek_milik(nama: str, df: pl.DataFrame, sumber: str, tanggal: date) -> None:
    """Semua baris harus milik (sumber, tanggal) ini; kalau tidak, DELETE tidak akan menghapusnya."""
    if "tanggal" in df.columns and not (df["tanggal"] == tanggal).fill_null(False).all():
        raise ValueError(f"{nama}: ada baris dengan tanggal selain {tanggal}")
    if "sumber" in df.columns and not (df["sumber"] == sumber).fill_null(False).all():
        raise ValueError(f"{nama}: ada baris dengan sumber selain {sumber!r}")


def muat(
    con: duckdb.DuckDBPyConnection,
    sumber: str,
    tanggal: date,
    lapisan1: pl.DataFrame,
    karantina: pl.DataFrame,
    bintang: Bintang,
) -> None:
    """Ganti semua data (sumber, tanggal) di gudang dalam satu transaksi."""
    if sumber not in _LAPISAN1:
        raise ValueError(f"sumber tidak dikenal: {sumber!r}")
    tabel1 = _LAPISAN1[sumber]
    isi = {
        tabel1: lapisan1,
        # baris yang gagal cek `tanggal` tetap ikut terhapus saat dimuat ulang
        "produk_karantina": karantina.with_columns(pl.col("tanggal").fill_null(tanggal)),
        "dim_produk": bintang.dim_produk,
        "dim_toko": bintang.dim_toko,
        "dim_tanggal": bintang.dim_tanggal,
        "fakta_harga": bintang.fakta_harga,
    }
    for nama, df in isi.items():
        _cek_milik(nama, df, sumber, tanggal)

    con.begin()
    try:
        con.execute(f"DELETE FROM {tabel1} WHERE tanggal = ?", [tanggal])
        for nama in ("fakta_harga", "produk_karantina"):
            con.execute(f"DELETE FROM {nama} WHERE sumber = ? AND tanggal = ?", [sumber, tanggal])
        for nama, df in isi.items():
            _sisip(con, nama, df)
        # produk/toko yang tidak dipakai fakta lagi (mis. kartu yang kini ikut induknya)
        for dim, kunci in (("dim_produk", "produk_key"), ("dim_toko", "toko_key")):
            con.execute(f"DELETE FROM {dim} d WHERE d.sumber = ? AND NOT EXISTS "
                        f"(SELECT 1 FROM fakta_harga f WHERE f.{kunci} = d.{kunci})", [sumber])
        con.commit()
    except BaseException:
        con.rollback()
        raise


def peta_induk(con: duckdb.DuckDBPyConnection, tanggal: date) -> pl.DataFrame | None:
    """Induk Tokopedia yang sudah ada di gudang (`produk_id`, `induk_id`), untuk `bangun`.

    `None` kalau `tanggal` sesudah `BATAS_PETA_INDUK`. Kalau satu kartu punya beberapa
    induk, yang dari tanggal terbaru dipakai.
    """
    if tanggal > BATAS_PETA_INDUK:
        return None
    return con.sql("""
        SELECT produk_id, arg_max(induk_id, tanggal) AS induk_id
        FROM tokopedia_produk
        WHERE induk_id IS NOT NULL
        GROUP BY produk_id
    """).pl()


def catat_run(con: duckdb.DuckDBPyConnection, run: dict) -> None:
    """Satu baris `pipeline_runs`. Kunci yang tidak ada → NULL."""
    asing = set(run) - set(KOLOM_RUN)
    if asing:
        raise ValueError(f"kolom pipeline_runs tidak dikenal: {sorted(asing)}")
    df = pl.DataFrame([{k: run.get(k) for k in KOLOM_RUN}], schema=KOLOM_RUN)
    _sisip(con, "pipeline_runs", df)
