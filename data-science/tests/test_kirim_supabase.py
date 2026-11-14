import json
from datetime import date, timedelta

import polars as pl
import pytest

from dashboard_manalagi import hitung
from kirim_supabase import (
    KOLOM_BARIS, KOLOM_HARIAN, baca_terkirim, kelompokkan, muatan, simpan_terkirim,
    tanggal_berubah, untuk_dikirim,
)
from tests.conftest import MULAI_TES


def j(hari: int) -> date:
    return date(2026, 1, hari)


def data_dari(buat_gudang, harga: dict[tuple[str, int], int]):
    """Data siap kirim dari {(produk_key, hari Januari): harga_per_kg}."""
    con = buat_gudang([{"tanggal": j(h), "produk_key": k, "harga_per_kg": v} for (k, h), v in harga.items()])
    return untuk_dikirim(*hitung(con, MULAI_TES))


def datar(produk: str, hari) -> dict:
    return {(produk, h): 10_000 for h in hari}


def test_untuk_dikirim_hanya_kolom_disetujui(buat_gudang):
    baris, harian = data_dari(buat_gudang, datar("a", range(1, 6)))

    assert baris.columns == KOLOM_BARIS
    assert harian.columns == KOLOM_HARIAN


def test_tanpa_salinan_semua_tanggal(buat_gudang):
    data = data_dari(buat_gudang, datar("a", (1, 2, 3)))

    assert tanggal_berubah(data, None) == [j(1), j(2), j(3)]


def test_hitungan_sama_tidak_ada_yang_berubah(buat_gudang):
    harga = {**datar("a", range(1, 10)), ("b", 1): 21_000, ("b", 4): 23_500, ("b", 9): 19_999,
             ("c", 2): 33_333, ("c", 3): 34_567}
    pertama = data_dari(buat_gudang, harga)
    kedua = data_dari(buat_gudang, harga)   # koneksi baru, seperti jalan 12:00 sesudah 06:00

    assert tanggal_berubah(kedua, pertama) == []


def test_tanggal_susulan_mengubah_tanggal_sesudahnya(buat_gudang):
    lama = data_dari(buat_gudang, datar("a", (1, 2, 4, 5)))
    baru = data_dari(buat_gudang, datar("a", (1, 2, 3, 4, 5)))

    # 3 Jan baru; 4 Jan kini punya 3 hari dalam jendela, jadi rasio_jendela terisi.
    # 5 Jan sudah punya 3 hari (1, 2, 4) sebelumnya, nilainya tidak berubah.
    assert tanggal_berubah(baru, lama) == [j(3), j(4)]


def test_tanggal_yang_hilang_ikut_berubah(buat_gudang):
    lama = data_dari(buat_gudang, datar("a", (1, 2)))
    baru = data_dari(buat_gudang, datar("a", (2,)))

    assert j(1) in tanggal_berubah(baru, lama)


def test_kelompokkan():
    tanggal = [j(1) + timedelta(days=i) for i in range(65)]

    kelompok = kelompokkan(tanggal)

    assert [len(k) for k in kelompok] == [31, 31, 3]
    assert [t for k in kelompok for t in k] == tanggal


def test_muatan_hanya_tanggal_diminta_dan_json_aman(buat_gudang):
    data = data_dari(buat_gudang, datar("a", (1, 2, 3)))

    m = muatan([j(1)], data)

    assert m["p_tanggal"] == ["2026-01-01"]
    assert {b["tanggal"] for b in m["p_baris"]} == {"2026-01-01"}
    assert {(h["tanggal"], h["pasar"]) for h in m["p_harian"]} == {("2026-01-01", "semua"), ("2026-01-01", "tokopedia")}
    assert m["p_baris"][0]["rasio_jendela"] is None
    json.dumps(m, allow_nan=False)


