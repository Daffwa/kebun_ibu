"""Tabel lapisan 1 yang sudah lolos validasi → star schema (spec 5.3).

Grain `fakta_harga`: satu opsi produk di satu marketplace pada satu tanggal.
Kunci fakta dihitung langsung dari kolom ID lapisan 1 (bukan join ke
dimensi), jadi toko tanpa kota tidak bisa hilang dari fakta.

Tokopedia (keputusan 9 Nov): opsi-opsi satu produk = satu produk induk
(`induk_id`), seperti Blibli (`produk_id` + `item_sku`). Kalau halaman produk
gagal ditarik di satu tanggal, induknya diambil dari tanggal lain.
"""
import hashlib
from dataclasses import dataclass

import polars as pl

from transform.parser import (
    asal_dari_nama,
    ember_terjual,
    jenis_buah,
    olahan,
    region,
    terjual_dari_label,
)

KOLOM_FAKTA: dict[str, pl.DataType] = {
    "tanggal": pl.Date,
    "produk_key": pl.Utf8,
    "toko_key": pl.Utf8,
    "sumber": pl.Utf8,
    "item_sku": pl.Utf8,
    "opsi_default": pl.Boolean,
    "variant": pl.Utf8,
    "harga": pl.Int64,
    "harga_coret": pl.Int64,
    "diskon_persen": pl.Int64,
    "berat_gram": pl.Int64,
    "sumber_berat": pl.Utf8,
    "jenis_satuan": pl.Utf8,
    "harga_per_kg": pl.Int64,
    "harga_per_buah": pl.Int64,
    "rating": pl.Float64,
    "terjual_min": pl.Int64,
}

_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]   # weekday() 1..7


@dataclass
class Bintang:
    dim_produk: pl.DataFrame
    dim_toko: pl.DataFrame
    dim_tanggal: pl.DataFrame
    fakta_harga: pl.DataFrame


def kunci(sumber: str, id_alami: str | None) -> str:
    """Kunci pengganti: md5 hex dari "<sumber>|<id>"."""
    return hashlib.md5(f"{sumber}|{id_alami or ''}".encode()).hexdigest()


def _kunci(id_alami: str) -> pl.Expr:
    teks = pl.concat_str(pl.col("sumber"), pl.lit("|"), pl.col(id_alami).fill_null(""))
    return teks.map_batches(
        lambda s: pl.Series([hashlib.md5(x.encode()).hexdigest() for x in s], dtype=pl.Utf8),
        return_dtype=pl.Utf8,
    )


def _per_baris(fungsi, kolom: str, tipe: pl.DataType) -> pl.Expr:
    return pl.col(kolom).map_elements(fungsi, return_dtype=tipe, skip_nulls=False)


# --- satu bentuk untuk kedua sumber -------------------------------------------------

_BERSAMA = ["tanggal", "item_sku", "opsi_default", "variant", "nama", "harga", "diskon_persen",
            "berat_gram", "sumber_berat", "jenis_satuan", "jumlah_buah", "rating"]


def _seragam_blibli(df: pl.DataFrame) -> pl.DataFrame:
    kategori = pl.col("kategori").fill_null("")
    return df.select(
        *_BERSAMA,
        "produk_id",
        "harga_coret",
        sumber=pl.lit("blibli"),
        terjual_min=pl.col("total_terjual").map_elements(ember_terjual, return_dtype=pl.Int64),
        toko_id=pl.col("merchant_code"),
        nama_toko=pl.col("penjual"),
        kota=pl.col("lokasi"),
        jenis_toko=pl.when(pl.col("resmi")).then(pl.lit("resmi")).otherwise(pl.lit("biasa")),
        asal=pl.when(kategori.str.contains("Buah Lokal")).then(pl.lit("lokal"))
        .when(kategori.str.contains("Buah Impor")).then(pl.lit("impor"))
        .when(pl.col("kategori_tarik") == "BU-1000190").then(pl.lit("lokal"))
        .when(pl.col("kategori_tarik") == "BU-1000191").then(pl.lit("impor")),
        asal_sumber=pl.lit("label"),
    )


