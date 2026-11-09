from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pytest

from load.duckdb_loader import BATAS_PETA_INDUK, TABEL, catat_run, muat, peta_induk, siapkan
from transform import blibli, tokopedia
from transform.model import bangun
from transform.skema import SkemaBlibli, SkemaTokopedia, pisahkan

FIXTURE = Path(__file__).parent / "fixtures"
TANGGAL = date(2026, 11, 8)
BESOK = date(2026, 11, 9)
SKU_DEFAULT = "NAS-70965-00407-00001"       # opsi default di fixture
SKU_LAIN = "NAS-70965-00407-00002"


@pytest.fixture(scope="module")
def mentah_blibli():
    df = blibli.ubah(FIXTURE / "blibli" / "date=2026-11-08", TANGGAL)
    # satu baris tanpa harga → karantina tidak kosong
    rusak = df.filter(~pl.col("produk_id").eq("NAS-70965-00407"))["item_sku"][0]
    return df.with_columns(
        harga=pl.when(pl.col("item_sku") == rusak).then(None).otherwise(pl.col("harga")))


@pytest.fixture(scope="module")
def mentah_tokped():
    return tokopedia.ubah(FIXTURE / "tokopedia" / "date=2026-11-08", TANGGAL)


def paket(mentah: pl.DataFrame, sumber: str) -> dict:
    """Argumen `muat` dari satu tabel lapisan 1 (sebelum validasi)."""
    skema = SkemaBlibli if sumber == "blibli" else SkemaTokopedia
    lolos, karantina = pisahkan(mentah, skema, sumber)
    bintang = bangun(lolos, None) if sumber == "blibli" else bangun(None, lolos)
    return {"sumber": sumber, "tanggal": mentah["tanggal"][0], "lapisan1": lolos,
            "karantina": karantina, "bintang": bintang}


def ganti_tanggal(mentah: pl.DataFrame, tanggal: date) -> pl.DataFrame:
    return mentah.with_columns(tanggal=pl.lit(tanggal))


@pytest.fixture()
def con():
    c = duckdb.connect(":memory:")
    siapkan(c)
    yield c
    c.close()


def jumlah(con) -> dict[str, int]:
    return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABEL}


def muat_paket(con, p: dict) -> None:
    muat(con, p["sumber"], p["tanggal"], p["lapisan1"], p["karantina"], p["bintang"])


# --- siapkan --------------------------------------------------------------------

def test_siapkan_dua_kali_aman(con):
    siapkan(con)
    nama = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
    assert set(TABEL) | {"v_produk", "v_opsi_berubah"} <= nama


# --- muat -----------------------------------------------------------------------

def test_muat_isi_semua_tabel(con, mentah_blibli, mentah_tokped):
    b, t = paket(mentah_blibli, "blibli"), paket(mentah_tokped, "tokopedia")
    muat_paket(con, b)
    muat_paket(con, t)
    assert b["karantina"].height >= 1
    assert jumlah(con) == {
        "blibli_produk": b["lapisan1"].height,
        "tokopedia_produk": t["lapisan1"].height,
        "produk_karantina": b["karantina"].height + t["karantina"].height,
        "fakta_harga": b["bintang"].fakta_harga.height + t["bintang"].fakta_harga.height,
        "dim_produk": b["bintang"].dim_produk.height + t["bintang"].dim_produk.height,
        "dim_toko": b["bintang"].dim_toko.height + t["bintang"].dim_toko.height,
        "dim_tanggal": 1,
        "pipeline_runs": 0,
    }


def test_muat_dua_kali_jumlah_sama(con, mentah_blibli):
    p = paket(mentah_blibli, "blibli")
    muat_paket(con, p)
    sekali = jumlah(con)
    muat_paket(con, p)
    assert jumlah(con) == sekali


def test_muat_ulang_mengganti_bukan_menambah(con, mentah_blibli):
    muat_paket(con, paket(mentah_blibli, "blibli"))
    sebelum = jumlah(con)["fakta_harga"]
    muat_paket(con, paket(mentah_blibli.filter(pl.col("item_sku") != SKU_LAIN), "blibli"))
    assert jumlah(con)["fakta_harga"] == sebelum - 1
    assert con.execute("SELECT count(*) FROM fakta_harga WHERE item_sku = ?", [SKU_LAIN]).fetchone()[0] == 0


