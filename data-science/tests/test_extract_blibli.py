from datetime import date

from extract.blibli import HalamanHabis, RingkasanGagal, tarik
from extract.http import AmbilGagal

TANGGAL = date(2026, 10, 18)


def jawaban_palsu(total_halaman):
    return {"data": {"products": [{"id": "x"}], "paging": {"total_page": total_halaman}}}


def berkas_tersimpan(akar):
    return sorted(p.name for p in (akar / "raw" / "blibli" / "date=2026-10-18").iterdir())


def test_menarik_semua_halaman_kedua_kategori(tmp_path):
    def ambil(kategori, halaman):
        return jawaban_palsu(2)

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "berhasil"
    assert hasil.halaman == 4
    assert berkas_tersimpan(tmp_path) == [
        "BU-1000190_page_001.json",
        "BU-1000190_page_002.json",
        "BU-1000191_page_001.json",
        "BU-1000191_page_002.json",
    ]


def test_422_setelah_halaman_terakhir_berarti_selesai(tmp_path):
    def ambil(kategori, halaman):
        if halaman >= 21:
            raise HalamanHabis("422")
        return jawaban_palsu(25)

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "berhasil"
    nama = berkas_tersimpan(tmp_path)
    assert len([n for n in nama if n.startswith("BU-1000190")]) == 20
    assert len([n for n in nama if n.startswith("BU-1000191")]) == 20


def test_halaman_habis_di_tengah_bukan_galat(tmp_path):
    def ambil(kategori, halaman):
        if halaman >= 3:
            raise HalamanHabis("422")
        return jawaban_palsu(5)

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "berhasil"
    assert hasil.halaman == 4


def test_halaman_pertama_gagal_berarti_gagal(tmp_path):
    def ambil(kategori, halaman):
        raise AmbilGagal("server mati")

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "gagal"
    assert hasil.halaman == 0


def test_gagal_di_tengah_berarti_sebagian(tmp_path):
    def ambil(kategori, halaman):
        if kategori == "BU-1000191" and halaman == 2:
            raise AmbilGagal("putus")
        return jawaban_palsu(3)

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, tidur=lambda s: None)

    assert hasil.status == "sebagian"
    assert hasil.halaman == 4
    assert "BU-1000191_page_001.json" in berkas_tersimpan(tmp_path)


# --- Tarikan varian: harga setiap opsi produk yang punya varian ---

def halaman_dengan(produk):
    return {"data": {"products": produk, "paging": {"total_page": 1}}}


def ringkasan_palsu(kode_terpilih, *kode_lain):
    """Jawaban _summary: opsi terpilih (default) + opsi lain, seperti data.options Blibli."""
    opsi = [{"id": f"is--{kode_terpilih}_PP-1", "selected": True}]
    opsi += [{"id": f"is--{kode}_PP-1", "selected": False} for kode in kode_lain]
    return {"code": 200, "data": {"itemSku": kode_terpilih, "options": opsi}}


def berkas_varian(akar):
    folder = akar / "raw" / "blibli" / "date=2026-10-18" / "varian"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def test_produk_bervarian_disimpan_ringkasan_dan_opsi_lainnya(tmp_path):
    def ambil(kategori, halaman):
        if kategori == "BU-1000190":
            return halaman_dengan([{"id": "A", "hasVariants": True}, {"id": "B", "hasVariants": False}])
        return halaman_dengan([{"id": "C"}])

    dipanggil = []

    def ambil_ringkasan(kode):
        dipanggil.append(kode)
        if kode == "ps--A":
            return ringkasan_palsu("A-00001", "A-00002")
        return {"code": 200, "data": {"itemSku": "A-00002", "options": []}}

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, ambil_ringkasan=ambil_ringkasan,
                  tidur=lambda s: None)

    assert hasil.status == "berhasil"
    assert dipanggil == ["ps--A", "is--A-00002"]
    assert berkas_varian(tmp_path) == ["is--A-00002.json", "ps--A.json"]


def test_produk_sama_di_dua_kategori_ditarik_sekali(tmp_path):
    def ambil(kategori, halaman):
        return halaman_dengan([{"id": "A", "hasVariants": True}])

    dipanggil = []

    def ambil_ringkasan(kode):
        dipanggil.append(kode)
        return ringkasan_palsu("A-00001")

    tarik(TANGGAL, tmp_path, ambil_halaman=ambil, ambil_ringkasan=ambil_ringkasan,
          tidur=lambda s: None)

    assert dipanggil == ["ps--A"]


def test_satu_varian_gagal_tidak_menggagalkan_tarikan(tmp_path):
    def ambil(kategori, halaman):
        if kategori == "BU-1000190":
            return halaman_dengan([{"id": "A", "hasVariants": True}, {"id": "B", "hasVariants": True}])
        return halaman_dengan([{"id": "C"}])

    def ambil_ringkasan(kode):
        if kode == "ps--A":
            raise RingkasanGagal("HTTP 404")
        return ringkasan_palsu("B-00001")

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, ambil_ringkasan=ambil_ringkasan,
                  tidur=lambda s: None)

    assert hasil.status == "berhasil"
    assert "1 gagal" in hasil.pesan
    assert berkas_varian(tmp_path) == ["ps--B.json"]


def test_semua_varian_gagal_berarti_sebagian(tmp_path):
    def ambil(kategori, halaman):
        return halaman_dengan([{"id": kategori, "hasVariants": True}])

    def ambil_ringkasan(kode):
        raise AmbilGagal("diblokir")

    hasil = tarik(TANGGAL, tmp_path, ambil_halaman=ambil, ambil_ringkasan=ambil_ringkasan,
                  tidur=lambda s: None)

    assert hasil.status == "sebagian"
    assert hasil.halaman == 2
    assert "2 gagal" in hasil.pesan