def test_simpan_terkirim_mengganti_tanggal_saja(buat_gudang, tmp_path):
    lama = data_dari(buat_gudang, datar("a", (1, 2, 3)))
    baru = data_dari(buat_gudang, {("a", 1): 10_000, ("a", 2): 99_000, ("a", 3): 10_000})
    assert baca_terkirim(tmp_path) is None

    salinan = simpan_terkirim(tmp_path, lama, baru, [j(2)])

    for tabel, s, l, b in zip(("baris", "harian"), salinan, lama, baru):
        assert s.filter(pl.col("tanggal") != j(2)).equals(l.filter(pl.col("tanggal") != j(2))), tabel
        assert s.filter(pl.col("tanggal") == j(2)).equals(b.filter(pl.col("tanggal") == j(2))), tabel
    dibaca = baca_terkirim(tmp_path)
    assert dibaca[0].equals(salinan[0]) and dibaca[1].equals(salinan[1])
    assert not list(tmp_path.glob("*.sementara"))


# ---------- Task 5: kunci, pengirim, jalankan ----------
from kirim_supabase import baca_kunci, buat_pengirim, jalankan  # noqa: E402


def data_tanggal(n: int, harga: int = 10_000):
    """Data siap kirim berisi n tanggal berturut-turut sejak 1 Jan (satu produk, pasar `semua`)."""
    tanggal = [j(1) + timedelta(days=i) for i in range(n)]
    baris = pl.DataFrame({
        "tanggal": tanggal, "sumber": ["tokopedia"] * n, "produk_key": ["a"] * n,
        "nama_toko": ["Toko"] * n, "kota": ["Jakarta"] * n, "harga_per_kg": [harga] * n,
        "terjual_min": [None] * n, "median_jendela": [None] * n, "rasio_jendela": [None] * n,
        "lonjak_toko": [False] * n,
    }, schema_overrides={"terjual_min": pl.Int64, "median_jendela": pl.Float64, "rasio_jendela": pl.Float64})
    harian = pl.DataFrame({
        "tanggal": tanggal, "pasar": ["semua"] * n, "jumlah_produk": [1] * n,
        "median": [float(harga)] * n, "indeks_berantai": [float(harga)] * n, "median_rasio": [None] * n,
        "lonjak_pasar": [False] * n, "naik": [0] * n, "turun": [0] * n,
    }, schema_overrides={"median_rasio": pl.Float64})
    return baris, harian


class PengirimPalsu:
    def __init__(self, gagal_pada: int | None = None):
        self.muatan = []
        self.gagal_pada = gagal_pada

    def __call__(self, m: dict) -> None:
        if self.gagal_pada is not None and len(self.muatan) + 1 == self.gagal_pada:
            raise RuntimeError("Supabase 503: palsu")
        self.muatan.append(m)

    @property
    def tanggal(self) -> list[str]:
        return [t for m in self.muatan for t in m["p_tanggal"]]


