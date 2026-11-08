"""Fungsi murni untuk membaca nama produk. Aturan: spec bagian 5.2."""
import re
from typing import NamedTuple
from urllib.parse import urlparse

BERAT_MIN, BERAT_MAKS = 100, 20_000

_ANGKA = r"\d+(?:[.,]\d+)?"
_SATUAN = r"kg|kilogram|kilo|gram|grm|gr|g|ons"
_POLA_BERAT = re.compile(
    rf"(?<![\d.,/])"
    rf"(?:(?P<pembilang>\d+)\s*/\s*(?P<penyebut>\d+)"   # pecahan: 1/2
    rf"|(?P<bawah>{_ANGKA})\s*-\s*(?P<atas>{_ANGKA})"   # rentang: 170 - 180
    rf"|(?P<angka>{_ANGKA}))"                           # angka biasa
    rf"\s*(?P<satuan>{_SATUAN})\b",
    re.I,
)
_POLA_RENTANG_DUA_SATUAN = re.compile(   # "900g - 1 Kg": satuan di kedua ujung
    rf"(?<![\d.,/])(?P<bawah>{_ANGKA})\s*(?P<satuan_bawah>{_SATUAN})\s*-\s*"
    rf"(?P<atas>{_ANGKA})\s*(?P<satuan_atas>{_SATUAN})\b",
    re.I,
)
# Multipack (spec 13 #6, keputusan 8 Nov): dikalikan. "8x125GR", "550g x 12", "200 gr×12 Pcs"
_POLA_JUMLAH_KALI_BERAT = re.compile(
    rf"(?<![\d.,/])(?P<n>\d+)\s*[x×]\s*(?P<angka>{_ANGKA})\s*(?P<satuan>{_SATUAN})\b", re.I)
_POLA_BERAT_KALI_JUMLAH = re.compile(
    rf"(?<![\d.,/])(?P<angka>{_ANGKA})\s*(?P<satuan>{_SATUAN})\s*[x×]\s*(?P<n>\d+)"
    rf"(?![\d.,])(?!\s*(?:{_SATUAN})\b)", re.I)
_PER_KILO = re.compile(r"(?:/\s*|\bper\s+)kg\b|\bkiloan\b", re.I)
_KATA_BILANGAN = {
    re.compile(r"\bsekilo\b", re.I): 1000,
    re.compile(r"\bsetengah\s+kilo\b", re.I): 500,
}
_KALI_SATUAN = {"kg": 1000, "kilogram": 1000, "kilo": 1000, "ons": 100}

_POLA_JUMLAH = re.compile(r"(?<![\d.,/-])(\d+)\s*(?:pcs|pc|buah|sisir|butir|biji|btr)\b", re.I)
_POLA_KEMASAN = re.compile(r"\b(?:pack|pak|dus|box|paket)\b|\d\s*(?:ml|liter|ltr)\b", re.I)
_SLUG_ID = re.compile(r"(?:-\d{15,})+$")
_SLUG_AMBIGU = re.compile(rf"\b\d+ \d+ ?(?:{_SATUAN})\b", re.I)


def _angka(teks: str) -> float:
    """"1,5" → 1.5; "1.000" → 1000 (titik + tepat 3 angka = ribuan); "2.5" → 2.5."""
    if re.fullmatch(r"\d+\.\d{3}", teks):
        return float(teks.replace(".", ""))
    return float(teks.replace(",", "."))


