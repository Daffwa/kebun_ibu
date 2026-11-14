from datetime import date

import polars as pl
import pytest

from dashboard_manalagi import daftar_wilayah, hitung
from tests.conftest import MULAI_TES


def j(hari: int, bulan: int = 1) -> date:
    return date(2026, bulan, hari)


def nilai(df, kolom, **saring):
    for k, v in saring.items():
        df = df.filter(df[k] == v)
    assert len(df) == 1, saring
    return df[kolom][0]


def test_filter_hanya_manalagi_default_bukan_olahan_sejak_mulai(buat_gudang):
    con = buat_gudang([
        {"tanggal": j(2), "produk_key": "ok", "harga_per_kg": 20_000},
        {"tanggal": j(2), "produk_key": "harum", "harga_per_kg": 20_000, "nama": "Mangga Harum Manis"},
        {"tanggal": j(2), "produk_key": "olahan", "harga_per_kg": 20_000, "olahan": True},
        {"tanggal": j(2), "produk_key": "opsi", "harga_per_kg": 20_000, "opsi_default": False},
        {"tanggal": j(2), "produk_key": "tanpa_harga", "harga_per_kg": None},
        {"tanggal": date(2025, 12, 31), "produk_key": "lama", "harga_per_kg": 20_000},
    ])

    baris, _ = hitung(con, MULAI_TES)

    assert baris["produk_key"].to_list() == ["ok"]
    assert len(baris.columns) == 18          # 16 + kabkota_kode, provinsi_kode


def test_lonjak_toko_ditandai_sekali(buat_gudang):
    con = buat_gudang([{"tanggal": j(h), "produk_key": "a", "harga_per_kg": 10_000} for h in (1, 2, 3)]
                      + [{"tanggal": j(h), "produk_key": "a", "harga_per_kg": 12_000} for h in (4, 5)])

    baris, _ = hitung(con, MULAI_TES)

    assert baris.filter(baris["lonjak_toko"])["tanggal"].to_list() == [j(4)]
    assert nilai(baris, "rasio_jendela", tanggal=j(4)) == pytest.approx(1.2)


def test_kurang_dari_min_data_tidak_dinilai(buat_gudang):
    con = buat_gudang([{"tanggal": j(1), "produk_key": "a", "harga_per_kg": 10_000},
                       {"tanggal": j(2), "produk_key": "a", "harga_per_kg": 10_000},
                       {"tanggal": j(3), "produk_key": "a", "harga_per_kg": 15_000}])

    baris, _ = hitung(con, MULAI_TES)

    assert nilai(baris, "rasio_jendela", tanggal=j(3)) is None
    assert nilai(baris, "lonjak_toko", tanggal=j(3)) is False


def test_indeks_berantai_abaikan_produk_baru(buat_gudang):
    con = buat_gudang([
        {"tanggal": j(1), "produk_key": "a", "harga_per_kg": 10_000},
        {"tanggal": j(2), "produk_key": "a", "harga_per_kg": 11_000},
        {"tanggal": j(1), "produk_key": "b", "harga_per_kg": 20_000},
        {"tanggal": j(2), "produk_key": "b", "harga_per_kg": 22_000},
        {"tanggal": j(2), "produk_key": "c", "harga_per_kg": 50_000},
    ])

    _, harian = hitung(con, MULAI_TES)

    assert nilai(harian, "indeks_berantai", pasar="semua", tanggal=j(1)) == pytest.approx(15_000)
    assert nilai(harian, "indeks_berantai", pasar="semua", tanggal=j(2)) == pytest.approx(16_500)


def test_jeda_lebih_dari_maks_tidak_menggerakkan_indeks(buat_gudang):
    con = buat_gudang([{"tanggal": j(1), "produk_key": "a", "harga_per_kg": 10_000},
                       {"tanggal": j(10, 2), "produk_key": "a", "harga_per_kg": 20_000}])

    baris, harian = hitung(con, MULAI_TES)

    assert nilai(baris, "faktor", tanggal=j(10, 2)) is None
    assert nilai(harian, "indeks_berantai", pasar="semua", tanggal=j(10, 2)) == pytest.approx(10_000)


def test_lonjak_pasar_dan_tiga_pasar(buat_gudang):
    produk = [("a", "tokopedia"), ("b", "tokopedia"), ("c", "blibli")]
    con = buat_gudang([{"tanggal": j(h), "produk_key": k, "sumber": s, "harga_per_kg": 10_000}
                       for k, s in produk for h in (1, 2, 3)]
                      + [{"tanggal": j(4), "produk_key": k, "sumber": s, "harga_per_kg": 11_000}
                         for k, s in produk])

    _, harian = hitung(con, MULAI_TES)

    assert nilai(harian, "lonjak_pasar", pasar="semua", tanggal=j(4)) is True
    assert nilai(harian, "naik", pasar="semua", tanggal=j(4)) == 3
    assert nilai(harian, "lonjak_pasar", pasar="semua", tanggal=j(3)) is False
    assert sorted(set(harian["pasar"].to_list())) == ["blibli", "semua", "tokopedia"]


