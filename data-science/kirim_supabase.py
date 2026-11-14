"""Mengirim data dashboard Mangga Manalagi ke Supabase, dijalankan Task Scheduler sesudah run.py.

Hanya tanggal yang BERUBAH yang dikirim. Pembandingnya salinan lokal "yang terakhir terkirim"
(warehouse/terkirim/*.parquet). Tanggal yang dimuat terlambat (misalnya dari data_lake_vps)
mengubah indeks berantai dan jendela 7 hari tanggal sesudahnya; tanggal-tanggal itu ikut terkirim.
Setiap kelompok tanggal diganti dalam satu transaksi oleh fungsi Postgres ganti_pasar_manalagi,
dan salinan lokal baru diperbarui sesudah kiriman kelompok itu berhasil.

Contoh (dari data-science/):
    python kirim_supabase.py            # kirim tanggal yang berubah
    python kirim_supabase.py --coba     # hanya tampilkan tanggal yang akan dikirim
    python kirim_supabase.py --semua    # kirim ulang semua (kalau tabel Supabase dikosongkan)

Kunci: NEXT_PUBLIC_SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY dari env var, kalau tidak ada dari
kebun-ibu/.env.local (Supabase PRODUKSI). Untuk Supabase lokal, isi kedua env var itu.
"""
import argparse
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import urlparse

import duckdb
import polars as pl
from curl_cffi import requests

from dashboard_manalagi import daftar_wilayah, hitung

DASAR = Path(__file__).resolve().parent
GUDANG = DASAR / "warehouse" / "harga_buah.duckdb"
TERKIRIM = DASAR / "warehouse" / "terkirim"
ENV = DASAR.parent / ".env.local"
LOG = DASAR / "logs" / "kirim_supabase.log"
NAMA_URL, NAMA_KUNCI = "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"

log = logging.getLogger("kirim_supabase")

# Baris harian per wilayah (selain `semua`) dan daftar wilayah baru dikirim kalau True. Nyalakan
# HANYA sesudah web membaca `.eq("wilayah", "semua")`, lalu jalankan `--semua` sekali
# (docs/superpowers/specs/2026-11-14-filter-wilayah-design.md, "Urutan supaya tidak ada yang rusak").
KIRIM_PER_WILAYAH = False

# Kolom yang disetujui 13 Nov (spec "Tabel Supabase") + kode wilayah 14 Nov; sisanya langkah
# antara, tetap di laptop. Kolom yang belum ada di Supabase diabaikan jsonb_populate_recordset.
KOLOM_BARIS = ["tanggal", "sumber", "produk_key", "nama_toko", "kota", "kabkota_kode",
               "provinsi_kode", "harga_per_kg", "terjual_min", "median_jendela", "rasio_jendela",
               "lonjak_toko"]
KOLOM_HARIAN = ["tanggal", "pasar", "wilayah", "jumlah_produk", "median", "indeks_berantai",
                "median_rasio", "lonjak_pasar", "naik", "turun"]
KUNCI = (["tanggal", "produk_key"], ["tanggal", "pasar", "wilayah"])   # primary key tabel Supabase
BERKAS = ("pasar_manalagi.parquet", "pasar_manalagi_harian.parquet")

Data = tuple[pl.DataFrame, pl.DataFrame]   # (baris, harian)


def untuk_dikirim(baris: pl.DataFrame, harian: pl.DataFrame, per_wilayah: bool | None = None) -> Data:
    """Hanya kolom yang dikirim, urut kunci; float dibulatkan 6 desimal supaya pembandingan stabil.

    `per_wilayah` None = ikut `KIRIM_PER_WILAYAH`; False = hanya baris harian `wilayah = 'semua'`.
    """
    if not (KIRIM_PER_WILAYAH if per_wilayah is None else per_wilayah):
        harian = harian.filter(pl.col("wilayah") == "semua")
    return tuple(df.select(kolom).with_columns(pl.col(pl.Float64).round(6)).sort(kunci)
                 for df, kolom, kunci in zip((baris, harian), (KOLOM_BARIS, KOLOM_HARIAN), KUNCI))