def test_baca_kunci_env_mengalahkan_berkas(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("# komentar\n\nNEXT_PUBLIC_SUPABASE_URL=https://berkas.supabase.co\n"
                   "SUPABASE_SERVICE_ROLE_KEY=kunci-berkas\n", encoding="utf-8")

    assert baca_kunci(env, {}) == ("https://berkas.supabase.co", "kunci-berkas")
    assert baca_kunci(env, {"NEXT_PUBLIC_SUPABASE_URL": "http://127.0.0.1:54321",
                            "SUPABASE_SERVICE_ROLE_KEY": "kunci-env"}) == ("http://127.0.0.1:54321", "kunci-env")


def test_baca_kunci_tidak_ada_menyebut_nama(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("NEXT_PUBLIC_SUPABASE_URL=https://x.supabase.co\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as galat:
        baca_kunci(env, {})
    assert "SUPABASE_SERVICE_ROLE_KEY" in str(galat.value)
    with pytest.raises(RuntimeError):
        baca_kunci(tmp_path / "tidak-ada", {})


def test_pengirim_header_dan_galat():
    panggilan = []

    class Jawaban:
        def __init__(self, status):
            self.status_code, self.text = status, '{"message":"JWT invalid"}'

    def post(url, **kw):
        panggilan.append((url, kw))
        return Jawaban(204 if len(panggilan) == 1 else 401)

    kirim = buat_pengirim("https://x.supabase.co/", "kunci-rahasia", post=post)
    kirim({"p_tanggal": []})

    url, kw = panggilan[0]
    assert url == "https://x.supabase.co/rest/v1/rpc/ganti_pasar_manalagi"
    assert kw["headers"]["apikey"] == "kunci-rahasia"
    assert kw["headers"]["Authorization"] == "Bearer kunci-rahasia"
    assert kw["json"] == {"p_tanggal": []}
    with pytest.raises(RuntimeError, match="401") as galat:
        kirim({"p_tanggal": []})
    assert "kunci-rahasia" not in str(galat.value)


def test_jalankan_pertama_mengirim_semua_lalu_tidak_ada(tmp_path):
    data = data_tanggal(5)
    kirim = PengirimPalsu()

    assert jalankan(data, tmp_path, kirim) == 5
    assert jalankan(data_tanggal(5), tmp_path, kirim) == 0
    assert len(kirim.muatan) == 1


def test_jalankan_menolak_hasil_kosong(tmp_path):
    jalankan(data_tanggal(3), tmp_path, PengirimPalsu())
    sebelum = baca_terkirim(tmp_path)
    kosong = tuple(df.clear() for df in data_tanggal(1))
    kirim = PengirimPalsu()

    with pytest.raises(RuntimeError, match="kosong"):
        jalankan(kosong, tmp_path, kirim)
    assert kirim.muatan == []
    assert baca_terkirim(tmp_path)[0].equals(sebelum[0])


def test_gagal_di_tengah_salinan_hanya_kelompok_yang_berhasil(tmp_path):
    data = data_tanggal(40)

    with pytest.raises(RuntimeError, match="503"):
        jalankan(data, tmp_path, PengirimPalsu(gagal_pada=2))
    assert baca_terkirim(tmp_path)[0].height == 31

    kirim = PengirimPalsu()
    assert jalankan(data, tmp_path, kirim) == 9
    assert kirim.tanggal == [(j(1) + timedelta(days=i)).isoformat() for i in range(31, 40)]


def test_semua_mengirim_semua_tanggal(tmp_path):
    data = data_tanggal(5)
    jalankan(data, tmp_path, PengirimPalsu())
    kirim = PengirimPalsu()

    assert jalankan(data, tmp_path, kirim, semua=True) == 5
    assert len(kirim.tanggal) == 5


def test_coba_tidak_mengirim_tidak_menyimpan(tmp_path):
    kirim = PengirimPalsu()

    assert jalankan(data_tanggal(5), tmp_path, kirim, coba=True) == 5
    assert kirim.muatan == []
    assert baca_terkirim(tmp_path) is None


def test_semua_juga_menghapus_tanggal_yang_hilang(tmp_path):
    jalankan(data_tanggal(5), tmp_path, PengirimPalsu())
    kirim = PengirimPalsu()

    assert jalankan(data_tanggal(4), tmp_path, kirim, semua=True) == 5
    assert "2026-01-05" in kirim.tanggal
    assert baca_terkirim(tmp_path)[0].height == 4


# ---------- Perbaikan sesudah review akhir ----------
from kirim_supabase import folder_terkirim  # noqa: E402


def test_salinan_terpisah_per_supabase(tmp_path):
    produksi = folder_terkirim(tmp_path, "https://abcd.supabase.co")
    lokal = folder_terkirim(tmp_path, "http://127.0.0.1:54321")

    assert produksi != lokal
    assert produksi == folder_terkirim(tmp_path, "https://abcd.supabase.co/")
    assert produksi.parent == lokal.parent == tmp_path


def test_semua_gagal_di_tengah_jalan_biasa_mengirim_sisanya(tmp_path):
    data = data_tanggal(40)
    jalankan(data, tmp_path, PengirimPalsu())        # salinan lengkap; lalu Supabase dikosongkan

    with pytest.raises(RuntimeError, match="503"):
        jalankan(data, tmp_path, PengirimPalsu(gagal_pada=2), semua=True)
    kirim = PengirimPalsu()

    assert jalankan(data, tmp_path, kirim) == 9
    assert kirim.tanggal == [(j(1) + timedelta(days=i)).isoformat() for i in range(31, 40)]


def test_baca_kunci_url_env_tanpa_kunci_env_ditolak(tmp_path):
    env = tmp_path / ".env.local"
    env.write_text("NEXT_PUBLIC_SUPABASE_URL=https://produksi.supabase.co\n"
                   "SUPABASE_SERVICE_ROLE_KEY=kunci-produksi\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        baca_kunci(env, {"NEXT_PUBLIC_SUPABASE_URL": "http://127.0.0.1:54321"})
