"""Alat tes bersama."""
from datetime import date

import duckdb
import pytest

_KOLOM_V_PRODUK = {
    "tanggal": "DATE", "sumber": "VARCHAR", "produk_key": "VARCHAR", "nama": "VARCHAR",
    "nama_toko": "VARCHAR", "kota": "VARCHAR", "harga": "BIGINT", "berat_gram": "BIGINT",
    "harga_per_kg": "BIGINT", "terjual_min": "BIGINT", "jenis_buah": "VARCHAR",
    "opsi_default": "BOOLEAN", "olahan": "BOOLEAN",
    "kabkota_kode": "VARCHAR", "provinsi_kode": "VARCHAR",
}
_BAWAAN = {
    "sumber": "tokopedia", "nama": "Mangga Manalagi 1 kg", "nama_toko": "Toko", "kota": "Jakarta",
    "harga": None, "berat_gram": 1000, "terjual_min": None, "jenis_buah": "mangga",
    "opsi_default": True, "olahan": False,
    "kabkota_kode": None, "provinsi_kode": None,
}
MULAI_TES = {"blibli": date(2026, 1, 1), "tokopedia": date(2026, 1, 1)}


def gudang_palsu(baris: list[dict]) -> duckdb.DuckDBPyConnection:
    """DuckDB di memori dengan TABEL `v_produk` berkolom yang dibaca dashboard_manalagi.

    Setiap dict minimal berisi tanggal, produk_key, harga_per_kg; sisanya memakai _BAWAAN.
    """
    con = duckdb.connect()
    con.execute("CREATE TABLE v_produk (" + ", ".join(f"{k} {t}" for k, t in _KOLOM_V_PRODUK.items()) + ")")
    for b in baris:
        isi = {**_BAWAAN, **b}
        con.execute(f"INSERT INTO v_produk VALUES ({', '.join('?' * len(_KOLOM_V_PRODUK))})",
                    [isi[k] for k in _KOLOM_V_PRODUK])
    return con


@pytest.fixture
def buat_gudang():
    dibuka = []

    def buat(baris: list[dict]) -> duckdb.DuckDBPyConnection:
        con = gudang_palsu(baris)
        dibuka.append(con)
        return con

    yield buat
    for con in dibuka:
        con.close()
