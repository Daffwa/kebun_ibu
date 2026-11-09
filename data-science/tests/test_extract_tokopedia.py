from datetime import date

from extract.http import AmbilGagal
from extract.tokopedia import produk_dari_jawaban, tarik

TANGGAL = date(2026, 10, 19)


def jawaban_palsu(produk):
    return [{"data": {"searchProductV5": {"data": {"products": produk}}}}]


def berkas_tersimpan(akar):
    return sorted(p.name for p in (akar / "raw" / "tokopedia" / "date=2026-10-19").iterdir())


def test_produk_dari_jawaban():
    produk = [{"id": 1, "name": "Mangga"}, {"id": 2, "name": "Pisang"}]

    assert produk_dari_jawaban(jawaban_palsu(produk)) == produk


def test_berhenti_di_halaman_kosong(tmp_path):
    def ambil(halaman):
        return jawaban_palsu([{"id": halaman}] if halaman <= 3 else [])

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "berhasil"
    assert hasil.halaman == 3
    assert berkas_tersimpan(tmp_path) == ["page_001.json", "page_002.json", "page_003.json"]


def test_berhenti_di_halaman_100(tmp_path):
    def ambil(halaman):
        return jawaban_palsu([{"id": halaman}])

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "berhasil"
    assert hasil.halaman == 100
    assert len(berkas_tersimpan(tmp_path)) == 100


def test_halaman_pertama_gagal_berarti_gagal(tmp_path):
    def ambil(halaman):
        raise AmbilGagal("diblokir")

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "gagal"
    assert hasil.halaman == 0


def test_gagal_di_tengah_berarti_sebagian(tmp_path):
    def ambil(halaman):
        if halaman == 3:
            raise AmbilGagal("putus")
        return jawaban_palsu([{"id": halaman}])

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "sebagian"
    assert hasil.halaman == 2
    assert berkas_tersimpan(tmp_path) == ["page_001.json", "page_002.json"]


# --- Halaman produk Mangga Manalagi (spec 4.2, keputusan 13 #11 = a) ---

import json

import pytest

from extract.http import KesalahanSementara
from extract.tokopedia import cache_dari_html


def kartu(id_, nama, url=None):
    return {"id": id_, "name": nama, "url": url or f"https://www.tokopedia.com/toko/p{id_}?extParam=x"}


def cache_palsu(berat=0.5):
    return {"$x.basicInfo": {"__typename": "pdpBasicInfo", "weight": berat, "weightUnit": "KILOGRAM"}}


def berkas_halaman(akar):
    folder = akar / "raw" / "tokopedia" / "date=2026-10-19" / "halaman"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def tarik_dengan(akar, halaman_cari, ambil_produk):
    """halaman_cari: daftar kartu per halaman (halaman setelahnya kosong)."""
    def ambil(n):
        return jawaban_palsu(halaman_cari[n - 1] if n <= len(halaman_cari) else [])
    return tarik(TANGGAL, akar, ambil_halaman=ambil, ambil_produk=ambil_produk, tidur=lambda s: None)


def test_cache_dari_html_membaca_window_cache():
    html = '<script>window.__cache={"a":{"__typename":"pdpBasicInfo","weight":1}};window.x=1</script>'

    assert cache_dari_html(html) == {"a": {"__typename": "pdpBasicInfo", "weight": 1}}


@pytest.mark.parametrize("html", [
    "<html>tanpa cache</html>",
    '<script>window.__cache={"a":{"__typename":"Lain"}};</script>',
])
def test_halaman_kosong_dianggap_kesalahan_sementara(html):
    with pytest.raises(KesalahanSementara):
        cache_dari_html(html)


def test_halaman_produk_manalagi_disimpan(tmp_path):
    dipanggil = []

    def ambil_produk(url):
        dipanggil.append(url)
        return cache_palsu()

    hasil = tarik_dengan(tmp_path, [[kartu(1, "Mangga Manalagi 1 kg"), kartu(2, "Pisang Cavendish")]],
                         ambil_produk)

    assert hasil.status == "berhasil"
    assert dipanggil == ["https://www.tokopedia.com/toko/p1"]
    assert berkas_halaman(tmp_path) == ["1.json"]
    jalur = tmp_path / "raw" / "tokopedia" / "date=2026-10-19" / "halaman" / "1.json"
    assert json.loads(jalur.read_text(encoding="utf-8")) == cache_palsu()
    assert "halaman produk: 1, 0 gagal" in hasil.pesan


def test_produk_sama_di_dua_halaman_ditarik_sekali(tmp_path):
    dipanggil = []

    def ambil_produk(url):
        dipanggil.append(url)
        return cache_palsu()

    tarik_dengan(tmp_path, [[kartu(1, "Mangga Manalagi")], [kartu(1, "Mangga Manalagi")]], ambil_produk)

    assert dipanggil == ["https://www.tokopedia.com/toko/p1"]


def test_halaman_kosong_dicoba_ulang(tmp_path):
    percobaan = []

    def ambil_produk(url):
        percobaan.append(url)
        if len(percobaan) < 3:
            raise KesalahanSementara("halaman kosong")
        return cache_palsu()

    hasil = tarik_dengan(tmp_path, [[kartu(1, "Mangga Manalagi")]], ambil_produk)

    assert len(percobaan) == 3
    assert berkas_halaman(tmp_path) == ["1.json"]
    assert hasil.status == "berhasil"


def test_satu_produk_gagal_tidak_menggagalkan_tarikan(tmp_path):
    def ambil_produk(url):
        if url.endswith("p1"):
            raise KesalahanSementara("halaman kosong")
        return cache_palsu()

    hasil = tarik_dengan(tmp_path, [[kartu(1, "Mangga Manalagi"), kartu(2, "Mangga Manalagi Madu 2kg")]],
                         ambil_produk)

    assert hasil.status == "berhasil"
    assert "halaman produk: 1, 1 gagal" in hasil.pesan
    assert berkas_halaman(tmp_path) == ["2.json"]


def test_semua_produk_gagal_berarti_sebagian(tmp_path):
    def ambil_produk(url):
        raise KesalahanSementara("halaman kosong")

    hasil = tarik_dengan(tmp_path, [[kartu(1, "Mangga Manalagi")]], ambil_produk)

    assert hasil.status == "sebagian"
    assert hasil.halaman == 1
    assert "halaman produk: 0, 1 gagal" in hasil.pesan


def test_tanpa_manalagi_tidak_menarik_halaman_produk(tmp_path):
    def ambil_produk(url):
        raise AssertionError("tidak boleh dipanggil")

    hasil = tarik_dengan(tmp_path, [[kartu(1, "Apel Fuji")]], ambil_produk)

    assert hasil.status == "berhasil"
    assert hasil.pesan is None
    assert berkas_halaman(tmp_path) == []
