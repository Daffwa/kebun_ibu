import json
from datetime import date
from pathlib import Path

import pandera.polars as pa
import polars as pl
import pytest

from transform import blibli, tokopedia
from transform.skema import (
    KOLOM_KARANTINA,
    SkemaBlibli,
    SkemaDimProduk,
    SkemaDimToko,
    SkemaFakta,
    SkemaTokopedia,
    pisahkan,
)

FIXTURE = Path(__file__).parent / "fixtures"
TANGGAL = date(2026, 11, 8)
VOUCHER = "HYP-60026-23787-00001"   # baris Blibli dengan harga_voucher terisi


@pytest.fixture(scope="module")
def df_blibli():
    return blibli.ubah(FIXTURE / "blibli" / "date=2026-11-08", TANGGAL)


@pytest.fixture(scope="module")
def df_tokped():
    return tokopedia.ubah(FIXTURE / "tokopedia" / "date=2026-11-08", TANGGAL)


def ganti(df, kolom_kunci, kunci, **nilai):
    """Ubah kolom satu baris (dipilih lewat `kolom_kunci == kunci`)."""
    pilih = pl.col(kolom_kunci) == kunci
    assert df.filter(pilih).height == 1
    return df.with_columns(
        pl.when(pilih).then(pl.lit(v, dtype=df.schema[k])).otherwise(pl.col(k)).alias(k)
        for k, v in nilai.items()
    )


def ganti_blibli(df, item_sku, **nilai):
    return ganti(df, "item_sku", item_sku, **nilai)


def satu_karantina(karantina):
    assert karantina.height == 1
    return karantina.row(0, named=True)


def default_pertama(df):
    return df.filter(pl.col("opsi_default"))["item_sku"][0]


# --- dasar ---------------------------------------------------------------

def test_baris_bagus_lolos_semua(df_blibli, df_tokped):
    for df, skema, sumber in ((df_blibli, SkemaBlibli, "blibli"), (df_tokped, SkemaTokopedia, "tokopedia")):
        lolos, karantina = pisahkan(df, skema, sumber)
        assert lolos.equals(df), sumber
        assert karantina.height == 0, sumber
        assert karantina.schema == pl.Schema(KOLOM_KARANTINA)


def test_harga_negatif_dikarantina(df_tokped):
    df = ganti(df_tokped, "produk_id", "903168210", harga=-1)

    lolos, karantina = pisahkan(df, SkemaTokopedia, "tokopedia")

    assert lolos.height == df.height - 1
    assert "903168210" not in lolos["produk_id"]
    k = satu_karantina(karantina)
    assert (k["sumber"], k["tanggal"], k["produk_id"]) == ("tokopedia", TANGGAL, "903168210")
    assert "harga" in k["alasan"] and "greater_than" in k["alasan"]


def test_rating_di_luar_batas_dikarantina(df_tokped):
    df = ganti(df_tokped, "produk_id", "903168210", rating=9.0)
    _, karantina = pisahkan(df, SkemaTokopedia, "tokopedia")
    assert "rating" in satu_karantina(karantina)["alasan"]


def test_diskon_di_luar_batas_dikarantina(df_blibli):
    df = ganti_blibli(df_blibli, VOUCHER, diskon_persen=101)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert "diskon_persen" in satu_karantina(karantina)["alasan"]


def test_dua_masalah_satu_baris_satu_entri(df_tokped):
    df = ganti(df_tokped, "produk_id", "903168210", harga=-1, rating=9.0)
    _, karantina = pisahkan(df, SkemaTokopedia, "tokopedia")
    alasan = satu_karantina(karantina)["alasan"]
    assert "harga" in alasan and "rating" in alasan
    assert alasan.count(";") == 1


def test_harga_null_dikarantina(df_blibli):
    df = ganti_blibli(df_blibli, "NAS-70965-00407-00002", harga=None, harga_coret=None, diskon_persen=None)
    lolos, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert lolos.height == df.height - 1
    assert "harga" in satu_karantina(karantina)["alasan"]


def test_produk_ganda_dikarantina(df_tokped):
    df = pl.concat([df_tokped, df_tokped.filter(pl.col("produk_id") == "903168210")])
    lolos, karantina = pisahkan(df, SkemaTokopedia, "tokopedia")
    assert karantina["produk_id"].to_list() == ["903168210", "903168210"]
    assert lolos.height == df_tokped.height - 1


