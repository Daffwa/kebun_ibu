import json
import shutil
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from transform.blibli import KOLOM_BLIBLI, angka_rupiah, ubah

FIXTURE = Path(__file__).parent / "fixtures" / "blibli"
DENGAN_VARIAN = FIXTURE / "date=2026-11-08"
TANPA_VARIAN = FIXTURE / "date=2026-11-06"


@pytest.fixture(scope="module")
def df():
    return ubah(DENGAN_VARIAN, date(2026, 11, 8))


def baris(df, item_sku):
    hasil = df.filter(pl.col("item_sku") == item_sku)
    assert hasil.height == 1, f"{item_sku}: {hasil.height} baris"
    return hasil.row(0, named=True)


def test_kolom_dan_tipe_tepat(df):
    assert df.schema == pl.Schema(KOLOM_BLIBLI)


def test_satu_baris_per_opsi(df):
    assert df.filter(pl.col("produk_id") == "NAS-70965-00407").height == 2
    opsi = baris(df, "NAS-70965-00407-00002")
    assert opsi["harga"] == 84900
    assert opsi["harga_coret"] == 90000
    assert opsi["diskon_persen"] == 6
    assert opsi["variant"] == "1 kg"
    assert opsi["opsi_default"] is False
    assert opsi["tanggal"] == date(2026, 11, 8)


def test_baris_default_dari_kartu(df):
    default = baris(df, "NAS-70965-00407-00001")
    assert default["opsi_default"] is True
    assert default["harga"] == 46000
    assert default["harga_coret"] == 50000
    assert default["variant"] == "500 gr"


def test_opsi_lain_menyalin_kolom_produk(df):
    default = baris(df, "DOD-70072-00076-00001")
    opsi = baris(df, "DOD-70072-00076-00002")
    for kolom in ("nama", "penjual", "merchant_code", "kategori", "kategori_tarik", "rating_toko",
                  "lokasi", "resmi", "rating", "jumlah_ulasan", "total_terjual"):
        assert opsi[kolom] == default[kolom], kolom


def test_opsi_lain_kolom_kartu_null(df):
    opsi = baris(df, "DOD-70072-00076-00002")
    for kolom in ("harga_voucher", "harga_coret_voucher", "diskon_voucher_persen", "kampanye",
                  "harga_sebelum_kampanye", "terjual_bulan_ini_min", "sku"):
        assert opsi[kolom] is None, kolom


def test_tanpa_folder_varian_hanya_baris_default():
    df6 = ubah(TANPA_VARIAN, date(2026, 11, 6))
    assert df6.height == 10
    assert df6["opsi_default"].all()


def test_rating_null_kalau_tanpa_ulasan(df):
    assert baris(df, "NAS-70965-00407-00001")["rating"] is None       # review.count = 0
    assert baris(df, "DOD-70072-00076-00001")["rating"] == 3.0


@pytest.mark.parametrize("teks,angka", [
    ("Rp39.100", 39100), ("Rp114.950", 114950), ("Rp1.250.000", 1250000), ("", None), (None, None),
])
def test_angka_rupiah(teks, angka):
    assert angka_rupiah(teks) == angka


def test_voucher(df):
    b = baris(df, "HYP-60026-23787-00001")
    assert (b["harga_voucher"], b["harga_coret_voucher"], b["diskon_voucher_persen"]) == (112950, 114950, 2)


def test_kampanye(df):
    b = baris(df, "RAM-70107-19892-00001")
    assert b["kampanye"] == "Campaign 11.11"
    assert b["harga_sebelum_kampanye"] == 32000


def test_terjual_bulan_ini_min(df):
    assert baris(df, "HYP-60026-02571-00001")["terjual_bulan_ini_min"] == 50   # "Dibeli 50+ kali bulan ini"


def test_berat_variant_menang(df):
    b = baris(df, "NAS-70965-00407-00001")             # nama "1 Kg", variant "500 gr"
    assert (b["berat_gram"], b["sumber_berat"], b["jenis_satuan"]) == (500, "variant", "berat")
    b = baris(df, "DOD-70072-00076-00002")              # opsi lain: "1 kg"
    assert (b["berat_gram"], b["sumber_berat"]) == (1000, "variant")


def test_kategori_tarik_dari_nama_berkas(df):
    assert baris(df, "NAS-70965-00407-00001")["kategori_tarik"] == "BU-1000191"
    assert baris(df, "DOD-70072-00076-00001")["kategori_tarik"] == "BU-1000190"


def test_baris_ganda_dibuang(df):
    assert df["item_sku"].is_unique().all()
    assert baris(df, "HYP-60026-02571-00001")["kategori_tarik"] == "BU-1000190"   # yang pertama


def test_sku_dan_url(df):
    default = baris(df, "NAS-70965-00407-00001")
    assert default["sku"] == default["produk_id"] == "NAS-70965-00407"
    # url tanpa sid/metaData pelacak, dengan ?ds=<item_sku> supaya membuka opsi yang benar
    assert default["url"] == "https://www.blibli.com/p/apel-fuji-super-fresh-1-kg/ps--NAS-70965-00407?ds=NAS-70965-00407-00001"
    assert baris(df, "NAS-70965-00407-00002")["url"] == \
        "https://www.blibli.com/p/apel-fuji-super-fresh-1-kg/ps--NAS-70965-00407?ds=NAS-70965-00407-00002"


def test_opsi_tanpa_harga_tetap_ada_dengan_harga_null(tmp_path):
    # Keputusan B (8 Nov): opsi yang Blibli tandai tidak tersedia punya price null
    # (86 dari 665 berkas is--). Barisnya tetap ada; Task 6 mengarantinanya.
    folder = tmp_path / "date=2026-11-08"
    shutil.copytree(DENGAN_VARIAN, folder)
    berkas = folder / "varian" / "is--DOD-70072-00076-00002.json"
    isi = json.loads(berkas.read_text(encoding="utf-8"))
    isi["data"]["price"] = None
    berkas.write_text(json.dumps(isi), encoding="utf-8")
    b = baris(ubah(folder, date(2026, 11, 8)), "DOD-70072-00076-00002")
    assert (b["harga"], b["harga_coret"], b["diskon_persen"]) == (None, None, None)
    assert b["variant"] == "1 kg"
    assert b["penjual"] == "Doyan Daging Store Depok"


def test_kolom_hilang_gagal_jelas(tmp_path):
    folder = tmp_path / "date=2026-11-06"
    shutil.copytree(TANPA_VARIAN, folder)
    berkas = folder / "BU-1000190_page_001.json"
    isi = json.loads(berkas.read_text(encoding="utf-8"))
    del isi["data"]["products"][0]["price"]
    berkas.write_text(json.dumps(isi), encoding="utf-8")
    with pytest.raises(ValueError, match=r"price.*BU-1000190_page_001\.json"):
        ubah(folder, date(2026, 11, 6))
