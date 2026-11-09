"""Validasi Pandera + pemisahan karantina (spec bagian 6).

`pisahkan(df, Skema, sumber)` → `(lolos, karantina)`:
- baris yang gagal cek tingkat baris → karantina (tidak masuk `lolos`);
- baris `berat_dikali = true` (cek H) → **disalin** ke karantina, tetap lolos;
- kegagalan tingkat skema (kolom hilang, tipe salah) → `SchemaErrors` dilempar,
  karena itu tanda kode atau bentuk data berubah, bukan baris yang buruk.

Cek yang membandingkan kolom (A–G) dilewati kalau salah satu kolomnya NULL.
"""
from datetime import date

import pandera.polars as pa
import polars as pl

SUMBER = ["blibli", "tokopedia"]

KOLOM_KARANTINA: dict[str, pl.DataType] = {
    "sumber": pl.Utf8,
    "tanggal": pl.Date,
    "produk_id": pl.Utf8,
    "data": pl.Utf8,     # baris asli sebagai JSON
    "alasan": pl.Utf8,   # "<kolom>: <cek>" atau nama cek, dipisah "; "
}

CEK_H = "cek_H_berat_dikali"


def _lewati_null(syarat: pl.Expr) -> pl.Expr:
    """NULL di kolom yang dibandingkan → cek dilewati (dianggap lolos)."""
    return syarat.fill_null(True)


def _hasil(data: pa.PolarsData, syarat: pl.Expr) -> pl.LazyFrame:
    return data.lazyframe.select(_lewati_null(syarat).alias("lolos"))


def _diskon_cocok(diskon: str, harga: str) -> pl.Expr:
    """`diskon` berbeda ≤ 1 poin dari (1 − harga/harga_coret) × 100."""
    hitung = (1 - pl.col(harga) / pl.col("harga_coret")) * 100
    return (pl.col(diskon) - hitung).abs() <= 1


# --- lapisan 1 -------------------------------------------------------------

class _SkemaLapisan1(pa.DataFrameModel):
    tanggal: date = pa.Field(nullable=False)
    produk_id: str = pa.Field(nullable=False)
    nama: str = pa.Field(nullable=False)
    harga: int = pa.Field(gt=0, nullable=False)
    rating: float = pa.Field(ge=0, le=5, nullable=True)
    diskon_persen: int = pa.Field(ge=0, le=100, nullable=True)


class SkemaBlibli(_SkemaLapisan1):
    class Config:
        unique = ["item_sku", "tanggal"]

    @pa.dataframe_check
    def cek_A_harga_urut(cls, data: pa.PolarsData) -> pl.LazyFrame:
        """harga_voucher < harga ≤ harga_coret."""
        return data.lazyframe.select(
            (_lewati_null(pl.col("harga_voucher") < pl.col("harga"))
             & _lewati_null(pl.col("harga") <= pl.col("harga_coret"))).alias("lolos")
        )

    @pa.dataframe_check
    def cek_B_diskon(cls, data: pa.PolarsData) -> pl.LazyFrame:
        return _hasil(data, _diskon_cocok("diskon_persen", "harga"))

    @pa.dataframe_check
    def cek_D_coret_voucher(cls, data: pa.PolarsData) -> pl.LazyFrame:
        return _hasil(data, pl.col("harga_coret_voucher") == pl.col("harga_coret"))

    @pa.dataframe_check
    def cek_E_diskon_voucher(cls, data: pa.PolarsData) -> pl.LazyFrame:
        return _hasil(data, _diskon_cocok("diskon_voucher_persen", "harga_voucher"))

    @pa.dataframe_check
    def cek_F_kampanye(cls, data: pa.PolarsData) -> pl.LazyFrame:
        """harga_sebelum_kampanye ≥ harga; berbeda hanya kalau kampanye terisi."""
        sebelum, harga = pl.col("harga_sebelum_kampanye"), pl.col("harga")
        return data.lazyframe.select(
            (_lewati_null(sebelum >= harga)
             & _lewati_null((sebelum == harga) | pl.col("kampanye").is_not_null())).alias("lolos")
        )

    @pa.dataframe_check
    def cek_G_sku_sama_id(cls, data: pa.PolarsData) -> pl.LazyFrame:
        return _hasil(data, pl.col("sku") == pl.col("produk_id"))


