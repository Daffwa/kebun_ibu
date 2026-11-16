import pytest

from transform.parser import (
    asal_dari_nama,
    ember_terjual,
    jenis_buah,
    olahan,
    region,
    terjual_dari_label,
    berat_dari_slug,
    berat_dikali,
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
    assert tuple(satuan_baris(nama, variant, banyak_opsi, usp))[:4] == hasil


# ---- Task 1B ----

@pytest.mark.parametrize("nama,jenis", [
    ("MANGGA HARUMANIS 470 - 500 G", "mangga"),
    ("Manga Harum Manis 1 kg", "mangga"),                # salah ketik, sama dengan mangga_manalagi
    ("DRAGON FRUIT RED LOKAL", "buah naga"),
    ("Buah Naga Merah", "buah naga"),
    ("Avocadron Alpukat Mentega", "alpukat"),
    ("PEAR MADU PREMIUM", "pir"),
    ("Apel Fuji", "apel"),
    ("Apel Manalagi 1 kg", "apel"),                      # perangkap spec 5.2
    ("Semangka Merah 1 buah", "semangka"),
    ("Buah Manggis Manis Segar 500gr", "manggis"),       # bukan mangga
    ("Kelengkeng Bangkok", "lengkeng"),
    ("Pisang Nangka", "pisang"),
    ("Kurma Ajwa", "lainnya"),
    ("Buah Nangka Manis", "lainnya"),
])
def test_jenis_buah(nama, jenis):
    assert jenis_buah(nama) == jenis


def test_olahan():
    assert olahan("Keripik Pisang 250g")
    assert olahan("Bibit Mangga Irwin")
    assert not olahan("Pisang Cavendish 1 kg")


def test_olahan_tidak_memakai_sale_dan_pohon():
    # keputusan pengguna 8 Nov: "flash sale" = promo, "tua pohon" = matang di pohon
    assert not olahan("MANGGA MANALAGI MANIS, (1KG) flash sale Buah")
    assert not olahan("Mangga Manalagi Madu (Arum ) Tua Pohon asli Situbondo")


@pytest.mark.parametrize("nama,asal", [
    ("Kiwi Green 4s Impor", "impor"),
    ("Anggur Red Globe Premium Import", "impor"),
    ("Apel Fuji 1 kg", "impor"),
    ("Jeruk Sunkist", "impor"),
    ("Salak Pondoh 1 kg", "lokal"),
    ("Manggis Super", "lokal"),
    ("Mangga Arumanis", "lokal"),
    ("Mangga Manalagi 1 kg", "lokal"),
    ("Jeruk Medan Lokal", "lokal"),
    ("Pisang Cavendish", "tidak_diketahui"),
])
def test_asal_dari_nama(nama, asal):
    assert asal_dari_nama(nama) == asal


@pytest.mark.parametrize("label,n", [
    ("23 terjual", 23), ("100+ terjual", 100), ("1rb+ terjual", 1000),
    ("1,5rb+ terjual", 1500), ("10rb+ terjual", 10000),
    ("", None), (None, None), ("Hemat s.d 8%", None),
])
def test_terjual_dari_label(label, n):
    assert terjual_dari_label(label) == n


@pytest.mark.parametrize("n,ember", [
    (0, 0), (23, 23), (29, 29), (30, 30), (47, 40), (99, 90), (100, 100),
    (249, 100), (250, 250), (600, 500), (800, 750), (1499, 1000),
    (6874, 6000), (None, None),
])
def test_ember_terjual(n, ember):
    assert ember_terjual(n) == ember


@pytest.mark.parametrize("kota,hasil", [
    ("Jakarta Barat", "jabodetabek"), ("Kota Jakarta Barat", "jabodetabek"),
    ("Kab. Bogor", "jabodetabek"), ("Bekasi", "jabodetabek"), ("Kota Tangerang Selatan", "jabodetabek"),
    ("Kota Surabaya", "jawa_lain"), ("Kab. Sleman", "jawa_lain"),
    ("Kab.Ciamis", "jawa_lain"),                          # tanpa spasi (data asli)
    ("Surakarta (Solo)", "jawa_lain"),                    # data asli
    ("Kab. Bandung Barat", "jawa_lain"),
    ("Kota Denpasar", "luar_jawa"), ("Bandar Lampung", "luar_jawa"),
    ("Kab. Kotawaringin Barat", "luar_jawa"),             # "Kota…" bukan awalan
    (None, "tidak_diketahui"), ("", "tidak_diketahui"),
])
def test_region(kota, hasil):
    assert region(kota) == hasil


# Multipack (keputusan pengguna 8 Nov, spec 13 #6): dikalikan, dan ditandai supaya
# barisnya dicatat di karantina untuk ditinjau.
@pytest.mark.parametrize("nama,gram,dikali", [
    ("BLUEBERRY TRAIN TOY 8x125GR PACK", 1000, True),          # data asli
    ("Kurma Akram Bam Mazafati 550g x 12 (1 dus)", 6600, True),  # data asli
    ("Strawberry 200 gr×12 Pcs", 2400, True),
    ("Apel 1 kg x 2", 2000, True),
    ("Jeruk 1 x 500gr", 500, False),                           # dikali 1 = tidak berubah
    ("Mangga Manalagi 1 kg", 1000, False),
    ("Anggur 3 x 10 kg", None, True),                          # 30 kg: di luar batas
])
def test_multipack(nama, gram, dikali):
    assert berat_gram(nama) == gram
    assert berat_dikali(nama) is dikali


def test_satuan_baris_menandai_berat_dikali():
    assert satuan_baris("BLUEBERRY TRAIN TOY 8x125GR PACK", None, False).berat_dikali is True
    assert satuan_baris("Mangga Manalagi 1 kg", None, False).berat_dikali is False
    assert satuan_baris("Kurma", "2 x 500 gr", True).berat_dikali is True