def test_tanggal_lain_tidak_tersentuh(con, mentah_blibli):
    a = paket(mentah_blibli, "blibli")
    muat_paket(con, a)
    muat_paket(con, paket(ganti_tanggal(mentah_blibli, BESOK), "blibli"))
    hitung = "SELECT count(*) FROM {} WHERE tanggal = ?"
    for tabel, harap in (("fakta_harga", a["bintang"].fakta_harga.height),
                         ("blibli_produk", a["lapisan1"].height),
                         ("produk_karantina", a["karantina"].height)):
        assert con.execute(hitung.format(tabel), [TANGGAL]).fetchone()[0] == harap, tabel
    assert jumlah(con)["dim_tanggal"] == 2


def test_sumber_lain_tidak_tersentuh(con, mentah_blibli, mentah_tokped):
    t = paket(mentah_tokped, "tokopedia")
    muat_paket(con, t)
    muat_paket(con, paket(mentah_blibli, "blibli"))
    muat_paket(con, paket(mentah_blibli, "blibli"))
    n = con.execute("SELECT count(*) FROM fakta_harga WHERE sumber = 'tokopedia'").fetchone()[0]
    assert n == t["bintang"].fakta_harga.height


def test_scd1_nama_terbaru_menang(con, mentah_blibli):
    muat_paket(con, paket(mentah_blibli, "blibli"))
    sebelum = jumlah(con)["dim_produk"]
    diganti = mentah_blibli.with_columns(
        nama=pl.when(pl.col("produk_id") == "NAS-70965-00407").then(pl.lit("Nama Baru"))
        .otherwise(pl.col("nama")))
    muat_paket(con, paket(diganti, "blibli"))
    nama = con.execute("SELECT nama FROM dim_produk WHERE produk_id = 'NAS-70965-00407'").fetchall()
    assert nama == [("Nama Baru",)]
    assert jumlah(con)["dim_produk"] == sebelum


def test_nama_tanggal_terbaru_menang_walau_dimuat_belakangan(con, mentah_blibli):
    # muat ulang tanggal lama sesudah tanggal baru tidak boleh mengembalikan nama lama
    baru = ganti_tanggal(mentah_blibli, BESOK).with_columns(
        nama=pl.when(pl.col("produk_id") == "NAS-70965-00407").then(pl.lit("Nama Baru"))
        .otherwise(pl.col("nama")),
        penjual=pl.lit("Toko Baru"))
    muat_paket(con, paket(baru, "blibli"))
    muat_paket(con, paket(mentah_blibli, "blibli"))     # tanggal lama, dimuat belakangan
    produk = con.execute("SELECT nama, tanggal_terakhir FROM dim_produk "
                         "WHERE produk_id = 'NAS-70965-00407'").fetchall()
    assert produk == [("Nama Baru", BESOK)]
    assert {r[0] for r in con.execute("SELECT nama_toko FROM dim_toko").fetchall()} == {"Toko Baru"}


def test_galat_di_tengah_dibatalkan(con, mentah_blibli, mentah_tokped):
    muat_paket(con, paket(mentah_tokped, "tokopedia"))
    muat_paket(con, paket(mentah_blibli, "blibli"))
    sebelum = jumlah(con)
    nama_sebelum = con.execute("SELECT nama FROM dim_produk ORDER BY produk_key").fetchall()

    p = paket(mentah_blibli.with_columns(nama=pl.lit("Tidak Boleh Masuk")), "blibli")
    rusak = p["bintang"].fakta_harga.with_columns(harga=pl.lit("bukan angka"))
    p["bintang"] = replace(p["bintang"], fakta_harga=rusak)
    with pytest.raises(duckdb.Error):
        muat_paket(con, p)

    assert jumlah(con) == sebelum
    assert con.execute("SELECT nama FROM dim_produk ORDER BY produk_key").fetchall() == nama_sebelum


def test_data_sumber_atau_tanggal_lain_ditolak(con, mentah_blibli):
    p = paket(mentah_blibli, "blibli")
    with pytest.raises(ValueError, match="tanggal"):
        muat(con, "blibli", BESOK, p["lapisan1"], p["karantina"], p["bintang"])
    with pytest.raises(ValueError, match="sumber"):
        muat(con, "tokopedia", TANGGAL, p["lapisan1"], p["karantina"], p["bintang"])
    assert set(jumlah(con).values()) == {0}


def test_dimensi_tanpa_fakta_dihapus(con, mentah_tokped):
    # tanggal lama dimuat tanpa induk → kartu jadi produk sendiri; dimuat ulang dengan induk → produk itu hilang
    lama = ganti_tanggal(mentah_tokped, date(2026, 11, 7)).with_columns(induk_id=pl.lit(None, pl.Utf8))
    muat_paket(con, paket(lama, "tokopedia"))
    sendiri = "SELECT count(*) FROM dim_produk WHERE produk_id = '103999725486'"
    assert con.execute(sendiri).fetchone()[0] == 1
    muat_paket(con, paket(ganti_tanggal(mentah_tokped, date(2026, 11, 7)), "tokopedia"))
    assert con.execute(sendiri).fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM dim_produk WHERE produk_key NOT IN "
                       "(SELECT produk_key FROM fakta_harga)").fetchone()[0] == 0


