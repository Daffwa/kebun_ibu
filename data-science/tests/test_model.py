import hashlib
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from transform import blibli, tokopedia
from transform.model import (
    KOLOM_DIM_PRODUK,
    KOLOM_DIM_TANGGAL,
    KOLOM_DIM_TOKO,
    KOLOM_FAKTA,
    Bintang,
    bangun,
    kunci,
)
from transform.skema import SkemaDimProduk, SkemaDimToko, SkemaFakta, pisahkan

FIXTURE = Path(__file__).parent / "fixtures"
TANGGAL = date(2026, 11, 8)


@pytest.fixture(scope="module")
def df_blibli():
    return blibli.ubah(FIXTURE / "blibli" / "date=2026-11-08", TANGGAL)


@pytest.fixture(scope="module")
def df_tokped():
    return tokopedia.ubah(FIXTURE / "tokopedia" / "date=2026-11-08", TANGGAL)


@pytest.fixture(scope="module")
def bintang(df_blibli, df_tokped):
    return bangun(df_blibli, df_tokped)


def fakta_item(bintang, item_sku):
    hasil = bintang.fakta_harga.filter(pl.col("item_sku") == item_sku)
    assert hasil.height == 1, f"{item_sku}: {hasil.height} baris"
    return hasil.row(0, named=True)


def produk(bintang, produk_key):
    hasil = bintang.dim_produk.filter(pl.col("produk_key") == produk_key)
    assert hasil.height == 1
    return hasil.row(0, named=True)


# --- kunci dan bentuk --------------------------------------------------------

def test_kunci_stabil():
    assert kunci("tokopedia", "123") == hashlib.md5(b"tokopedia|123").hexdigest()
    assert kunci("blibli", None) == hashlib.md5(b"blibli|").hexdigest()


def test_kolom_keluaran(bintang):
    assert isinstance(bintang, Bintang)
    assert bintang.fakta_harga.schema == pl.Schema(KOLOM_FAKTA)
    assert bintang.dim_produk.columns == ["produk_key", "sumber", "produk_id", "nama", "jenis_buah",
                                          "asal", "asal_sumber", "olahan", "tanggal_terakhir"]
    assert bintang.dim_toko.columns == ["toko_key", "sumber", "toko_id", "nama_toko", "kota",
                                        "region", "jenis_toko", "tanggal_terakhir"]
    assert bintang.dim_tanggal.columns == ["tanggal", "tahun", "bulan", "minggu", "hari"]


def test_tipe_kolom_dimensi(bintang):
    assert bintang.dim_produk.schema == pl.Schema(KOLOM_DIM_PRODUK)
    assert bintang.dim_toko.schema == pl.Schema(KOLOM_DIM_TOKO)
    assert bintang.dim_tanggal.schema == pl.Schema(KOLOM_DIM_TANGGAL)


def test_jumlah_fakta_sama_dengan_baris_lapisan_1(bintang, df_blibli, df_tokped):
    assert bintang.fakta_harga.height == df_blibli.height + df_tokped.height


def test_kunci_fakta_dihitung_dari_id(bintang):
    f = fakta_item(bintang, "NAS-70965-00407-00002")
    assert f["produk_key"] == kunci("blibli", "NAS-70965-00407")
    assert f["sumber"] == "blibli"


def test_setiap_kunci_fakta_ada_di_dimensi(bintang):
    f = bintang.fakta_harga
    assert f.join(bintang.dim_produk, on="produk_key", how="anti").height == 0
    assert f.join(bintang.dim_toko, on="toko_key", how="anti").height == 0
    assert f.join(bintang.dim_tanggal, on="tanggal", how="anti").height == 0


def test_kunci_dimensi_unik(bintang):
    assert bintang.dim_produk["produk_key"].is_unique().all()
    assert bintang.dim_toko["toko_key"].is_unique().all()
    assert bintang.dim_tanggal["tanggal"].is_unique().all()


def test_lolos_skema_lapisan_2(bintang):
    for df, skema in ((bintang.fakta_harga, SkemaFakta), (bintang.dim_produk, SkemaDimProduk),
                      (bintang.dim_toko, SkemaDimToko)):
        _, karantina = pisahkan(df, skema, "campuran")
        assert karantina.height == 0, skema.__name__


# --- harga per kg / per buah ------------------------------------------------

def test_harga_per_kg_per_opsi(bintang):
    assert fakta_item(bintang, "NAS-70965-00407-00001")["harga_per_kg"] == 92000    # 46000 / 500 g
    assert fakta_item(bintang, "NAS-70965-00407-00002")["harga_per_kg"] == 84900    # 1 kg


