"""Data mentah Tokopedia satu tanggal → tabel lapisan 1 `tokopedia_produk` (spec 5.1).

Satu baris per opsi (`produk_id`), sama seperti Blibli (spec 5.0):
- baris kartu (`opsi_default = True`) dari hasil cari `page_*.json`;
- baris opsi lain (`opsi_default = False`) dari halaman produk `halaman/<id>.json`
  (hanya Mangga Manalagi, keputusan 13 #11 = a).

Berat (spec 5.2): opsi → halaman (hanya kalau nama tanpa berat) → nama → URL.
"""
import json
from datetime import date
from pathlib import Path

import polars as pl

from extract.tokopedia import produk_dari_jawaban
from transform.blibli import angka_rupiah
from transform.parser import Satuan, berat_dari_slug, satuan_baris

KOLOM_TOKOPEDIA: dict[str, pl.DataType] = {
    "tanggal": pl.Date,
    "produk_id": pl.Utf8,
    "induk_id": pl.Utf8,
    "opsi_default": pl.Boolean,
    "nama": pl.Utf8,
    "variant": pl.Utf8,
    "harga": pl.Int64,
    "harga_asli": pl.Int64,      # disimpan, tidak dipakai di fakta (13 #1)
    "diskon_persen": pl.Int64,   # selalu NULL (13 #2)
    "toko_id": pl.Utf8,
    "nama_toko": pl.Utf8,
    "kota": pl.Utf8,
    "tier_toko": pl.Int64,
    "rating": pl.Float64,
    "terjual_label": pl.Utf8,
    "kategori": pl.Utf8,
    "url": pl.Utf8,
    # turunan (spec 5.1 "Kolom turunan")
    "berat_gram": pl.Int64,
    "sumber_berat": pl.Utf8,
    "jenis_satuan": pl.Utf8,
    "jumlah_buah": pl.Int64,
    "berat_dikali": pl.Boolean,
}

# kolom yang disalin dari baris kartu ke baris opsi lain
_SALIN = ("nama", "toko_id", "nama_toko", "kota", "tier_toko", "rating", "terjual_label", "kategori")

_GRAM_PER_SATUAN = {"KILOGRAM": 1000, "GRAM": 1}


class HalamanProduk:
    """Bagian `window.__cache` halaman produk yang dipakai transform."""

    def __init__(self, cache: dict):
        def semua(tipe):
            return [v for v in cache.values() if isinstance(v, dict) and v.get("__typename") == tipe]

        info = (semua("pdpBasicInfo") or [{}])[0]
        varian = (semua("pdpContentSnapshotVariant") or [{}])[0]
        satuan = _GRAM_PER_SATUAN.get(info.get("weightUnit"))
        berat = info.get("weight")
        self.berat_gram = round(berat * satuan) if berat and satuan else None
        self.induk_id = varian.get("parentID") if varian.get("isVariant") else None
        self.opsi: dict[str, dict] = {}
        if self.induk_id:
            for anak in semua("pdpProductVariantChildren"):
                self.opsi.setdefault(str(anak["productID"]), anak)


def _nama_opsi(anak: dict) -> str | None:
    nama = anak.get("optionName") or []
    if isinstance(nama, dict):            # cache Apollo: {"type": "json", "json": [...]}
        nama = nama.get("json") or []
    return ", ".join(nama) or None


def _url(url: str | None) -> str | None:
    return url.split("?")[0] if url else None


def _satuan(nama: str, url: str | None, variant: str | None, berat_halaman: int | None) -> Satuan:
    """Berat satu baris, urutan spec 5.2: opsi → halaman (bersyarat) → nama → URL."""
    if variant is not None:
        # produk bervarian: hanya teks opsi (keputusan A1, sama dengan Blibli)
        s = satuan_baris(nama, variant, banyak_opsi=True)
        if s.berat_gram is None and berat_halaman:
            return Satuan(berat_halaman, "halaman", "berat", None)
        return s._replace(sumber_berat="opsi") if s.berat_gram is not None else s
    s = satuan_baris(nama, None, banyak_opsi=False)
    if s.berat_gram is not None:
        return s
    if berat_halaman:
        return Satuan(berat_halaman, "halaman", "berat", None)
    berat_url = berat_dari_slug(url)
    if berat_url is not None:
        return Satuan(berat_url, "url", "berat", None)
    return s