def tanggal_berubah(baru: Data, lama: Data | None) -> list[date]:
    """Tanggal yang barisnya berbeda di salah satu tabel, termasuk yang hanya ada di satu sisi.

    EXCEPT menganggap NULL sama dengan NULL, jadi kolom kosong tidak terhitung berubah.
    """
    if lama is None:
        return sorted(set(baru[0]["tanggal"].to_list()) | set(baru[1]["tanggal"].to_list()))
    con = duckdb.connect()
    try:
        bagian = []
        for i, kolom in enumerate((KOLOM_BARIS, KOLOM_HARIAN)):
            con.register(f"baru{i}", baru[i])
            con.register(f"lama{i}", lama[i])
            k = ", ".join(kolom)
            bagian += [f"SELECT tanggal FROM (SELECT {k} FROM baru{i} EXCEPT SELECT {k} FROM lama{i})",
                       f"SELECT tanggal FROM (SELECT {k} FROM lama{i} EXCEPT SELECT {k} FROM baru{i})"]
        return [t for (t,) in con.execute(" UNION ".join(bagian) + " ORDER BY 1").fetchall()]
    finally:
        con.close()


def kelompokkan(tanggal: list[date], ukuran: int = 31) -> list[list[date]]:
    return [tanggal[i:i + ukuran] for i in range(0, len(tanggal), ukuran)]


def _baris_json(df: pl.DataFrame, tanggal: list[date]) -> list[dict]:
    return (df.filter(pl.col("tanggal").is_in(tanggal))
              .with_columns(pl.col(pl.Date).dt.strftime("%Y-%m-%d"))
              .to_dicts())


def muatan(tanggal: list[date], data: Data) -> dict:
    """Isi panggilan ganti_pasar_manalagi untuk tanggal-tanggal ini."""
    return {"p_tanggal": [t.isoformat() for t in tanggal],
            "p_baris": _baris_json(data[0], tanggal),
            "p_harian": _baris_json(data[1], tanggal)}


def baca_terkirim(folder: Path) -> Data | None:
    """Salinan yang terakhir terkirim; None kalau salah satu berkas tidak ada (= kirim semua)."""
    jalur = [Path(folder) / b for b in BERKAS]
    if not all(p.exists() for p in jalur):
        return None
    salinan = pl.read_parquet(jalur[0]), pl.read_parquet(jalur[1])
    if any(not set(kolom) <= set(df.columns) for df, kolom in zip(salinan, (KOLOM_BARIS, KOLOM_HARIAN))):
        log.info("salinan terkirim berkolom lama: kirim semua")
        return None
    return salinan


