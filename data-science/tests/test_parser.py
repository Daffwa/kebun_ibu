import pytest

from transform.parser import (
    berat_dari_slug,
    berat_gram,
    jenis_satuan,
    jumlah_buah,
    mangga_manalagi,
    pilih_berat,
    satuan_baris,
)


@pytest.mark.parametrize("nama,gram", [
    # Mangga Manalagi asli (target utama)
    ("MANGGA MANALAGI 170 - 180 G", 175),
    ("Mangga Manalagi 1 kg ( 0.9 - 1.1 kg / pack)", 1000),       # berat sama ditulis dua kali
    ("Mangga Manalagi 500 gram ( 400 - 500 gram / pack)", 500),  # berat tunggal di dalam rentang
    ("Mangga manalagi segar manis 1/2 kg", 500),                 # pecahan DIBACA
    ("Mangga Manalagi 900g - 1 Kg", 950),                        # rentang, satuan di dua ujung (Tokopedia asli)
    ("Mangga manalagi madu (Arum )fres & segar  tua pohon 1kg isi 3-5 buah.", 1000),
    ("Mangga Manalagi Super Kiloan Raja Alpukat", 1000),         # kiloan = 1 kg
    ("Mangga Manalagi Potong Manis", None),                      # tanpa berat
    ("Mangga Manalagi Madu", None),
    # aturan umum
    ("PEPAYA CALIFORNIA 1300 - 1500 GR", 1400),
    ("MANGGA HARUMANIS 470 - 500 G", 485),
    ("Avocadron Alpukat Mentega Mini [Paket 2 Kg]", 2000),
    ("Castle Farms Kurma Ajwa 500gr", 500),
    ("Anggur 1,5kg", 1500),
    ("Apel 2.5 kg", 2500),
    ("Jeruk 0,95kg", 950),
    ("Salak Pondoh 1.000 gr", 1000),                             # titik + 3 angka = ribuan
    ("Jeruk songkit ijo 500 grm", 500),
    ("Alpukat Mentega 1 KILO", 1000),
    ("Jeruk Medan 1/4Kg", 250),
    ("Duku 5 ons", 500),
    ("Pisang sekilo", 1000),
    ("Anggur setengah kilo", 500),
    ("Mangga isi 3-5/ kg", 1000),
    ("Kelengkeng per kg", 1000),
    ("Apel Fuji 1 Kg 1/2 Kg", None),                             # dua pilihan berbeda
    ("Apel 1 kg isi 6 pcs", 1000),                               # berat menang atas jumlah
    ("Kiwi Green 4s Impor 1 pack", None),
    ("Semangka 30 kg", None),                                    # di atas 20.000 g
    ("Cabe 50 g", None),                                         # di bawah 100 g
    ("Mangga +-0.9g-1kg", None),                                 # salah ketik, dua berat beda
    ("", None),
    (None, None),
])
def test_berat_gram(nama, gram):
    assert berat_gram(nama) == gram


def test_berat_gram_mengembalikan_int():
    assert isinstance(berat_gram("Anggur 1,5kg"), int)


@pytest.mark.parametrize("url,gram", [
    ("https://www.tokopedia.com/toko/mangga-manalagi-madu-1-kg?extParam=x", 1000),
    ("https://www.tokopedia.com/toko/mangga-manalagi-1-2-kg", None),   # ambigu: 1/2? 1.2? 1-2?
    ("https://www.tokopedia.com/toko/mangga-manalagi-500gr-1731543572100384126", 500),
    ("https://www.tokopedia.com/toko/mangga-manalagi-madu", None),
    (None, None),
])
def test_berat_dari_slug(url, gram):
    assert berat_dari_slug(url) == gram


def test_pilih_berat_variant_menang_atas_nama():
    # Blibli NAS-70965-00407: nama "1 Kg", variant "500 gr", harga = harga 500 gr
    assert pilih_berat([("variant", "500 gr"), ("nama", "Apel Fuji Super Fresh 1 Kg")]) == (500, "variant")


def test_pilih_berat_lanjut_ke_sumber_berikutnya():
    assert pilih_berat([("variant", None), ("nama", "Mangga 1 kg")]) == (1000, "nama")


def test_pilih_berat_tidak_ada_yang_terbaca():
    assert pilih_berat([("variant", "Standar"), ("nama", "Mangga Potong")]) == (None, None)