def _semua_berat(teks: str) -> tuple[list[tuple[float, float]], bool]:
    """Setiap berat di teks sebagai (batas bawah, batas atas) dalam gram, dan
    apakah ada berat yang dikalikan (multipack). Berat tunggal punya bawah = atas."""
    hasil = []
    dikali = False

    def multipack(cocok: re.Match) -> str:
        nonlocal dikali
        n = int(cocok["n"])
        nilai = _angka(cocok["angka"]) * _KALI_SATUAN.get(cocok["satuan"].lower(), 1) * n
        hasil.append((nilai, nilai))
        dikali = dikali or n > 1
        return " "

    def rentang_dua_satuan(cocok: re.Match) -> str:
        bawah = _angka(cocok["bawah"]) * _KALI_SATUAN.get(cocok["satuan_bawah"].lower(), 1)
        atas = _angka(cocok["atas"]) * _KALI_SATUAN.get(cocok["satuan_atas"].lower(), 1)
        # hanya rentang yang masuk akal; "+-0.9g-1kg" tetap dibaca sebagai dua berat
        if not (BERAT_MIN <= bawah < atas <= BERAT_MAKS):
            return cocok[0]
        hasil.append((bawah, atas))
        return " "

    teks = _POLA_JUMLAH_KALI_BERAT.sub(multipack, teks)
    teks = _POLA_BERAT_KALI_JUMLAH.sub(multipack, teks)
    teks = _POLA_RENTANG_DUA_SATUAN.sub(rentang_dua_satuan, teks)
    for cocok in _POLA_BERAT.finditer(teks):
        kali = _KALI_SATUAN.get(cocok["satuan"].lower(), 1)
        if cocok["pembilang"]:
            penyebut = int(cocok["penyebut"])
            if penyebut == 0:
                continue
            nilai = int(cocok["pembilang"]) / penyebut * kali
            hasil.append((nilai, nilai))
        elif cocok["bawah"]:
            hasil.append((_angka(cocok["bawah"]) * kali, _angka(cocok["atas"]) * kali))
        else:
            nilai = _angka(cocok["angka"]) * kali
            hasil.append((nilai, nilai))
    for pola, gram in _KATA_BILANGAN.items():
        if pola.search(teks):
            hasil.append((gram, gram))
    if _PER_KILO.search(teks):
        hasil.append((1000, 1000))
    return hasil, dikali


def berat_gram(teks: str | None) -> int | None:
    """Berat dalam gram dari nama/variant/slug. `None` kalau tidak ada,
    kalau ada dua berat yang berbeda, atau di luar 100–20.000 g."""
    if not teks:
        return None
    berat, _ = _semua_berat(teks)
    if not berat:
        return None

    tunggal = {bawah for bawah, atas in berat if bawah == atas}
    rentang = [(bawah, atas) for bawah, atas in berat if bawah != atas]
    if len(tunggal) == 1:
        nilai = next(iter(tunggal))
        # rentang lain boleh ada asal berat tunggal itu jatuh di dalamnya
        if not all(bawah <= nilai <= atas for bawah, atas in rentang):
            return None
    elif not tunggal and len({(b + a) / 2 for b, a in rentang}) == 1:
        nilai = (rentang[0][0] + rentang[0][1]) / 2
    else:
        return None

    gram = round(nilai)
    return gram if BERAT_MIN <= gram <= BERAT_MAKS else None


def berat_dikali(teks: str | None) -> bool:
    """True kalau berat di teks didapat dengan mengalikan (multipack "8x125GR").
    Baris seperti ini dicatat di karantina untuk ditinjau (cek H)."""
    return bool(teks) and _semua_berat(teks)[1]


def berat_dari_slug(url: str | None) -> int | None:
    """Berat dari slug URL Tokopedia (bagian setelah nama toko).
    Slug ambigu seperti "1-2-kg" (1/2? 1.2? 1-2?) → `None`."""
    if not url:
        return None
    bagian = [b for b in urlparse(url).path.split("/") if b]
    if len(bagian) < 2:
        return None
    slug = _SLUG_ID.sub("", bagian[-1]).replace("-", " ")
    if _SLUG_AMBIGU.search(slug):
        return None
    return berat_gram(slug)


def pilih_berat(kandidat: list[tuple[str, str | None]]) -> tuple[int | None, str | None]:
    """`kandidat` = [(sumber_berat, teks), ...] urut prioritas.
    Hasil: (berat pertama yang terbaca, sumbernya) atau (None, None)."""
    for sumber, teks in kandidat:
        berat = berat_gram(teks)
        if berat is not None:
            return berat, sumber
    return None, None