def _seragam_tokopedia(df: pl.DataFrame) -> pl.DataFrame:
    # induk dari tanggal lain untuk kartu yang halaman produknya gagal ditarik
    peta_induk = (
        df.filter(pl.col("induk_id").is_not_null())
        .select("produk_id", induk_lain=pl.col("induk_id"))
        .unique("produk_id", keep="last", maintain_order=True)
    )
    return df.join(peta_induk, on="produk_id", how="left", maintain_order="left").select(
        *[c for c in _BERSAMA if c != "item_sku"],
        item_sku=pl.col("produk_id"),
        produk_id=pl.coalesce("induk_id", "induk_lain", "produk_id"),
        harga_coret=pl.lit(None, pl.Int64),       # 13 #1: harga_asli tidak dipakai di fakta
        sumber=pl.lit("tokopedia"),
        terjual_min=pl.col("terjual_label").map_elements(terjual_dari_label, return_dtype=pl.Int64),
        toko_id=pl.col("toko_id"),
        nama_toko=pl.col("nama_toko"),
        kota=pl.col("kota"),
        jenis_toko=pl.lit("tier_") + pl.col("tier_toko").cast(pl.Utf8),
        asal=pl.lit(None, pl.Utf8),               # dari nama, dihitung di dim_produk
        asal_sumber=pl.lit("aturan"),
    )


# --- dimensi dan fakta ----------------------------------------------------------

def _terakhir(df: pl.DataFrame, kunci_kolom: str) -> pl.DataFrame:
    """SCD tipe 1: satu baris per kunci, tanggal terakhir menang."""
    return df.sort("tanggal", maintain_order=True).unique(kunci_kolom, keep="last", maintain_order=True)


def _dim_produk(semua: pl.DataFrame) -> pl.DataFrame:
    return _terakhir(semua, "produk_key").select(
        "produk_key", "sumber", "produk_id", "nama",
        jenis_buah=_per_baris(jenis_buah, "nama", pl.Utf8),
        asal=pl.coalesce("asal", _per_baris(asal_dari_nama, "nama", pl.Utf8)),
        asal_sumber=pl.col("asal_sumber"),
        olahan=_per_baris(olahan, "nama", pl.Boolean),
    )


def _dim_toko(semua: pl.DataFrame) -> pl.DataFrame:
    return _terakhir(semua, "toko_key").select(
        "toko_key", "sumber", "toko_id", "nama_toko", "kota",
        region=_per_baris(region, "kota", pl.Utf8),
        jenis_toko=pl.col("jenis_toko"),
    )


def _dim_tanggal(semua: pl.DataFrame) -> pl.DataFrame:
    tgl = pl.col("tanggal")
    return semua.select(tgl.unique().sort()).select(
        tgl,
        tahun=tgl.dt.year(),
        bulan=tgl.dt.month(),
        minggu=tgl.dt.week(),
        hari=tgl.dt.weekday().replace_strict(list(range(1, 8)), _HARI, return_dtype=pl.Utf8),
    )


def _fakta(semua: pl.DataFrame) -> pl.DataFrame:
    harga, berat, jumlah = pl.col("harga"), pl.col("berat_gram"), pl.col("jumlah_buah")
    return semua.with_columns(
        harga_per_kg=pl.when((pl.col("jenis_satuan") == "berat") & (berat > 0))
        .then((harga * 1000 / berat).round(0)),
        harga_per_buah=pl.when((pl.col("jenis_satuan") == "jumlah") & (jumlah > 0))
        .then((harga / jumlah).round(0)),
    ).select(pl.col(k).cast(t) for k, t in KOLOM_FAKTA.items())


def bangun(blibli: pl.DataFrame | None, tokopedia: pl.DataFrame | None) -> Bintang:
    """Lapisan 1 (sudah lolos `pisahkan`) dari satu atau dua sumber → star schema."""
    bagian = []
    if blibli is not None:
        bagian.append(_seragam_blibli(blibli))
    if tokopedia is not None:
        bagian.append(_seragam_tokopedia(tokopedia))
    if not bagian:
        raise ValueError("bangun() butuh minimal satu sumber")
    semua = pl.concat(bagian, how="diagonal_relaxed").with_columns(
        produk_key=_kunci("produk_id"),
        toko_key=_kunci("toko_id"),
    )
    return Bintang(
        dim_produk=_dim_produk(semua),
        dim_toko=_dim_toko(semua),
        dim_tanggal=_dim_tanggal(semua),
        fakta_harga=_fakta(semua),
    )
