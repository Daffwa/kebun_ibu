import polars as pl
import pytest

from transform.wilayah import ALIAS_KOTA, KELOMPOK, anggota, cocokkan, kabkota, kunci_nama


@pytest.mark.parametrize("kota,hasil", [
    ("Kota Surabaya", ("35.78", "35")),
    ("Surabaya", ("35.78", "35")),                 # gaya Tokopedia, tanpa awalan
    ("Kab.Ciamis", ("32.07", "32")),               # tanpa spasi sesudah "Kab."
    ("Kota Palangka Raya", ("62.71", "62")),       # resmi: Palangkaraya
    ("Kota Pematang Siantar", ("12.72", "12")),    # resmi: Pematangsiantar
    ("Kota Banjar", ("32.79", "32")),
    ("Kab. Banjar", ("63.03", "63")),
    ("Banjar", (None, None)),                      # satu-satunya nama di dua provinsi
    ("Kota Antah Berantah", (None, None)),
    (None, (None, None)),
    ("  ", (None, None)),
    ("Jakarta Timur", ("31.75", "31")),            # resmi: Kota Administrasi Jakarta Timur
])
def test_cocokkan(kota, hasil):
    assert cocokkan(kota) == hasil


def test_alias(monkeypatch):
    monkeypatch.setitem(ALIAS_KOTA, kunci_nama("Kota Antah Berantah"), "35.78")
    assert cocokkan("Kota Antah Berantah") == ("35.78", "35")


def test_daftar_lengkap():
    k = kabkota()
    assert k.height == 514 and k["provinsi_kode"].n_unique() == 38
    assert "Administrasi" not in " ".join(k["nama"])
    assert all(n == n.strip() for n in k["nama"])
    assert len(KELOMPOK["jabodetabek"][1]) == 14


def test_anggota_surabaya():
    a = anggota()
    assert sorted(a.filter(pl.col("kabkota_kode") == "35.78")["wilayah"].to_list()) == ["35", "35.78"]
    assert "jabodetabek" in a.filter(pl.col("kabkota_kode") == "36.74")["wilayah"].to_list()