# --- peta induk (keputusan 9 Nov: hanya tanggal lama) ----------------------------

def test_peta_induk_dari_gudang(con, mentah_tokped):
    muat_paket(con, paket(ganti_tanggal(mentah_tokped, BESOK), "tokopedia"))
    peta = peta_induk(con, BATAS_PETA_INDUK)
    assert dict(peta.rows())["103999725486"] == "103388173219"
    assert peta["induk_id"].null_count() == 0


def test_peta_induk_tidak_dipakai_sesudah_batas(con, mentah_tokped):
    muat_paket(con, paket(ganti_tanggal(mentah_tokped, BESOK), "tokopedia"))
    assert BATAS_PETA_INDUK == date(2026, 11, 8)
    assert peta_induk(con, BATAS_PETA_INDUK + timedelta(days=1)) is None


def test_tanggal_lama_dimuat_ulang_ikut_induk(con, mentah_tokped):
    muat_paket(con, paket(ganti_tanggal(mentah_tokped, BESOK), "tokopedia"))
    lama = ganti_tanggal(mentah_tokped, date(2026, 11, 7)).filter(pl.col("opsi_default")).with_columns(
        induk_id=pl.lit(None, pl.Utf8), variant=pl.lit(None, pl.Utf8))
    lolos, karantina = pisahkan(lama, SkemaTokopedia, "tokopedia")
    b = bangun(None, lolos, peta_induk=peta_induk(con, date(2026, 11, 7)))
    muat(con, "tokopedia", date(2026, 11, 7), lolos, karantina, b)
    hasil = con.execute("SELECT p.produk_id FROM fakta_harga f JOIN dim_produk p USING (produk_key) "
                        "WHERE f.item_sku = '103999725486' ORDER BY f.tanggal").fetchall()
    assert hasil == [("103388173219",), ("103388173219",)]


# --- view -----------------------------------------------------------------------

def test_v_produk_satu_baris_per_fakta(con, mentah_blibli, mentah_tokped):
    muat_paket(con, paket(mentah_blibli, "blibli"))
    muat_paket(con, paket(mentah_tokped, "tokopedia"))
    v = con.sql("FROM v_produk").pl()
    assert v.height == jumlah(con)["fakta_harga"]
    assert {"nama", "jenis_buah", "asal", "nama_toko", "region", "hari"} <= set(v.columns)
    baris = v.filter(pl.col("item_sku") == SKU_LAIN).row(0, named=True)
    assert (baris["harga_per_kg"], baris["sumber"], baris["hari"]) == (84900, "blibli", "Minggu")


def test_v_opsi_berubah(con, mentah_blibli):
    muat_paket(con, paket(mentah_blibli, "blibli"))
    besok = ganti_tanggal(mentah_blibli, BESOK).with_columns(
        opsi_default=pl.when(pl.col("item_sku") == SKU_DEFAULT).then(False)
        .when(pl.col("item_sku") == SKU_LAIN).then(True)
        .otherwise(pl.col("opsi_default")))
    muat_paket(con, paket(besok, "blibli"))
    v = con.sql("FROM v_opsi_berubah").pl()
    assert v.select("tanggal", "produk_id", "item_sku_sebelumnya", "item_sku").rows() == [
        (BESOK, "NAS-70965-00407", SKU_DEFAULT, SKU_LAIN)]


# --- pipeline_runs ----------------------------------------------------------------

def test_catat_run(con):
    run = {"run_id": "r1", "mulai": datetime(2026, 11, 9, 6, 0), "selesai": datetime(2026, 11, 9, 6, 5),
           "sumber": "blibli", "tanggal": TANGGAL, "halaman_ditarik": 12, "baris_mentah": 32,
           "baris_dimuat": 31, "baris_karantina": 1, "status": "berhasil", "pesan_galat": None}
    catat_run(con, run)
    hasil = con.sql("FROM pipeline_runs").pl().row(0, named=True)
    assert hasil == run


def test_catat_run_status_salah_ditolak(con):
    with pytest.raises(duckdb.ConstraintException):
        catat_run(con, {"run_id": "r2", "sumber": "blibli", "tanggal": TANGGAL, "status": "aneh"})
