"""
Tarik harga pangan harian Bali dari SIGAPURA (Pemprov Bali).

API-nya tidak didokumentasikan, tapi terbuka: alamatnya ditemukan dari
berkas JavaScript situs sigapura.baliprov.go.id. Tidak perlu kunci.

Dipecah per tahun karena satu permintaan untuk rentang panjang
kehabisan waktu di server mereka.
"""

import csv
import json
import sys
import time
import urllib.request

BASIS = "https://dashboard-sigapura.baliprov.go.id/api/v1"
KEPALA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
    "Referer": "https://sigapura.baliprov.go.id/",
    "Accept": "application/json",
}


def ambil(komoditas: int, pasar: str, mulai: str, akhir: str) -> dict:
    url = (
        f"{BASIS}/market-price-commodity-per-date"
        f"?commodity_id={komoditas}&mart_type={pasar}"
        f"&report_type=harian&start_date={mulai}&end_date={akhir}&district_id="
    )
    permintaan = urllib.request.Request(url, headers=KEPALA)
    with urllib.request.urlopen(permintaan, timeout=180) as jawaban:
        return json.load(jawaban)


def ratakan(mentah: dict, pasar: str) -> list[dict]:
    """Bentuk aslinya bersarang tiga lapis; diratakan jadi satu baris per hari."""
    baris = []
    for _kabupaten, catatan in mentah["data"]["market_price"].items():
        for per_tanggal in catatan:
            for _label, isi in per_tanggal.items():
                harga = isi.get("avg_market_price")
                if harga in (None, 0):
                    continue  # hari tanpa laporan petugas
                baris.append(
                    {
                        "komoditas": isi["commodity_name"],
                        "komoditas_id": isi["commodity_id"],
                        "tanggal": isi["input_date"],
                        "kabupaten": isi["district_name"],
                        "kabupaten_id": isi["district_id"],
                        "jenis_pasar": pasar,
                        "satuan": isi["unit"],
                        "harga": harga,
                    }
                )
    return baris


def main() -> None:
    komoditas = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    tahun_awal = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
    tahun_akhir = int(sys.argv[3]) if len(sys.argv) > 3 else 2026

    semua: list[dict] = []
    for pasar in ("tradisional", "modern"):
        for tahun in range(tahun_awal, tahun_akhir + 1):
            akhir = f"{tahun}-12-31" if tahun < tahun_akhir else "2026-09-27"
            try:
                mentah = ambil(komoditas, pasar, f"{tahun}-01-01", akhir)
                baru = ratakan(mentah, pasar)
                semua.extend(baru)
                print(f"{pasar} {tahun}: {len(baru)} baris")
            except Exception as galat:  # noqa: BLE001
                print(f"{pasar} {tahun}: GAGAL - {galat}")
            time.sleep(1)

    if not semua:
        print("Tidak ada data.")
        return

    semua.sort(key=lambda b: (b["tanggal"], b["kabupaten"], b["jenis_pasar"]))
    keluaran = f"data-mentah/sigapura_komoditas_{komoditas}.csv"
    with open(keluaran, "w", newline="", encoding="utf-8") as berkas:
        penulis = csv.DictWriter(berkas, fieldnames=list(semua[0]))
        penulis.writeheader()
        penulis.writerows(semua)

    print(f"\n{len(semua)} baris -> {keluaran}")
    print(f"rentang: {semua[0]['tanggal']} .. {semua[-1]['tanggal']}")


if __name__ == "__main__":
    main()