def jumlah_buah(nama: str | None) -> int | None:
    """Angka tepat sebelum pcs/pc/buah/sisir/butir/biji/btr.
    Rentang ("3-5 buah") → `None`, karena jumlahnya tidak pasti."""
    if not nama:
        return None
    cocok = _POLA_JUMLAH.search(nama)
    return int(cocok[1]) if cocok else None


def jenis_satuan(nama: str | None, berat: int | None) -> str:
    """`berat` / `jumlah` / `kemasan` / `lain` (spec 5.2)."""
    if berat is not None:
        return "berat"
    if jumlah_buah(nama) is not None:
        return "jumlah"
    if nama and _POLA_KEMASAN.search(nama):
        return "kemasan"
    return "lain"


class Satuan(NamedTuple):
    berat_gram: int | None
    sumber_berat: str | None
    jenis_satuan: str
    jumlah_buah: int | None   # diisi hanya kalau jenis_satuan = "jumlah"
    berat_dikali: bool = False  # multipack; dicatat di karantina (cek H)


def satuan_baris(
    nama: str | None,
    variant: str | None,
    banyak_opsi: bool,
    usp: str | None = None,
) -> Satuan:
    """Berat, sumbernya, jenis satuan, dan jumlah untuk satu baris (satu opsi).

    Produk dengan **beberapa opsi** (keputusan A1, 8 Nov): hanya `variant` opsi itu
    yang dibaca. Nama menggambarkan seluruh produk, bukan tiap opsi, jadi beratnya
    tidak dipinjam ("Buy 1 Get 1" pada "… Per Kg" bukan 1 kg).
    Produk dengan **satu opsi**: `variant` → nama → `usp` (spec 5.2).
    """
    if banyak_opsi:
        teks = variant
        kandidat = [("variant", variant)]
    else:
        teks = nama
        kandidat = [("variant", variant), ("nama", nama), ("usp", usp)]
    berat, sumber = pilih_berat(kandidat)
    jenis = jenis_satuan(teks, berat)
    teks_berat = dict(kandidat).get(sumber, teks)   # teks yang menghasilkan berat
    return Satuan(berat, sumber, jenis,
                  jumlah_buah(teks) if jenis == "jumlah" else None,
                  berat_dikali(teks_berat))


# Salah ketik: satu kata boleh beda **1 huruf** (salah/hilang/lebih) dari kata
# aslinya. Diuji pada 9.871 nama (8 Nov):
# - 1 huruf dari "mangga" = tepat salah ketik asli: manga, manggah, manggo, mangg.
#   2 huruf sudah buah lain: nangka, manggis, bangka. Jadi batasnya 1.
# - 1 huruf dari "manalagi" = 0 kata; 2 huruf = "simanalagi" (manisan belimbing).
# "mango" (Inggris) beda 2 huruf, jadi ditulis sendiri.
_MANGGA_LAIN = {"mango"}
_ANGKA_JADI_HURUF = str.maketrans("4013", "aoie")   # "m4ngg4" → "mangga"


def _jarak_edit(a: str, b: str) -> int:
    """Jumlah huruf yang harus diganti/dihapus/ditambah supaya `a` jadi `b` (Levenshtein)."""
    sebelum = list(range(len(b) + 1))
    for i, huruf_a in enumerate(a, 1):
        kini = [i]
        for j, huruf_b in enumerate(b, 1):
            kini.append(min(sebelum[j] + 1, kini[j - 1] + 1, sebelum[j - 1] + (huruf_a != huruf_b)))
        sebelum = kini
    return sebelum[-1]


def _mirip(kata: str, asli: str) -> bool:
    """Sama, beda 1 huruf, atau tertempel ke kata berikutnya ("manggamuda")."""
    if kata.startswith(asli):
        return True
    return abs(len(kata) - len(asli)) <= 1 and _jarak_edit(kata, asli) <= 1