# --- wilayah --------------------------------------------------------------------

# (produk_key, sumber, kabkota_kode, nama_toko, harga per hari mulai 1 Jan; None = tidak muncul)
PRODUK = [
    ("a", "tokopedia", "35.78", "A", [10_000, 10_000, 11_000, 12_000]),   # Surabaya, Jatim
    ("b", "blibli", "32.75", "B", [20_000, 22_000, 22_000, 20_000]),      # Kota Bekasi, Jabar
    ("c", "tokopedia", "31.75", "C", [15_000, 15_000, 15_000, 18_000]),   # Jakarta Timur
    ("d", "tokopedia", None, "D", [30_000, 30_000, 30_000, 30_000]),      # kota tak dikenal
]


def gudang_wilayah(buat_gudang, produk, dengan_kode=True):
    baris = []
    for key, sumber, kab, toko, harga in produk:
        for h, hg in enumerate(harga, start=1):
            if hg is None:
                continue
            ada = dengan_kode and kab is not None
            baris.append({"tanggal": j(h), "produk_key": key, "sumber": sumber, "nama_toko": toko,
                          "harga_per_kg": hg, "kabkota_kode": kab if ada else None,
                          "provinsi_kode": kab[:2] if ada else None})
    return buat_gudang(baris)


def deret(harian, wilayah):
    return harian.filter(pl.col("wilayah") == wilayah).drop("wilayah")


def test_semua_tidak_terpengaruh_kode(buat_gudang):
    _, dengan = hitung(gudang_wilayah(buat_gudang, PRODUK), MULAI_TES)
    _, tanpa = hitung(gudang_wilayah(buat_gudang, PRODUK, dengan_kode=False), MULAI_TES)
    assert deret(dengan, "semua").equals(deret(tanpa, "semua"))
    assert set(tanpa["wilayah"]) == {"semua"}


def test_deret_provinsi_sama_dengan_dihitung_sendiri(buat_gudang):
    # indeks berantai, jendela 7 hari, dan lonjakan dihitung per wilayah, bukan dari deret semua
    _, semua = hitung(gudang_wilayah(buat_gudang, PRODUK), MULAI_TES)
    _, sendiri = hitung(gudang_wilayah(buat_gudang, PRODUK[:1]), MULAI_TES)
    assert deret(semua, "35").equals(deret(sendiri, "semua"))


def test_kelompok_jabodetabek(buat_gudang):
    _, harian = hitung(gudang_wilayah(buat_gudang, PRODUK), MULAI_TES)
    # b (Kota Bekasi) dan c (Jakarta Timur) masuk; a (Surabaya) dan d (tanpa kode) tidak
    assert nilai(harian, "jumlah_produk", wilayah="jabodetabek", pasar="semua", tanggal=j(1)) == 2


def test_tanpa_kode_hanya_di_semua(buat_gudang):
    _, harian = hitung(gudang_wilayah(buat_gudang, PRODUK), MULAI_TES)
    assert harian["wilayah"].null_count() == 0
    assert set(harian["wilayah"]) == {"semua", "jabodetabek", "35", "35.78", "32", "32.75",
                                      "31", "31.75"}
    assert nilai(harian, "jumlah_produk", wilayah="semua", pasar="semua", tanggal=j(1)) == 4


def test_daftar_wilayah(buat_gudang):
    # dua toko di Surabaya, satu Blibli satu Tokopedia, di tanggal berbeda
    baris, _ = hitung(gudang_wilayah(buat_gudang, [
        ("a", "tokopedia", "35.78", "A", [10_000, None]),
        ("e", "blibli", "35.78", "E", [None, 12_000]),
    ]), MULAI_TES)
    assert {"kabkota_kode", "provinsi_kode"} <= set(baris.columns)
    d = daftar_wilayah(baris)
    assert d.columns == ["wilayah", "pasar", "nama", "tingkat", "provinsi_kode", "kata_kunci",
                         "jumlah_toko"]
    assert nilai(d, "jumlah_toko", wilayah="35", pasar="semua") == 2
    assert nilai(d, "jumlah_toko", wilayah="35", pasar="blibli") == 1
    kab = d.filter((pl.col("wilayah") == "35.78") & (pl.col("pasar") == "semua")).row(0, named=True)
    assert (kab["tingkat"], kab["nama"], kab["provinsi_kode"]) == ("kabkota", "Kota Surabaya", "35")
    prov = d.filter((pl.col("wilayah") == "35") & (pl.col("pasar") == "semua")).row(0, named=True)
    assert (prov["tingkat"], prov["nama"]) == ("provinsi", "Jawa Timur")
    assert "jatim" in prov["kata_kunci"]
    assert "semua" not in d["wilayah"].to_list()