def test_kolom_hilang_tidak_dikarantina_tapi_dilempar(df_tokped):
    with pytest.raises(pa.errors.SchemaErrors):
        pisahkan(df_tokped.drop("harga"), SkemaTokopedia, "tokopedia")


def test_tipe_salah_dilempar(df_tokped):
    with pytest.raises(pa.errors.SchemaErrors):
        pisahkan(df_tokped.with_columns(pl.col("harga").cast(pl.Float64)), SkemaTokopedia, "tokopedia")


def test_data_karantina_bisa_dibaca_ulang(df_tokped):
    df = ganti(df_tokped, "produk_id", "903168210", harga=-1)
    _, karantina = pisahkan(df, SkemaTokopedia, "tokopedia")
    data = json.loads(karantina["data"][0])
    assert data["harga"] == -1
    assert data["nama"] == "Mangga Manalagi 1kg"


# --- cek perbandingan Blibli (spec 6.1) ----------------------------------

def test_cek_A_voucher_lebih_mahal_dikarantina(df_blibli):
    harga = df_blibli.filter(pl.col("item_sku") == VOUCHER)["harga"][0]
    df = ganti_blibli(df_blibli, VOUCHER, harga_voucher=harga + 1)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert "cek_A_harga_urut" in satu_karantina(karantina)["alasan"]


def test_cek_A_harga_di_atas_coret_dikarantina(df_blibli):
    sku = default_pertama(df_blibli)
    coret = df_blibli.filter(pl.col("item_sku") == sku)["harga_coret"][0]
    df = ganti_blibli(df_blibli, sku, harga=coret + 1, diskon_persen=0, harga_sebelum_kampanye=None)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert "cek_A_harga_urut" in satu_karantina(karantina)["alasan"]


def test_cek_B_diskon_tidak_cocok_dikarantina(df_blibli):
    sku = default_pertama(df_blibli)
    diskon = df_blibli.filter(pl.col("item_sku") == sku)["diskon_persen"][0]
    df = ganti_blibli(df_blibli, sku, diskon_persen=diskon + 5)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert satu_karantina(karantina)["alasan"] == "cek_B_diskon"


def test_cek_D_coret_voucher_beda_dikarantina(df_blibli):
    coret = df_blibli.filter(pl.col("item_sku") == VOUCHER)["harga_coret"][0]
    df = ganti_blibli(df_blibli, VOUCHER, harga_coret_voucher=coret + 1000)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert satu_karantina(karantina)["alasan"] == "cek_D_coret_voucher"


def test_cek_E_diskon_voucher_tidak_cocok_dikarantina(df_blibli):
    diskon = df_blibli.filter(pl.col("item_sku") == VOUCHER)["diskon_voucher_persen"][0]
    df = ganti_blibli(df_blibli, VOUCHER, diskon_voucher_persen=diskon + 5)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert satu_karantina(karantina)["alasan"] == "cek_E_diskon_voucher"


def test_cek_F_harga_turun_tanpa_kampanye_dikarantina(df_blibli):
    # kasus asli FRX-60021-01718: sebelum kampanye 15000, harga 10000, kampanye NULL
    sku = default_pertama(df_blibli)
    df = ganti_blibli(df_blibli, sku, harga=10000, harga_coret=40000, diskon_persen=75,
                      harga_sebelum_kampanye=15000, kampanye=None)
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert satu_karantina(karantina)["alasan"] == "cek_F_kampanye"


def test_cek_F_lolos_kalau_kampanye_ada(df_blibli):
    sku = default_pertama(df_blibli)
    df = ganti_blibli(df_blibli, sku, harga=10000, harga_coret=40000, diskon_persen=75,
                      harga_sebelum_kampanye=15000, kampanye="Flash Sale")
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert karantina.height == 0


def test_cek_G_sku_beda_dari_id_dikarantina(df_blibli):
    sku = default_pertama(df_blibli)
    produk_id = df_blibli.filter(pl.col("item_sku") == sku)["produk_id"][0]
    df = ganti_blibli(df_blibli, sku, sku=produk_id + "X")
    _, karantina = pisahkan(df, SkemaBlibli, "blibli")
    assert satu_karantina(karantina)["alasan"] == "cek_G_sku_sama_id"