def _ganti_angka_dalam_kata(teks: str) -> str:
    """Angka di dalam kata yang juga berisi huruf diganti huruf. "1 kg" tetap."""
    return re.sub(
        r"[a-z0-9]+",
        lambda m: m[0].translate(_ANGKA_JADI_HURUF) if re.search(r"[a-z]", m[0]) else m[0],
        teks,
    )


def mangga_manalagi(nama: str | None) -> bool:
    """Nama memuat mangga **dan** manalagi (spec 5.2), boleh salah ketik 1 huruf
    dan angka pengganti huruf ("M4ngg4 M4n4lgi")."""
    if not nama:
        return False
    kata = _kata(nama)
    return _ada_mangga(kata) and any(_mirip(k, "manalagi") for k in kata)


def _kata(nama: str) -> list[str]:
    return re.findall(r"[a-z]+", _ganti_angka_dalam_kata(nama.lower()))


def _ada_mangga(kata: list[str]) -> bool:
    return any(k in _MANGGA_LAIN or _mirip(k, "mangga") for k in kata)



# ---- Task 1B ----

# Urut: yang pertama cocok menang. Kata kunci dicocokkan di AWAL kata (\b),
# jadi "kelengkeng" perlu ditulis sendiri dan "semangka" tidak cocok dengan "mangka".
_JENIS_BUAH = [
    ("apel", r"apel|apple"),
    ("pisang", r"pisang"),
    ("jeruk", r"jeruk"),
    ("anggur", r"anggur"),
    ("melon", r"melon\b"),
    ("semangka", r"semangka"),
    ("alpukat", r"alpukat|avocad"),
    ("pepaya", r"pepaya"),
    ("buah naga", r"buah naga|dragon"),
    ("pir", r"pir\b|pear\b"),
    ("kiwi", r"kiwi"),
    ("salak", r"salak"),
    ("manggis", r"manggis"),
    ("durian", r"durian"),
    ("lengkeng", r"lengkeng|kelengkeng"),
    ("nanas", r"nanas"),
    ("stroberi", r"stroberi|strawberry"),
    ("jambu", r"jambu"),
]
_POLA_JENIS = [(jenis, re.compile(rf"\b(?:{pola})", re.I)) for jenis, pola in _JENIS_BUAH]

# Dari kebun-ibu/skrip/bersihkan_blibli.py, tanpa "sale" dan "pohon" (keputusan
# pengguna 8 Nov): "flash sale" = promo, "tua pohon" = matang di pohon (buah segar).
POLA_OLAHAN = re.compile(
    r"\b(keripik|kripik|selai|jus|juice|sirup|manisan|kering|dried|"
    r"puree|bubuk|powder|bibit|benih|tanaman|okulasi|jantung|daun|kulit)\b",
    re.I,
)

_VARIETAS_IMPOR = r"kiwi|fuji|red globe|sunkist|pear|pir|washington|envy|ponkam|shine muscat|crimson"
_VARIETAS_LOKAL = r"salak|manggis|arumanis|harumanis|manalagi|medan|pontianak|kepok|ambon|rambutan|duku"
_ATURAN_ASAL = [
    ("impor", re.compile(r"\b(?:impor|import)\b", re.I)),
    ("lokal", re.compile(r"\blokal\b", re.I)),
    ("impor", re.compile(rf"\b(?:{_VARIETAS_IMPOR})\b", re.I)),
    ("lokal", re.compile(rf"\b(?:{_VARIETAS_LOKAL})\b", re.I)),
]

_POLA_TERJUAL = re.compile(r"(\d+(?:,\d+)?)\s*(rb)?\+?\s*terjual", re.I)

