"""Membuat `wilayah_kabkota.csv` dari `db/wilayah.sql` milik cahyadsn/wilayah.

Sumber: https://github.com/cahyadsn/wilayah (Kepmendagri No 300.2.2-2138 Tahun 2025, lisensi MIT).
Dijalankan sekali, hasilnya disimpan di repo; pipeline tidak mengunduh apa-apa.

    python referensi/buat_wilayah_kabkota.py <path ke wilayah.sql>
"""
import csv
import re
import sys
from pathlib import Path

KELUAR = Path(__file__).resolve().parent / "wilayah_kabkota.csv"
ATRIBUSI = [
    "# Sumber: cahyadsn/wilayah db/wilayah.sql (https://github.com/cahyadsn/wilayah), lisensi MIT,",
    "# copyright (c) 2025 cahya dsn. Data: Kepmendagri No 300.2.2-2138 Tahun 2025.",
    "# Dibuat oleh referensi/buat_wilayah_kabkota.py. Nama: tanpa kata 'Administrasi', tanpa spasi ujung.",
]


def nama_tampil(nama: str) -> str:
    return re.sub(r"\s+", " ", nama.replace("Administrasi", "")).strip()


def main(sql: Path) -> None:
    pasangan = re.findall(r"\('([0-9.]+)','([^']*)'\)", sql.read_text(encoding="utf-8"))
    provinsi = {k: nama_tampil(n) for k, n in pasangan if len(k) == 2}
    baris = []
    for kode, nama in pasangan:
        if not re.fullmatch(r"\d{2}\.\d{2}", kode):
            continue
        nama = nama_tampil(nama)
        jenis = "kota" if nama.startswith("Kota ") else "kabupaten"
        baris.append((kode, nama, jenis, kode[:2], provinsi[kode[:2]]))
    with KELUAR.open("w", encoding="utf-8", newline="") as f:
        f.write("\n".join(ATRIBUSI) + "\n")
        tulis = csv.writer(f, lineterminator="\n")
        tulis.writerow(["kode", "nama", "jenis", "provinsi_kode", "provinsi"])
        tulis.writerows(sorted(baris))
    print(f"{len(baris)} kab/kota, {len({b[3] for b in baris})} provinsi -> {KELUAR}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