class SkemaTokopedia(_SkemaLapisan1):
    class Config:
        unique = ["produk_id", "tanggal"]


# --- lapisan 2 (star schema, Task 7) ---------------------------------------

class SkemaFakta(pa.DataFrameModel):
    tanggal: date = pa.Field(nullable=False)
    sumber: str = pa.Field(isin=SUMBER)
    produk_key: str = pa.Field(nullable=False)
    toko_key: str = pa.Field(nullable=False)
    harga: int = pa.Field(gt=0, nullable=False)
    # 13 #5 (9 Nov): 2.000–2.000.000/kg; anggur Nagano, persimmon Korea ±Rp4 jt/kg tetap asli
    harga_per_kg: int = pa.Field(in_range={"min_value": 2_000, "max_value": 2_000_000}, nullable=True)


class SkemaDimProduk(pa.DataFrameModel):
    produk_key: str = pa.Field(unique=True)
    sumber: str = pa.Field(isin=SUMBER)


class SkemaDimToko(pa.DataFrameModel):
    toko_key: str = pa.Field(unique=True)
    sumber: str = pa.Field(isin=SUMBER)


# --- pemisahan -------------------------------------------------------------

_BARIS = "_baris"
_ALASAN_KOSONG = pl.DataFrame(schema={_BARIS: pl.UInt32, "alasan": pl.Utf8})


def _alasan_skema(df: pl.DataFrame, skema: type[pa.DataFrameModel]) -> pl.DataFrame:
    """Satu baris per (nomor baris, alasan gagal). Kegagalan tingkat skema dilempar."""
    try:
        skema.validate(df, lazy=True)
        return _ALASAN_KOSONG
    except pa.errors.SchemaErrors as galat:
        kasus = galat.failure_cases
        if kasus["index"].null_count():
            raise
        return kasus.select(
            pl.col("index").cast(pl.UInt32).alias(_BARIS),
            pl.when(pl.col("schema_context") == "Column")
            .then(pl.col("column") + ": " + pl.col("check"))
            .otherwise(pl.col("check"))
            .alias("alasan"),
        )


def _kolom_atau_null(df: pl.DataFrame, kolom: str) -> pl.Expr:
    return pl.col(kolom) if kolom in df.columns else pl.lit(None)


def pisahkan(
    df: pl.DataFrame, skema: type[pa.DataFrameModel], sumber: str
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Validasi `df` dengan `skema` → `(lolos, karantina)` (spec 6.2)."""
    alasan = _alasan_skema(df, skema)
    gagal = alasan[_BARIS].unique()

    baris = df.with_row_index(_BARIS)
    if "berat_dikali" in df.columns:
        dikali = baris.filter(pl.col("berat_dikali").fill_null(False))
        alasan = pl.concat([alasan, dikali.select(_BARIS, pl.lit(CEK_H).alias("alasan"))])

    karantina = (
        alasan.group_by(_BARIS, maintain_order=True)
        .agg(pl.col("alasan").unique(maintain_order=True).str.join("; "))
        .sort(_BARIS)
        .join(baris.select(_BARIS, pl.struct(df.columns).struct.json_encode().alias("data"),
                           _kolom_atau_null(df, "tanggal").alias("tanggal"),
                           _kolom_atau_null(df, "produk_id").alias("produk_id")),
              on=_BARIS, how="left")
        .with_columns(pl.lit(sumber).alias("sumber"))
        .select(pl.col(k).cast(t) for k, t in KOLOM_KARANTINA.items())
    )
    lolos = baris.filter(~pl.col(_BARIS).is_in(gagal.implode())).drop(_BARIS)
    return lolos, karantina