JABODETABEK = {
    "jakarta pusat", "jakarta barat", "jakarta timur", "jakarta selatan", "jakarta utara",
    "kepulauan seribu", "bogor", "depok", "tangerang", "tangerang selatan", "bekasi",
}
# Kota/kabupaten di Banten, Jawa Barat, Jawa Tengah, DIY, Jawa Timur (termasuk Madura),
# di luar Jabodetabek. Mencakup semua nama Jawa yang muncul di data sampai 8 Nov.
JAWA_LAIN = {
    # Banten
    "serang", "cilegon", "lebak", "pandeglang",
    # Jawa Barat
    "bandung", "bandung barat", "cimahi", "sukabumi", "cianjur", "garut", "tasikmalaya",
    "ciamis", "pangandaran", "banjar", "kuningan", "cirebon", "majalengka", "sumedang",
    "indramayu", "subang", "purwakarta", "karawang",
    # Jawa Tengah
    "semarang", "salatiga", "kendal", "demak", "grobogan", "kudus", "jepara", "pati",
    "rembang", "blora", "surakarta", "solo", "sukoharjo", "karanganyar", "sragen",
    "boyolali", "klaten", "wonogiri", "magelang", "temanggung", "wonosobo", "purworejo",
    "kebumen", "banjarnegara", "purbalingga", "banyumas", "cilacap", "tegal", "brebes",
    "pemalang", "pekalongan", "batang",
    # DIY
    "yogyakarta", "sleman", "bantul", "kulon progo", "gunungkidul", "gunung kidul",
    # Jawa Timur
    "surabaya", "sidoarjo", "gresik", "lamongan", "tuban", "bojonegoro", "ngawi", "madiun",
    "magetan", "ponorogo", "pacitan", "trenggalek", "tulungagung", "blitar", "kediri",
    "nganjuk", "jombang", "mojokerto", "pasuruan", "probolinggo", "malang", "batu",
    "lumajang", "jember", "bondowoso", "situbondo", "banyuwangi",
    "bangkalan", "sampang", "pamekasan", "sumenep",
}
_AWALAN_KOTA = re.compile(r"^(?:kota\s+|kabupaten\s+|kab\.\s*)", re.I)


def jenis_buah(nama: str | None) -> str:
    """Jenis buah dari kata kunci; mangga ikut aturan salah ketik `mangga_manalagi`."""
    if not nama:
        return "lainnya"
    if _ada_mangga(_kata(nama)):
        return "mangga"
    for jenis, pola in _POLA_JENIS:
        if pola.search(nama):
            return jenis
    return "lainnya"


def olahan(nama: str | None) -> bool:
    """Produk olahan / bukan buah utuh (bibit, keripik, jus, …). Hanya penanda."""
    return bool(nama and POLA_OLAHAN.search(nama))


def asal_dari_nama(nama: str | None) -> str:
    """`impor` / `lokal` / `tidak_diketahui` dari kata di nama (dipakai untuk Tokopedia)."""
    for asal, pola in _ATURAN_ASAL:
        if nama and pola.search(nama):
            return asal
    return "tidak_diketahui"


def terjual_dari_label(label: str | None) -> int | None:
    """"23 terjual" → 23, "100+ terjual" → 100, "1,5rb+ terjual" → 1500."""
    cocok = _POLA_TERJUAL.search(label or "")
    if not cocok:
        return None
    angka = float(cocok[1].replace(",", "."))
    return round(angka * 1000) if cocok[2] else round(angka)


def ember_terjual(n: int | None) -> int | None:
    """Angka terjual pasti → batas bawah seperti label Tokopedia, supaya dua sumber setara."""
    if n is None:
        return None
    if n < 30:
        return n
    if n < 100:
        return n // 10 * 10
    if n < 1000:
        return max(b for b in (100, 250, 500, 750) if b <= n)
    return n // 1000 * 1000


def region(kota: str | None) -> str:
    """`jabodetabek` / `jawa_lain` / `luar_jawa` / `tidak_diketahui`."""
    if not kota or not kota.strip():
        return "tidak_diketahui"
    bersih = _AWALAN_KOTA.sub("", kota.strip())
    bersih = re.sub(r"\s*\(.*?\)", "", bersih).strip().lower()   # "Surakarta (Solo)"
    if bersih in JABODETABEK:
        return "jabodetabek"
    if bersih in JAWA_LAIN:
        return "jawa_lain"
    return "luar_jawa"