def test_harga_per_kg_null_kalau_berat_tidak_terbaca(bintang):
    lain = bintang.fakta_harga.filter(pl.col("jenis_satuan") != "berat")
    assert lain.height > 0
    assert lain["harga_per_kg"].null_count() == lain.height


def test_harga_per_buah_kalau_jumlah(df_blibli):
    sku = "NAS-70965-00407-00001"
    df = df_blibli.with_columns(
        pl.when(pl.col("item_sku") == sku).then(pl.lit(v)).otherwise(pl.col(k)).alias(k)
        for k, v in (("jenis_satuan", "jumlah"), ("jumlah_buah", 4), ("berat_gram", None))
    )
    f = fakta_item(bangun(df, None), sku)
    assert (f["harga_per_buah"], f["harga_per_kg"]) == (11500, None)    # 46000 / 4


# --- Blibli -------------------------------------------------------------------

def test_asal_blibli_dari_label(bintang):
    b = bintang.dim_produk.filter(pl.col("sumber") == "blibli")
    assert (b["asal_sumber"] == "label").all()
    assert set(b["asal"]) <= {"lokal", "impor"}


def test_toko_blibli(bintang, df_blibli):
    baris = df_blibli.filter(pl.col("item_sku") == "NAS-70965-00407-00002").row(0, named=True)
    f = fakta_item(bintang, "NAS-70965-00407-00002")
    toko = bintang.dim_toko.filter(pl.col("toko_key") == f["toko_key"]).row(0, named=True)
    assert toko["toko_id"] == baris["merchant_code"]
    assert toko["nama_toko"] == baris["penjual"]
    assert toko["jenis_toko"] == ("resmi" if baris["resmi"] else "biasa")


def test_kota_per_baris_fakta(df_blibli):
    # Blibli: lokasi milik produk (gudang pengirim), bukan toko. Ranch Market punya produk dari
    # Surabaya dan Jakarta di hari yang sama (14 Nov), jadi kota disimpan per baris fakta.
    sku = "NAS-70965-00407-00002"
    df = df_blibli.with_columns(
        lokasi=pl.when(pl.col("item_sku") == sku).then(pl.lit("Kota Surabaya"))
        .otherwise(pl.lit("Kota Bekasi")))
    f = bangun(df, None).fakta_harga
    assert f.filter(pl.col("item_sku") == sku)["kota"].to_list() == ["Kota Surabaya"]
    assert set(f.filter(pl.col("item_sku") != sku)["kota"]) == {"Kota Bekasi"}


def test_fakta_kode_wilayah(df_blibli):
    sku = "NAS-70965-00407-00002"
    df = df_blibli.with_columns(
        lokasi=pl.when(pl.col("item_sku") == sku).then(pl.lit("Kota Surabaya"))
        .otherwise(pl.lit("Kota Antah")))
    f = bangun(df, None).fakta_harga
    kode = ["kabkota_kode", "provinsi_kode"]
    assert f.filter(pl.col("item_sku") == sku).select(kode).rows() == [("35.78", "35")]
    assert set(f.filter(pl.col("item_sku") != sku).select(kode).rows()) == {(None, None)}


def test_harga_coret_dan_terjual_blibli(bintang, df_blibli):
    baris = df_blibli.filter(pl.col("item_sku") == "NAS-70965-00407-00002").row(0, named=True)
    f = fakta_item(bintang, "NAS-70965-00407-00002")
    assert (f["harga"], f["harga_coret"], f["diskon_persen"]) == (84900, 90000, 6)
    assert f["opsi_default"] is False
    assert f["variant"] == "1 kg"
    from transform.parser import ember_terjual
    assert f["terjual_min"] == ember_terjual(baris["total_terjual"])


# --- Tokopedia ----------------------------------------------------------------

def test_opsi_tokopedia_satu_produk_induk(bintang):
    # 103999725486 (kartu) + 5 opsi lain, induk 103388173219 (keputusan 9 Nov)
    kunci_induk = kunci("tokopedia", "103388173219")
    opsi = bintang.fakta_harga.filter(pl.col("produk_key") == kunci_induk)
    assert opsi.height == 6
    assert opsi["item_sku"].n_unique() == 6
    assert opsi.filter(pl.col("opsi_default"))["item_sku"].to_list() == ["103999725486"]
    assert produk(bintang, kunci_induk)["produk_id"] == "103388173219"


def test_tokopedia_tanpa_induk_pakai_id_sendiri(bintang):
    f = fakta_item(bintang, "903168210")
    assert f["produk_key"] == kunci("tokopedia", "903168210")


