"""
Bersihkan hasil tarikan Blibli jadi tabel buah segar yang bisa dihitung.

Dua masalah yang ditemukan waktu memeriksa hasil mentah:

1. Mencari "pisang" di Blibli mengembalikan Liquid Vape, sirup, susu UHT,
   keripik, sampai tabir surya "Banana Boat". Dari sekitar 700 hasil,
   hanya 92 yang benar-benar buah. Menyaring lewat NAMA saja tidak cukup;
   yang dipakai di sini jenjang kategori dari Blibli sendiri.

2. Nama seperti "Mangga manalagi 1/2 kg" terbaca "2 kg" oleh pembaca
   berat yang pertama, jadi harganya jatuh 4x lipat.
"""

import csv
import io
import re
import statistics as st
from collections import Counter

# Hanya kategori buah segar. Olahan (keripik, sale, sirup) sengaja dibuang
# karena harga per kg-nya memang beda jenis, bukan salah data.
KATEGORI_BUAH = ("Buah Lokal", "Buah Impor", "Buah - buahan", "Buah Potong")

# Olahan yang kadang tetap lolos kategori buah.
POLA_OLAHAN = re.compile(
    r"\b(keripik|kripik|sale|selai|jus|juice|sirup|manisan|kering|dried|"
    r"puree|bubuk|powder|bibit|benih|tanaman|pohon|okulasi|jantung|daun|kulit)\b",
    re.I,
)

# Berat: tolak yang didahului "/" supaya "1/2 kg" tidak terbaca "2 kg".
POLA_BERAT = re.compile(
    r"(?<![/\d])(\d+(?:[.,]\d+)?)\s*(?:-\s*(\d+(?:[.,]\d+)?)\s*)?(kg|kilogram|gram|gr|g)\b",
    re.I,
)


def berat_gram(nama: str) -> float | None:
    if re.search(r"\d\s*/\s*\d\s*kg", nama, re.I):
        return None  # "1/2 kg" dan sejenisnya: dilewati, bukan ditebak
    cocok = POLA_BERAT.search(nama)
    if not cocok:
        return None
    awal = float(cocok.group(1).replace(",", "."))
    akhir = float(cocok.group(2).replace(",", ".")) if cocok.group(2) else awal
    nilai = (awal + akhir) / 2
    gram = nilai * 1000 if cocok.group(3).lower().startswith("k") else nilai
    return gram if 100 <= gram <= 20_000 else None


def main() -> None:
    mentah = list(csv.DictReader(io.open("data-mentah/blibli_buah.csv", encoding="utf-8")))
    alasan = Counter()
    bersih = []

    for r in mentah:
        kategori = r["kategori"]
        if not any(k in kategori for k in KATEGORI_BUAH):
            alasan["bukan kategori buah"] += 1
            continue
        if POLA_OLAHAN.search(r["nama"]):
            alasan["olahan / bukan buah utuh"] += 1
            continue
        if not r["harga"]:
            alasan["tanpa harga"] += 1
            continue

        gram = berat_gram(r["nama"])
        if not gram:
            alasan["berat tidak tertulis"] += 1
            continue

        harga = float(r["harga"])
        per_kg = harga / gram * 1000
        if not 3_000 <= per_kg <= 200_000:
            alasan["harga/kg di luar akal"] += 1
            continue

        r["berat_gram"] = round(gram)
        r["harga_per_kg"] = round(per_kg)
        r["buah"] = "mangga" if "mangga" in r["kata_cari"] else "pisang"
        bersih.append(r)

    print(f"{len(mentah)} baris mentah -> {len(bersih)} baris terpakai "
          f"({len(bersih)/len(mentah)*100:.1f}%)\n")
    print("DIBUANG KARENA:")
    for k, n in alasan.most_common():
        print(f"  {n:>5}  {k}")

    with open("data-mentah/blibli_bersih.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(bersih[0]))
        w.writeheader()
        w.writerows(bersih)

    print("\n=== HARGA PER KG (setelah dibersihkan) ===")
    for jenis in ("mangga", "pisang"):
        v = sorted(b["harga_per_kg"] for b in bersih if b["buah"] == jenis)
        if v:
            print(f"  {jenis:<8} n={len(v):>3}  "
                  f"p25 Rp {v[len(v)//4]:>6,}  median Rp {st.median(v):>6,.0f}  "
                  f"p75 Rp {v[3*len(v)//4]:>6,}")


if __name__ == "__main__":
    main()