@pytest.mark.parametrize("nama,n", [
    ("Buah Naga Merah 1 Buah", 1),
    ("Apel 1 kg isi 6 pcs", 6),
    ("Pisang Cavendish 1 sisir", 1),
    ("Kelapa Muda 2 butir", 2),
    ("Telur Puyuh 10 btr", 10),
    ("Mangga isi 3-5 buah", None),                               # rentang: jumlah tidak pasti
    ("Mangga Manalagi Madu", None),
])
def test_jumlah_buah(nama, n):
    assert jumlah_buah(nama) == n


@pytest.mark.parametrize("nama,berat,jenis", [
    ("Mangga Manalagi 1 kg", 1000, "berat"),
    ("Buah Naga Merah 1 Buah", None, "jumlah"),
    ("Pisang Cavendish 1 sisir", None, "jumlah"),
    ("Kiwi Green 4s Impor 1 pack", None, "kemasan"),
    ("Jus Jeruk 250 ml", None, "kemasan"),
    ("Mangga Manalagi Madu", None, "lain"),
    ("Apel Fuji 1 Kg 1/2 Kg", None, "lain"),
])
def test_jenis_satuan(nama, berat, jenis):
    assert jenis_satuan(nama, berat) == jenis


@pytest.mark.parametrize("nama,hasil", [
    ("Mangga Manalagi 1 kg", True),
    ("MANGGA MANALAGI 170 - 180 G", True),
    ("Mangga madu manalagi segar", True),
    ("M4ngg4 M4n4l4gi 1kg", True),                     # angka pengganti huruf
    ("Manga Manalagi Super", True),                    # ejaan asli di data: manga, manggah, manggo, mango, mangg
    ("Manggah Manalagi", True),
    ("Mango Manalagi Fresh", True),
    ("ManggaMuda Manalagi", True),                     # tertempel ke kata berikutnya
    ("Mangga M4n4lgi", True),                          # angka + 1 huruf hilang
    ("Mangga Manalgi", True),                          # 1 huruf hilang
    ("Mangga Mnalagi Madu", True),
    ("Mangga Manakagi", True),                         # 1 huruf salah
    ("Mangka Manalagi", True),                         # 1 huruf salah di mangga
    ("Nangka Manalagi", False),                        # nangka = 2 huruf beda, buah lain
    ("Mangga Manalagian Sale", True),                  # tertempel ke kata berikutnya
    ("Mangga Malang", False),                          # Malang = kota
    ("Apel Manalagi 1 kg", False),                     # perangkap spec 5.2
    ("500Gr MANISAN BUAH SIMANALAGI ASLI KALIMANTAN", False),
    ("Semangka Manalagi", False),                      # semangka bukan mangga
    ("Manggis Manalagi", False),                       # manggis bukan mangga
    ("Mangga Harumanis 1 kg", False),
    ("", False),
    (None, False),
])
def test_mangga_manalagi(nama, hasil):
    assert mangga_manalagi(nama) is hasil


# A1 (8 Nov): produk dengan BEBERAPA opsi hanya membaca `variant` opsinya sendiri,
# tidak meminjam berat dari nama. Produk dengan SATU opsi: variant → nama → usp.
@pytest.mark.parametrize("nama,variant,banyak_opsi,usp,hasil", [
    ("Buah Mangga Manalagi segar", "1/2 kg", True, None, (500, "variant", "berat", None)),
    ("HarvestMoon Mangga Harum Manis Per Kg", "Buy 1 Get 1", True, None, (None, None, "lain", None)),
    ("ANGGUR MERAH IMPORT SEGAR MANIS - 500 GR", "PERU", True, None, (None, None, "lain", None)),
    ("Jeruk Murcot Impor", "3 pcs", True, None, (None, None, "jumlah", 3)),
    ("APEL ENVY PREMIUM 1 kg", "PAKET 4 PCS", True, None, (None, None, "jumlah", 4)),
    ("Buah strawberry per pack", "pack besar", True, None, (None, None, "kemasan", None)),
    ("Mangga Manalagi 900g - 1 Kg", "", False, None, (950, "nama", "berat", None)),
    ("Apel Fuji Super Fresh 1 Kg", "500 gr", False, None, (500, "variant", "berat", None)),
    ("Mangga Manalagi Madu", None, False, "Berat 1 kg", (1000, "usp", "berat", None)),
    ("Buah Naga Merah 1 Buah", None, False, None, (None, None, "jumlah", 1)),
    ("Apel 1 kg isi 6 pcs", None, False, None, (1000, "nama", "berat", None)),   # berat menang, jumlah tidak diisi
])
def test_satuan_baris(nama, variant, banyak_opsi, usp, hasil):
    assert tuple(satuan_baris(nama, variant, banyak_opsi, usp)) == hasil
