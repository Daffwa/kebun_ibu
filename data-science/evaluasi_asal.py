"""Seberapa tepat aturan `asal_dari_nama` (dipakai untuk Tokopedia)? Dinilai dengan Blibli.

Blibli menarik dua kategori, jadi asal setiap produk Blibli sudah diketahui:
BU-1000190 = Buah Lokal, BU-1000191 = Buah Impor. Aturannya dijalankan pada nama
produk Blibli lalu dibandingkan dengan label itu.

Satu produk dihitung sekali (baris opsi default saja), supaya produk dengan
banyak opsi tidak dihitung berkali-kali.

Contoh:
    python evaluasi_asal.py --tanggal 2026-11-08
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import polars as pl

from transform import blibli
from transform.parser import asal_dari_nama

DASAR = Path(__file__).resolve().parent
LABEL = {"BU-1000190": "lokal", "BU-1000191": "impor"}
TIDAK_DIKETAHUI = "tidak_diketahui"
AMBANG = 0.90   # spec 13.3


def evaluasi(df: pl.DataFrame) -> dict:
    """Bandingkan tebakan aturan dengan label kategori.

    - `n`: jumlah produk;
    - `tepat`: tebakan yang sama dengan label;
    - `ketepatan`: tepat / produk yang dijawab aturan (`None` kalau tidak ada yang dijawab);
    - `cakupan`: porsi produk yang dijawab aturan (bukan `tidak_diketahui`);
    - `matriks`: label -> tebakan -> jumlah.
    """
    produk = df.filter(pl.col("opsi_default"))
    asing = set(produk["kategori_tarik"].unique().to_list()) - set(LABEL)
    if asing:
        raise ValueError(f"kategori_tarik tanpa label: {sorted(asing, key=str)}")

    pasangan = produk.select(
        label=pl.col("kategori_tarik").replace_strict(LABEL),
        tebakan=pl.col("nama").map_elements(asal_dari_nama, return_dtype=pl.Utf8),
    )
    n = pasangan.height
    dijawab = pasangan.filter(pl.col("tebakan") != TIDAK_DIKETAHUI)
    tepat = dijawab.filter(pl.col("tebakan") == pl.col("label")).height

    matriks: dict[str, dict[str, int]] = {}
    for label, tebakan, jumlah in pasangan.group_by("label", "tebakan").len().sort("label", "tebakan").rows():
        matriks.setdefault(label, {})[tebakan] = jumlah

    return {
        "n": n,
        "tepat": tepat,
        "ketepatan": tepat / dijawab.height if dijawab.height else None,
        "cakupan": dijawab.height / n if n else 0.0,
        "matriks": matriks,
    }


def baca_argumen(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--akar", type=Path, default=DASAR / "data_lake", help="folder data lake")
    parser.add_argument("--tanggal", type=date.fromisoformat, required=True, help="YYYY-MM-DD")
    return parser.parse_args(argv)


def main() -> int:
    a = baca_argumen()
    folder = a.akar / "raw" / "blibli" / f"date={a.tanggal:%Y-%m-%d}"
    if not folder.is_dir():
        print(f"data mentah tidak ada: {folder}", file=sys.stderr)
        return 1

    hasil = evaluasi(blibli.ubah(folder, a.tanggal))
    ketepatan = hasil["ketepatan"]
    print(f"n         : {hasil['n']}")
    print(f"tepat     : {hasil['tepat']}")
    print(f"ketepatan : {'-' if ketepatan is None else f'{ketepatan:.1%}'}")
    print(f"cakupan   : {hasil['cakupan']:.1%}")
    for label, isi in hasil["matriks"].items():
        print(f"  label {label:5}: {isi}")
    if ketepatan is None or ketepatan < AMBANG:
        print(f"PERINGATAN: ketepatan di bawah {AMBANG:.0%}; anggap asal Tokopedia "
              f"'{TIDAK_DIKETAHUI}' di analisis.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