def simpan_terkirim(folder: Path, lama: Data | None, baru: Data, tanggal: list[date]) -> Data:
    """Salinan = `lama` tanpa `tanggal` + `baru` untuk `tanggal`. Ditulis ke .sementara lalu diganti nama."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    hasil = []
    for i, (nama, kolom, kunci) in enumerate(zip(BERKAS, (KOLOM_BARIS, KOLOM_HARIAN), KUNCI)):
        bagian = [baru[i].filter(pl.col("tanggal").is_in(tanggal))]
        if lama is not None:
            bagian.insert(0, lama[i].filter(~pl.col("tanggal").is_in(tanggal)))
        df = pl.concat(bagian).select(kolom).sort(kunci)
        sementara = folder / f"{nama}.sementara"
        df.write_parquet(sementara)
        sementara.replace(folder / nama)
        hasil.append(df)
    return tuple(hasil)


def folder_terkirim(akar: Path, url: str) -> Path:
    """Salinan terkirim per Supabase tujuan, supaya uji ke Supabase lokal tidak mengubah salinan produksi."""
    host = urlparse(url).netloc or url
    return Path(akar) / re.sub(r"[^A-Za-z0-9.-]", "_", host)


def baca_kunci(env: Path, lingkungan: Mapping[str, str] = os.environ) -> tuple[str, str]:
    """(url, kunci service role). Galat menyebut nama, tidak pernah isinya.

    Kalau salah satu env var diisi, KEDUANYA harus dari env var: kalau tidak, URL lokal bisa
    berpasangan dengan kunci produksi dari berkas, dan kunci produksi terkirim ke URL itu.
    """
    berkas = {}
    if Path(env).exists():
        for baris in Path(env).read_text(encoding="utf-8").splitlines():
            baris = baris.strip()
            if baris and not baris.startswith("#") and "=" in baris:
                nama, nilai = baris.split("=", 1)
                berkas[nama.strip()] = nilai.strip().strip('"').strip("'")
    dari_env = any(lingkungan.get(n) for n in (NAMA_URL, NAMA_KUNCI))
    sumber, asal = (lingkungan, "env var") if dari_env else (berkas, str(env))
    hasil = []
    for nama in (NAMA_URL, NAMA_KUNCI):
        nilai = sumber.get(nama)
        if not nilai:
            raise RuntimeError(f"{nama} tidak ada di {asal} (env var dan berkas tidak dicampur)")
        hasil.append(nilai)
    return hasil[0], hasil[1]


def buat_pengirim(url: str, kunci: str, post: Callable = requests.post,
                  fungsi: str = "ganti_pasar_manalagi") -> Callable[[dict], None]:
    """Fungsi yang memanggil fungsi Postgres `fungsi` lewat PostgREST; status bukan 2xx → RuntimeError."""
    alamat = f"{url.rstrip('/')}/rest/v1/rpc/{fungsi}"
    kepala = {"apikey": kunci, "Authorization": f"Bearer {kunci}", "Content-Type": "application/json"}

    def kirim(isi: dict) -> None:
        jawaban = post(alamat, json=isi, headers=kepala, timeout=60)
        if not 200 <= jawaban.status_code < 300:
            raise RuntimeError(f"Supabase {jawaban.status_code}: {jawaban.text[:300]}")

    return kirim


def jalankan(data: Data, folder: Path, kirim: Callable[[dict], None],
             semua: bool = False, coba: bool = False) -> int:
    """Mengirim tanggal yang berubah per kelompok; mengembalikan jumlah tanggal (terkirim/akan dikirim)."""
    if data[0].is_empty() or data[1].is_empty():
        # Tanpa ini, gudang kosong membuat semua tanggal "berubah" dan Supabase dikosongkan.
        raise RuntimeError("hasil hitungan kosong: tidak ada baris Mangga Manalagi di gudang, tidak dikirim")
    lama = baca_terkirim(folder)
    berubah = tanggal_berubah(data, None if semua else lama)
    if semua and lama is not None:
        # tanggal yang hanya ada di salinan lama juga dikirim (kosong) supaya terhapus di Supabase
        berubah = sorted(set(berubah) | set(lama[0]["tanggal"].to_list()) | set(lama[1]["tanggal"].to_list()))
    if coba:
        log.info("coba: %d tanggal akan dikirim: %s", len(berubah), [t.isoformat() for t in berubah])
        return len(berubah)
    # --semua: salinan dibangun ulang dari kosong, jadi kalau kiriman putus di tengah, salinan hanya
    # memuat kelompok yang benar-benar terkirim dan jalan berikutnya mengirim sisanya.
    salinan = None if semua else lama
    for kelompok in kelompokkan(berubah):
        kirim(muatan(kelompok, data))
        salinan = simpan_terkirim(folder, salinan, data, kelompok)
        log.info("terkirim %s s.d. %s (%d tanggal)", kelompok[0], kelompok[-1], len(kelompok))
    return len(berubah)


def kirim_daftar_wilayah(daftar: pl.DataFrame, kirim: Callable[[dict], None]) -> int:
    """Ganti seluruh isi `pasar_wilayah` (fungsi ganti_pasar_wilayah); mengembalikan jumlah baris."""
    kirim({"p_baris": daftar.to_dicts()})
    return daftar.height


def baca_argumen(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--semua", action="store_true", help="kirim ulang semua tanggal, abaikan salinan terkirim")
    parser.add_argument("--coba", action="store_true", help="hanya tampilkan tanggal yang akan dikirim")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arg = baca_argumen(argv)
    LOG.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG, encoding="utf-8"), logging.StreamHandler()],
    )
    try:
        with duckdb.connect(str(GUDANG), read_only=True) as con:
            baris, harian = hitung(con)
        data = untuk_dikirim(baris, harian)
        url, kunci = baca_kunci(ENV)
        tujuan = folder_terkirim(TERKIRIM, url)
        log.info("tujuan: %s", urlparse(url).netloc)   # host saja, kunci tidak pernah ditulis
        kirim = (lambda _: None) if arg.coba else buat_pengirim(url, kunci)
        jumlah = jalankan(data, tujuan, kirim, semua=arg.semua, coba=arg.coba)
        if KIRIM_PER_WILAYAH and not arg.coba:
            n = kirim_daftar_wilayah(daftar_wilayah(baris),
                                     buat_pengirim(url, kunci, fungsi="ganti_pasar_wilayah"))
            log.info("daftar wilayah: %d baris", n)
    except Exception:
        log.exception("gagal mengirim ke Supabase")
        return 1
    if not arg.coba:
        log.info("terkirim %d tanggal; isi tabel sesudahnya: %d baris, %d baris harian",
                 jumlah, data[0].height, data[1].height)
    return 0


if __name__ == "__main__":
    sys.exit(main())
