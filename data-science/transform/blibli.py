"""Data mentah Blibli satu tanggal → tabel lapisan 1 `blibli_produk` (spec 5.1).

Satu baris per opsi (`item_sku`):
- baris default (`opsi_default = True`) dari kartu hasil cari `*_page_*.json`;
- baris opsi lain (`opsi_default = False`) dari `varian/is--<itemSku>.json`.
"""
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import polars as pl

from transform.parser import satuan_baris

BLIBLI = "https://www.blibli.com"

KOLOM_BLIBLI: dict[str, pl.DataType] = {
    "tanggal": pl.Date,
    "produk_id": pl.Utf8,
    "item_sku": pl.Utf8,
    "opsi_default": pl.Boolean,
    "nama": pl.Utf8,
    "variant": pl.Utf8,
    "harga": pl.Int64,
    "harga_coret": pl.Int64,
    "diskon_persen": pl.Int64,
    "harga_voucher": pl.Int64,
    "harga_coret_voucher": pl.Int64,
    "diskon_voucher_persen": pl.Int64,
    "kampanye": pl.Utf8,
    "harga_sebelum_kampanye": pl.Int64,
    "merchant_code": pl.Utf8,
    "penjual": pl.Utf8,
    "resmi": pl.Boolean,
    "lokasi": pl.Utf8,
    "lencana_toko": pl.Utf8,
    "rating_toko": pl.Float64,
    "merek": pl.Utf8,
    "kategori": pl.Utf8,
    "kategori_tarik": pl.Utf8,
    "rating": pl.Float64,
    "jumlah_ulasan": pl.Int64,
    "total_terjual": pl.Int64,
    "terjual_bulan_ini_min": pl.Int64,
    "url": pl.Utf8,
    "sku": pl.Utf8,
    # turunan (spec 5.1 "Kolom turunan")
    "berat_gram": pl.Int64,
    "sumber_berat": pl.Utf8,
    "jenis_satuan": pl.Utf8,
    "jumlah_buah": pl.Int64,
    "berat_dikali": pl.Boolean,
}

# kolom yang disalin dari baris default ke baris opsi lain
_SALIN = ("nama", "merchant_code", "penjual", "resmi", "lokasi", "lencana_toko", "rating_toko",
          "merek", "kategori", "kategori_tarik", "rating", "jumlah_ulasan", "total_terjual")


def angka_rupiah(teks: str | None) -> int | None:
    """"Rp39.100" → 39100; None/"" → None."""
    angka = re.sub(r"\D", "", teks or "")
    return int(angka) if angka else None


def _bulat(nilai) -> int | None:
    return None if nilai is None else int(round(float(nilai)))


def _terjual_bulan_ini(label: str | None) -> int | None:
    """"Dibeli 100+ kali bulan ini" → 100; "Dibeli 1rb+ kali" → 1000."""
    cocok = re.search(r"(\d+(?:[.,]\d+)?)\s*(rb)?\s*\+", label or "")
    if not cocok:
        return None
    angka = float(cocok[1].replace(",", "."))
    return round(angka * 1000) if cocok[2] else round(angka)


def _url(url_relatif: str | None, item_sku: str) -> str | None:
    """Halaman produk tanpa parameter pelacak (sid, metaData), dengan ?ds=<item_sku>."""
    if not url_relatif:
        return None
    return f"{BLIBLI}{urlparse(url_relatif).path}?ds={item_sku}"


def _wajib(objek: dict, kunci: str, berkas: Path):
    if objek.get(kunci) is None:
        raise ValueError(f"kolom wajib '{kunci}' tidak ada di {berkas.name}")
    return objek[kunci]


