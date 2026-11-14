"""Kode wilayah resmi (Kepmendagri 2025) untuk nama kota dari marketplace.

Daftar: `referensi/wilayah_kabkota.csv` (514 kab/kota, 38 provinsi).
Desain: docs/superpowers/specs/2026-11-14-filter-wilayah-design.md.

Nama dari marketplace dicocokkan setelah dinormalisasi (`kunci_nama`). Awalan menentukan jenis:
Blibli menulis "Kota X"/"Kab. X"; Tokopedia menulis "Kab. X" untuk kabupaten dan nama polos untuk
kota (14 Nov: 64 nama berawalan "Kab.", nama polos tidak pernah hanya cocok ke kabupaten), jadi nama
polos yang cocok ke kota dan kabupaten sekaligus dibaca sebagai kota. Kalau calonnya ada di lebih
dari satu provinsi (hanya "Banjar"), hasilnya kosong: lebih baik kosong daripada salah provinsi.
"""
import re
from functools import cache
from pathlib import Path

import polars as pl

CSV = Path(__file__).resolve().parent.parent / "referensi" / "wilayah_kabkota.csv"

# kunci_nama(nama di marketplace) -> kode kab/kota, untuk nama yang tertahan cek I
ALIAS_KOTA: dict[str, str] = {}

KELOMPOK: dict[str, tuple[str, frozenset[str]]] = {
    "jabodetabek": ("Jabodetabek", frozenset({
        "31.01", "31.71", "31.72", "31.73", "31.74", "31.75",    # DKI Jakarta
        "32.01", "32.71", "32.76", "32.16", "32.75",             # Bogor, Depok, Bekasi
        "36.03", "36.71", "36.74",                               # Tangerang, Tangerang Selatan
    })),
}

# Kata tambahan untuk kotak cari provinsi (dipisah spasi, huruf kecil)
KATA_KUNCI_PROVINSI: dict[str, str] = {
    "31": "dki jakarta", "32": "jabar", "33": "jateng", "34": "diy jogja yogya",
    "35": "jatim", "36": "banten", "51": "bali", "12": "sumut", "13": "sumbar", "16": "sumsel",
    "61": "kalbar", "62": "kalteng", "63": "kalsel", "64": "kaltim", "65": "kaltara",
    "71": "sulut", "72": "sulteng", "73": "sulsel", "74": "sultra", "76": "sulbar",
    "52": "ntb", "53": "ntt", "19": "babel", "21": "kepri",
}

_AWALAN = re.compile(r"^(kabupaten administrasi|kota administrasi|kabupaten|kab\.|kota)\s*")


def kunci_nama(nama: str) -> str:
    """Huruf kecil, tanpa isi kurung, tanpa awalan kota/kabupaten, tanpa spasi."""
    n = re.sub(r"\s*\(.*?\)", "", nama.strip().lower())
    return re.sub(r"\s+", "", _AWALAN.sub("", n))


def _jenis_masukan(nama: str) -> str | None:
    n = nama.strip().lower()
    if n.startswith("kota"):
        return "kota"
    if n.startswith(("kab.", "kabupaten")):
        return "kabupaten"
    return None


@cache
def kabkota() -> pl.DataFrame:
    """kode, nama, jenis, provinsi_kode, provinsi (514 baris)."""
    return pl.read_csv(CSV, comment_prefix="#", schema_overrides={
        "kode": pl.Utf8, "provinsi_kode": pl.Utf8})


@cache
def _indeks() -> dict[str, list[tuple[str, str]]]:
    hasil: dict[str, list[tuple[str, str]]] = {}
    for kode, nama, jenis in kabkota().select("kode", "nama", "jenis").iter_rows():
        hasil.setdefault(kunci_nama(nama), []).append((kode, jenis))
    return hasil


def cocokkan(kota: str | None) -> tuple[str | None, str | None]:
    """(kabkota_kode, provinsi_kode); (None, None) kalau kosong, tidak dikenal, atau ambigu."""
    if not kota or not kota.strip():
        return None, None
    kunci = kunci_nama(kota)
    if kunci in ALIAS_KOTA:
        kode = ALIAS_KOTA[kunci]
        return kode, kode[:2]
    calon = _indeks().get(kunci, [])
    jenis = _jenis_masukan(kota)
    if jenis is None and len({kode[:2] for kode, _ in calon}) > 1:
        return None, None              # nama polos di dua provinsi: jangan menebak
    pilihan = [kode for kode, j in calon if j == (jenis or "kota")] or [kode for kode, _ in calon]
    if len(pilihan) != 1:
        return None, None
    return pilihan[0], pilihan[0][:2]


@cache
def anggota() -> pl.DataFrame:
    """kabkota_kode, wilayah: setiap kab/kota masuk wilayahnya sendiri, provinsinya, dan kelompoknya."""
    baris = []
    for kode in kabkota()["kode"]:
        baris += [(kode, kode), (kode, kode[:2])]
        baris += [(kode, nama) for nama, (_, isi) in KELOMPOK.items() if kode in isi]
    return pl.DataFrame(baris, schema={"kabkota_kode": pl.Utf8, "wilayah": pl.Utf8}, orient="row")
