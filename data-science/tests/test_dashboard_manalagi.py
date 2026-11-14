from datetime import date

import pytest

from dashboard_manalagi import hitung
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
    assert len(baris.columns) == 16


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