def _wajib(p: dict, berkas: Path) -> None:
    for kunci in ("id", "name", "price", "shop"):
        if p.get(kunci) is None:
            raise ValueError(f"kolom wajib '{kunci}' tidak ada di {berkas.name} (produk {p.get('id')})")


def _baris_kartu(p: dict, halaman: HalamanProduk | None, tanggal: date, berkas: Path) -> dict:
    _wajib(p, berkas)
    produk_id = str(p["id"])
    toko = p["shop"]
    label = {g.get("position"): g.get("title") for g in p.get("labelGroups") or []}
    anak = halaman.opsi.get(produk_id) if halaman else None
    variant = _nama_opsi(anak) if anak else None
    url = _url(p.get("url"))
    return {
        "tanggal": tanggal,
        "produk_id": produk_id,
        "induk_id": halaman.induk_id if halaman else None,
        "opsi_default": True,
        "nama": p["name"],
        "variant": variant,
        "harga": p["price"].get("number"),
        "harga_asli": angka_rupiah(p["price"].get("original")),
        "diskon_persen": None,
        "toko_id": str(toko["id"]) if toko.get("id") is not None else None,
        "nama_toko": toko.get("name"),
        "kota": toko.get("city") or None,
        "tier_toko": toko.get("tier"),
        "rating": float(p["rating"]) if p.get("rating") else None,
        "terjual_label": label.get("ri_product_credibility"),
        "kategori": (p.get("category") or {}).get("breadcrumb"),
        "url": url,
        **_satuan(p["name"], url, variant, halaman.berat_gram if halaman else None)._asdict(),
    }


def _baris_opsi(anak: dict, kartu: dict) -> dict:
    variant = _nama_opsi(anak)
    baris = {kolom: kartu[kolom] for kolom in _SALIN}
    baris.update({
        "tanggal": kartu["tanggal"],
        "produk_id": str(anak["productID"]),
        "induk_id": kartu["induk_id"],
        "opsi_default": False,
        "variant": variant,
        "harga": anak.get("price"),
        "harga_asli": angka_rupiah(anak.get("slashPriceFmt")),
        "diskon_persen": None,
        "url": _url(anak.get("productURL")),
        # berat halaman hanya milik opsi kartu, jadi tidak dipinjam di sini
        **_satuan(kartu["nama"], None, variant, None)._asdict(),
    })
    return baris


def _baca_halaman(folder: Path, produk_id: str) -> HalamanProduk | None:
    jalur = folder / "halaman" / f"{produk_id}.json"
    if not jalur.exists():
        return None
    return HalamanProduk(json.loads(jalur.read_text(encoding="utf-8")))


def ubah(folder: Path, tanggal: date) -> pl.DataFrame:
    """Semua berkas mentah Tokopedia satu tanggal → DataFrame `tokopedia_produk`."""
    folder = Path(folder)
    kartu, opsi = [], []
    for berkas in sorted(folder.glob("page_*.json")):
        for p in produk_dari_jawaban(json.loads(berkas.read_text(encoding="utf-8"))):
            halaman = _baca_halaman(folder, str(p.get("id")))
            baris = _baris_kartu(p, halaman, tanggal, berkas)
            kartu.append(baris)
            if halaman:
                opsi += [_baris_opsi(anak, baris) for id_, anak in halaman.opsi.items()
                         if id_ != baris["produk_id"]]
    return (
        pl.DataFrame(kartu + opsi, schema=KOLOM_TOKOPEDIA)
        .unique("produk_id", keep="first", maintain_order=True)
    )