def test_induk_diisi_dari_tanggal_lain(df_tokped):
    # tanggal 9: kartu yang sama tetapi halaman produknya gagal ditarik → induk_id NULL
    hari_lain = df_tokped.filter(pl.col("opsi_default")).with_columns(
        tanggal=pl.lit(date(2026, 11, 9)), induk_id=pl.lit(None, pl.Utf8), variant=pl.lit(None, pl.Utf8))
    b = bangun(None, pl.concat([df_tokped, hari_lain]))
    f = b.fakta_harga.filter((pl.col("item_sku") == "103999725486") & (pl.col("tanggal") == date(2026, 11, 9)))
    assert f["produk_key"].to_list() == [kunci("tokopedia", "103388173219")]


def test_induk_dari_peta_luar(df_tokped):
    # tanggal lama tanpa halaman produk: induk diambil dari peta (dibaca dari gudang)
    lama = df_tokped.filter(pl.col("opsi_default")).with_columns(
        tanggal=pl.lit(date(2026, 11, 7)), induk_id=pl.lit(None, pl.Utf8))
    peta = pl.DataFrame({"produk_id": ["103999725486"], "induk_id": ["103388173219"]})
    tanpa = fakta_item(bangun(None, lama), "103999725486")
    dengan = fakta_item(bangun(None, lama, peta_induk=peta), "103999725486")
    assert tanpa["produk_key"] == kunci("tokopedia", "103999725486")
    assert dengan["produk_key"] == kunci("tokopedia", "103388173219")


def test_induk_baris_sendiri_menang_atas_peta_luar(df_tokped):
    peta = pl.DataFrame({"produk_id": ["103999725486"], "induk_id": ["999"]})
    f = fakta_item(bangun(None, df_tokped, peta_induk=peta), "103999725486")
    assert f["produk_key"] == kunci("tokopedia", "103388173219")


def test_tokopedia_tanpa_harga_coret_dan_diskon(bintang):
    # keputusan 13 #1–2: harga_asli tidak dipakai di fakta, diskon NULL
    t = bintang.fakta_harga.filter(pl.col("sumber") == "tokopedia")
    assert t["harga_coret"].null_count() == t.height
    assert t["diskon_persen"].null_count() == t.height


def test_asal_tokopedia_dari_aturan(bintang):
    t = bintang.dim_produk.filter(pl.col("sumber") == "tokopedia")
    assert (t["asal_sumber"] == "aturan").all()
    assert set(t["asal"]) <= {"lokal", "impor", "tidak_diketahui"}


def test_toko_tanpa_kota_tetap_masuk_fakta(bintang):
    f = fakta_item(bintang, "492628329")
    toko = bintang.dim_toko.filter(pl.col("toko_key") == f["toko_key"]).row(0, named=True)
    assert toko["kota"] is None
    assert toko["region"] == "tidak_diketahui"


def test_jenis_toko_tokopedia_dari_tier(bintang):
    f = fakta_item(bintang, "8061245026")
    toko = bintang.dim_toko.filter(pl.col("toko_key") == f["toko_key"]).row(0, named=True)
    assert toko["jenis_toko"] == "tier_3"
    assert f["terjual_min"] == 26          # "26 terjual"


def test_jenis_buah_dan_olahan(bintang):
    p = produk(bintang, kunci("tokopedia", "903168210"))   # "Mangga Manalagi 1kg"
    assert (p["jenis_buah"], p["olahan"]) == ("mangga", False)


# --- tanggal dan pilihan sumber --------------------------------------------

def test_dim_tanggal():
    df = blibli.ubah(FIXTURE / "blibli" / "date=2026-11-08", TANGGAL)
    t = bangun(df, None).dim_tanggal.row(0, named=True)
    assert t == {"tanggal": TANGGAL, "tahun": 2026, "bulan": 11, "minggu": 45, "hari": "Minggu"}


def test_bangun_satu_sumber_saja(df_blibli, df_tokped):
    hanya_blibli = bangun(df_blibli, None)
    assert hanya_blibli.fakta_harga.height == df_blibli.height
    assert set(hanya_blibli.fakta_harga["sumber"]) == {"blibli"}
    assert bangun(None, df_tokped).fakta_harga.height == df_tokped.height


def test_dimensi_yang_terakhir_menang(df_tokped):
    besok = df_tokped.with_columns(tanggal=pl.lit(date(2026, 11, 9)), nama_toko=pl.lit("Toko Baru"))
    b = bangun(None, pl.concat([df_tokped, besok]))
    assert set(b.dim_toko["nama_toko"]) == {"Toko Baru"}
    assert b.dim_tanggal.height == 2
    assert set(b.dim_toko["tanggal_terakhir"]) == {date(2026, 11, 9)}
    assert set(b.dim_produk["tanggal_terakhir"]) == {date(2026, 11, 9)}