def test_cek_dilewati_kalau_kolom_null(df_blibli):
    # baris opsi lain: voucher, kampanye, sku semuanya NULL
    opsi = df_blibli.filter(~pl.col("opsi_default"))
    assert opsi["harga_voucher"].null_count() == opsi.height
    assert opsi["sku"].null_count() == opsi.height
    lolos, karantina = pisahkan(df_blibli, SkemaBlibli, "blibli")
    assert karantina.height == 0
    assert lolos.filter(~pl.col("opsi_default")).height == opsi.height


# --- cek H: dicatat, tetap lolos ----------------------------------------

@pytest.mark.parametrize("platform", ["blibli", "tokopedia"])
def test_cek_H_berat_dikali_dicatat_tetapi_tetap_lolos(df_blibli, df_tokped, platform):
    if platform == "blibli":
        df, skema, kunci = df_blibli, SkemaBlibli, ("item_sku", VOUCHER)
    else:
        df, skema, kunci = df_tokped, SkemaTokopedia, ("produk_id", "903168210")
    df = ganti(df, *kunci, nama="Jeruk 8x125GR", berat_dikali=True)

    lolos, karantina = pisahkan(df, skema, platform)

    assert lolos.height == df.height
    k = satu_karantina(karantina)
    assert k["alasan"] == "cek_H_berat_dikali"
    assert json.loads(k["data"])["nama"] == "Jeruk 8x125GR"


def test_cek_H_digabung_dengan_masalah_lain(df_tokped):
    df = ganti(df_tokped, "produk_id", "903168210", harga=-1, berat_dikali=True)
    lolos, karantina = pisahkan(df, SkemaTokopedia, "tokopedia")
    assert lolos.height == df.height - 1
    alasan = satu_karantina(karantina)["alasan"]
    assert "harga" in alasan and "cek_H_berat_dikali" in alasan


# --- lapisan 2 (dipakai Task 7) -------------------------------------------

def fakta(**nilai):
    baris = {"tanggal": TANGGAL, "sumber": "tokopedia", "produk_key": "p1", "toko_key": "t1",
             "harga": 24250, "harga_per_kg": 48500} | nilai
    return pl.DataFrame([baris], schema={"tanggal": pl.Date, "sumber": pl.Utf8, "produk_key": pl.Utf8,
                                         "toko_key": pl.Utf8, "harga": pl.Int64, "harga_per_kg": pl.Int64})


def test_fakta_bagus_lolos():
    baik = [fakta(), fakta(harga_per_kg=None), fakta(harga_per_kg=2000), fakta(harga_per_kg=2_000_000)]
    lolos, karantina = pisahkan(pl.concat(baik), SkemaFakta, "tokopedia")
    assert (lolos.height, karantina.height) == (4, 0)


@pytest.mark.parametrize("nilai, kata", [
    # batas 2.000–2.000.000 per kg (keputusan 13 #5, 9 Nov)
    ({"harga_per_kg": 1999}, "harga_per_kg"),
    ({"harga_per_kg": 2_000_001}, "harga_per_kg"),
    ({"sumber": "shopee"}, "sumber"),
    ({"harga": 0}, "harga"),
])
def test_fakta_di_luar_batas_dikarantina(nilai, kata):
    _, karantina = pisahkan(fakta(**nilai), SkemaFakta, "tokopedia")
    k = satu_karantina(karantina)
    assert kata in k["alasan"]
    assert k["produk_id"] is None      # fakta tidak punya produk_id


def test_kunci_dimensi_ganda_dikarantina():
    dim_produk = pl.DataFrame({"produk_key": ["a", "a", "b"], "sumber": ["blibli"] * 3})
    _, karantina = pisahkan(dim_produk, SkemaDimProduk, "blibli")
    assert karantina.height == 2
    assert karantina["tanggal"].null_count() == 2

    dim_toko = pl.DataFrame({"toko_key": ["x", "y"], "sumber": ["blibli", "lazada"]})
    _, karantina = pisahkan(dim_toko, SkemaDimToko, "blibli")
    assert "sumber" in satu_karantina(karantina)["alasan"]