def _baris_default(p: dict, kategori_tarik: str, tanggal: date, berkas: Path) -> dict:
    for kunci in ("id", "name", "price", "itemSku"):
        _wajib(p, kunci, berkas)
    harga = p["price"]
    voucher = p.get("contextualPrice") or {}
    ulasan = p.get("review") or {}
    jumlah_ulasan = ulasan.get("count")
    satuan = satuan_baris(p["name"], p.get("variant"), bool(p.get("hasVariants")),
                          p.get("uniqueSellingPoint"))
    return {
        "tanggal": tanggal,
        "produk_id": p["id"],
        "item_sku": p["itemSku"],
        "opsi_default": True,
        "nama": p["name"],
        "variant": p.get("variant"),
        "harga": _bulat(harga.get("salePrice")),
        "harga_coret": _bulat(harga.get("listPrice")),
        "diskon_persen": _bulat(harga.get("discount")),
        "harga_voucher": angka_rupiah(voucher.get("priceDisplay")),
        "harga_coret_voucher": angka_rupiah(voucher.get("strikeThroughPriceDisplay")),
        "diskon_voucher_persen": _bulat(voucher.get("discount")),
        "kampanye": (p.get("campaignInfo") or {}).get("name"),
        "harga_sebelum_kampanye": angka_rupiah(harga.get("offerPriceDisplay")),
        "merchant_code": p.get("merchantCode"),
        "penjual": p.get("merchantName"),
        "resmi": p.get("official"),
        "lokasi": p.get("location"),
        "lencana_toko": (p.get("badge") or {}).get("merchantBadge"),
        "rating_toko": ulasan.get("sellerRating"),
        "merek": p.get("brand"),
        "kategori": " > ".join(p.get("categoryNameHierarchy") or []) or None,
        "kategori_tarik": kategori_tarik,
        "rating": ulasan.get("absoluteRating") if jumlah_ulasan else None,
        "jumlah_ulasan": jumlah_ulasan,
        "total_terjual": p.get("soldCountTotal"),
        "terjual_bulan_ini_min": _terjual_bulan_ini(p.get("monthlySoldCountLabel")),
        "url": _url(p.get("url"), p["itemSku"]),
        "sku": p.get("sku"),
        **satuan._asdict(),
    }


def _baris_opsi(berkas: Path, default: dict, tanggal: date) -> dict:
    data = json.loads(berkas.read_text(encoding="utf-8")).get("data") or {}
    item_sku = _wajib(data, "itemSku", berkas)
    # price null = opsi yang Blibli tandai tidak tersedia (keputusan B, 8 Nov):
    # baris tetap dibuat dengan harga NULL, lalu dikarantina di Task 6.
    harga = data.get("price") or {}
    terpilih = next((o for o in data.get("options") or [] if o.get("selected")), {})
    variant = ((terpilih.get("attributes") or [{}])[0]).get("value")
    satuan = satuan_baris(default["nama"], variant, banyak_opsi=True)
    baris = {kolom: None for kolom in KOLOM_BLIBLI}
    baris.update({kolom: default[kolom] for kolom in _SALIN})
    baris.update({
        "tanggal": tanggal,
        "produk_id": data.get("productSku") or default["produk_id"],
        "item_sku": item_sku,
        "opsi_default": False,
        "variant": variant,
        "harga": _bulat(harga.get("offered")),
        "harga_coret": _bulat(harga.get("listed")),
        "diskon_persen": _bulat(harga.get("listDiscount")),
        "url": _url(urlparse(default["url"]).path if default["url"] else None, item_sku),
        **satuan._asdict(),
    })
    return baris


def ubah(folder: Path, tanggal: date) -> pl.DataFrame:
    """Semua berkas mentah Blibli satu tanggal → DataFrame `blibli_produk`."""
    folder = Path(folder)
    default = []
    for berkas in sorted(folder.glob("*_page_*.json")):
        kategori_tarik = berkas.name.split("_")[0]
        isi = json.loads(berkas.read_text(encoding="utf-8"))
        for p in (isi.get("data") or {}).get("products") or []:
            default.append(_baris_default(p, kategori_tarik, tanggal, berkas))

    opsi = []
    per_produk = {}
    for b in default:
        per_produk.setdefault(b["produk_id"], b)
    folder_varian = folder / "varian"
    if folder_varian.is_dir():
        for berkas in sorted(folder_varian.glob("is--*.json")):
            produk_id = berkas.stem.removeprefix("is--").rsplit("-", 1)[0]
            if produk_id not in per_produk:      # produk hilang dari hasil cari → dilewati
                continue
            opsi.append(_baris_opsi(berkas, per_produk[produk_id], tanggal))

    return (
        pl.DataFrame(default + opsi, schema=KOLOM_BLIBLI)
        .unique("item_sku", keep="first", maintain_order=True)
    )
