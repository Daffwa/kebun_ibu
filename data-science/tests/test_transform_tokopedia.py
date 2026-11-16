import json
import shutil
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from transform.tokopedia import KOLOM_TOKOPEDIA, ubah

# Data asli 8 Nov: 2 halaman x 20 produk (1 ganda) + halaman produk 4 Mangga Manalagi
# (dipangkas ke pdpBasicInfo, pdpContentSnapshotVariant, pdpProductVariantChildren).
FIXTURE = Path(__file__).parent / "fixtures" / "tokopedia" / "date=2026-11-08"
TANGGAL = date(2026, 11, 8)


@pytest.fixture(scope="module")
def df():
    return ubah(FIXTURE, TANGGAL)


def baris(df, produk_id):
    hasil = df.filter(pl.col("produk_id") == produk_id)
    assert hasil.height == 1, f"{produk_id}: {hasil.height} baris"
    return hasil.row(0, named=True)


def test_kolom_dan_tipe_tepat(df):
    assert df.schema == pl.Schema(KOLOM_TOKOPEDIA)


def test_satu_baris_per_produk_kartu_ditambah_opsi_lain(df):
    # 39 kartu unik (1 ganda dibuang) + 1 opsi lain 8061245026 + 5 opsi lain 103999725486
    assert df.height == 45
    assert df["produk_id"].n_unique() == 45
    assert df.filter(pl.col("opsi_default")).height == 39


def test_kolom_dasar_dari_kartu(df):
    b = baris(df, "8061245026")
    assert b["tanggal"] == TANGGAL
    assert b["nama"] == "MANGGA MANALAGI MADU MANGGA MANALAGI MATANG MANIS Buah"
    assert b["harga"] == 24250
    assert b["toko_id"] == "9604679"
    assert b["nama_toko"] == "Mantra Khatulistiwa"
    assert b["kota"] == "Depok"
    assert b["tier_toko"] == 3
    assert b["rating"] == 4.7
    assert b["terjual_label"] == "26 terjual"
    assert b["kategori"] == "makanan-minuman/buah/buah-buahan"
    assert b["opsi_default"] is True


def test_harga_asli_diurai_diskon_selalu_null(df):
    assert baris(df, "10705788896")["harga_asli"] == 55000
    assert baris(df, "2138923770")["harga_asli"] is None
    assert df["diskon_persen"].null_count() == df.height


def test_rating_kosong_dan_label_hilang_jadi_null(df):
    b = baris(df, "2138923770")
    assert b["rating"] is None
    assert b["terjual_label"] is None


def test_kota_kosong_jadi_null(df):
    assert baris(df, "492628329")["kota"] is None


def test_url_tanpa_query(df):
    assert baris(df, "2652345561")["url"] == "https://www.tokopedia.com/sayurkendal/jeruk-ponkam-sayur-kendal-1000gr"


def test_baris_kartu_opsi_dapat_variant_dan_induk(df):
    b = baris(df, "103999725486")
    assert b["variant"] == "mengkal bermadu, 500 gram"
    assert b["induk_id"] == "103388173219"
    assert b["opsi_default"] is True


def test_opsi_lain_jadi_baris(df):
    opsi = baris(df, "8061245027")
    assert opsi["opsi_default"] is False
    assert opsi["variant"] == "1 kg"
    assert opsi["harga"] == 43650
    assert opsi["harga_asli"] == 45000
    assert opsi["induk_id"] == baris(df, "8061245026")["induk_id"]
    assert opsi["url"] == ("https://www.tokopedia.com/mantra-khatulistiwa/"
                           "mangga-manalagi-madu-mangga-manalagi-matang-manis-1731543572100449662")
    assert opsi["berat_gram"] == 1000
    assert opsi["sumber_berat"] == "opsi"


def test_opsi_lain_menyalin_kolom_produk(df):
    kartu = baris(df, "103999725486")
    opsi = baris(df, "103999725491")
    for kolom in ("tanggal", "nama", "toko_id", "nama_toko", "kota", "tier_toko", "rating",
                  "terjual_label", "kategori"):
        assert opsi[kolom] == kartu[kolom], kolom
    assert opsi["variant"] == "mentah tua, 2kg+bumbu bagkok"
    assert opsi["harga"] == 35000


def test_berat_dari_opsi_bukan_nama(df):
    # nama "... 1kg isi 3-5 buah", halaman produk: opsi "500 gram"
    b = baris(df, "103999725486")
    assert (b["berat_gram"], b["sumber_berat"]) == (500, "opsi")
    b = baris(df, "8061245026")
    assert (b["berat_gram"], b["sumber_berat"]) == (500, "opsi")


def test_berat_halaman_kalau_nama_tanpa_berat(df):
    b = baris(df, "14020643072")   # "Mangga Manalagi Potong Manis", halaman 0,35 kg
    assert (b["berat_gram"], b["sumber_berat"], b["jenis_satuan"]) == (350, "halaman", "berat")


def test_nama_menang_atas_halaman(df):
    b = baris(df, "903168210")   # "Mangga Manalagi 1kg", halaman 1,2 kg (kemasan)
    assert (b["berat_gram"], b["sumber_berat"]) == (1000, "nama")


def test_tanpa_halaman_produk_pakai_nama(df):
    b = baris(df, "11808381073")   # Manalagi yang halamannya gagal ditarik
    assert (b["berat_gram"], b["sumber_berat"]) == (1000, "nama")
    assert b["induk_id"] is None
    assert b["variant"] is None


def test_url_kalau_nama_tanpa_berat(df):
    b = baris(df, "2652345561")   # "Jeruk Ponkam - Sayur Kendal", slug "...-1000gr"
    assert (b["berat_gram"], b["sumber_berat"]) == (1000, "url")


def test_tanpa_folder_halaman_hanya_baris_kartu(tmp_path):
    folder = tmp_path / "date=2026-11-08"
    shutil.copytree(FIXTURE, folder, ignore=shutil.ignore_patterns("halaman"))

    df = ubah(folder, TANGGAL)

    assert df.height == 39
    assert df["opsi_default"].all()
    assert (baris(df, "103999725486")["berat_gram"], baris(df, "103999725486")["sumber_berat"]) == (1000, "nama")


def test_kolom_hilang_gagal_jelas(tmp_path):
    folder = tmp_path / "date=2026-11-08"
    folder.mkdir()
    isi = json.loads((FIXTURE / "page_001.json").read_text(encoding="utf-8"))
    del isi[0]["data"]["searchProductV5"]["data"]["products"][0]["shop"]
    (folder / "page_001.json").write_text(json.dumps(isi), encoding="utf-8")

    with pytest.raises(ValueError, match="shop"):
        ubah(folder, TANGGAL)
