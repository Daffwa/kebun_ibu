"""
Tarik daftar produk buah dari pencarian Blibli.

Blibli menolak permintaan tanpa header browser lengkap (403), jadi
headernya ditiru persis seperti yang dikirim halaman aslinya.

Keluaran: satu baris per produk, plus kolom hasil pembersihan:
  - bibit          : True kalau yang dijual tanaman, bukan buah
  - berat_gram     : diambil dari nama produk kalau ada
  - harga_per_kg   : hanya terisi kalau beratnya ketahuan
"""

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request

CARI = "https://www.blibli.com/backend/search/products"

KEPALA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    "Origin": "https://www.blibli.com",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

# Yang dijual tanaman, bukan buah. Ini penyebab utama angka jadi ngawur:
# satu batang bibit Miyazaki Rp68.000 masuk ke rata-rata harga buah.
POLA_BIBIT = re.compile(
    r"\b(bibit|benih|tanaman|pohon|okulasi|cangkok|tabulampot|stek|pupuk|seedling)\b",
    re.I,
)

# "470 - 500 G", "1 kg", "500 gram", "0.9 - 1.1 kg"
POLA_BERAT = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:-\s*(\d+(?:[.,]\d+)?)\s*)?(kg|kilogram|gram|gr|g)\b",
    re.I,
)


def angka(teks: str) -> float:
    return float(teks.replace(",", "."))


def berat_gram(nama: str) -> float | None:
    """Ambil berat dari nama produk. Rentang diambil titik tengahnya."""
    cocok = POLA_BERAT.search(nama)
    if not cocok:
        return None
    awal = angka(cocok.group(1))
    akhir = angka(cocok.group(2)) if cocok.group(2) else awal
    nilai = (awal + akhir) / 2
    satuan = cocok.group(3).lower()
    gram = nilai * 1000 if satuan.startswith("k") else nilai
    # Di bawah 50 g biasanya bukan berat ("Mangga 3 G" = 3 gratis?),
    # di atas 50 kg pasti salah baca.
    return gram if 50 <= gram <= 50_000 else None


def satu_halaman(kata: str, halaman: int) -> dict:
    param = urllib.parse.urlencode(
        {
            "searchTerm": kata,
            "page": halaman,
            "start": (halaman - 1) * 40,
            "itemPerPage": 40,
            "channelId": "web",
        }
    )
    kepala = dict(KEPALA)
    kepala["Referer"] = f"https://www.blibli.com/jual/{urllib.parse.quote(kata)}"
    permintaan = urllib.request.Request(f"{CARI}?{param}", headers=kepala)
    with urllib.request.urlopen(permintaan, timeout=60) as jawaban:
        return json.load(jawaban)


def ratakan(produk: dict, kata: str) -> dict:
    nama = produk.get("name", "")
    harga = (produk.get("price") or {}).get("salePrice")
    ulasan = produk.get("review") or {}
    jenjang = produk.get("categoryNameHierarchy") or []
    gram = berat_gram(nama)

    return {
        "kata_cari": kata,
        "id": produk.get("id"),
        "nama": nama,
        "harga": harga,
        "harga_coret": (produk.get("price") or {}).get("listPrice"),
        "diskon_persen": (produk.get("price") or {}).get("discount"),
        "penjual": produk.get("merchantName"),
        "resmi": produk.get("official"),
        "lokasi": produk.get("location"),
        "kategori": " > ".join(jenjang),
        "rating": ulasan.get("absoluteRating"),
        "jumlah_ulasan": ulasan.get("count"),
        "rating_penjual": ulasan.get("sellerRating"),
        "total_terjual": produk.get("soldCountTotal"),
        "bibit": bool(POLA_BIBIT.search(nama)) or "Tanaman" in " ".join(jenjang),
        "berat_gram": gram,
        "harga_per_kg": round(harga / gram * 1000) if (harga and gram) else None,
    }


def main() -> None:
    kata_kunci = sys.argv[1:] or [
        "mangga",
        "mangga harum manis",
        "mangga manalagi",
        "pisang",
        "pisang cavendish",
        "pisang ambon",
    ]
    maks_halaman = 20

    semua: list[dict] = []
    terlihat: set[str] = set()

    for kata in kata_kunci:
        for halaman in range(1, maks_halaman + 1):
            try:
                jawaban = satu_halaman(kata, halaman)
            except Exception as galat:  # noqa: BLE001
                print(f"  {kata} hal {halaman}: GAGAL - {galat}")
                break

            data = jawaban.get("data") or {}
            produk = data.get("products") or []
            if not produk:
                break

            baru = 0
            for p in produk:
                baris = ratakan(p, kata)
                kunci = str(baris["id"])
                if kunci in terlihat:
                    continue
                terlihat.add(kunci)
                semua.append(baris)
                baru += 1

            total = (data.get("paging") or {}).get("total_page", 0)
            if halaman == 1:
                print(f"{kata}: {(data.get('paging') or {}).get('total_item')} hasil, "
                      f"{min(total, maks_halaman)} halaman diambil")
            if halaman >= total:
                break
            time.sleep(1.2)

    if not semua:
        print("Tidak ada data.")
        return

    keluaran = "data-mentah/blibli_buah.csv"
    with open(keluaran, "w", newline="", encoding="utf-8") as berkas:
        penulis = csv.DictWriter(berkas, fieldnames=list(semua[0]))
        penulis.writeheader()
        penulis.writerows(semua)

    bibit = sum(1 for b in semua if b["bibit"])
    berat = sum(1 for b in semua if b["harga_per_kg"])
    print(f"\n{len(semua)} produk unik -> {keluaran}")
    print(f"  bibit/tanaman disaring : {bibit} ({bibit/len(semua)*100:.1f}%)")
    print(f"  beratnya ketahuan      : {berat} ({berat/len(semua)*100:.1f}%)")


if __name__ == "__main__":
    main()
