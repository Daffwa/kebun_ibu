"""Fixture uji silang untuk halaman web /admin/pasar.

Menjalankan fungsi Langkah 2 notebook `dashboard_contoh.ipynb` (batas_data, status_preset,
rentang_preset, kerapatan, deret) pada data asli gudang dan data sintetis 3 tahun, lalu menulis
hasilnya ke `src/lib/pasar.fixture.json`. `src/lib/pasar.test.ts` memastikan port TypeScript-nya
memberi hasil yang sama.

Fungsi notebook diambil dengan `exec` sel kodenya, jadi tidak ada salinan kedua.
Jalankan ulang kalau aturan Langkah 2 di notebook berubah:

    cd data-science
    .venv/Scripts/python ekspor_uji_web.py
"""
import json
import math
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from dashboard_manalagi import hitung

FOLDER = Path(__file__).parent
NOTEBOOK = FOLDER / "dashboard_contoh.ipynb"
KELUARAN = FOLDER.parent / "src" / "lib" / "pasar.fixture.json"

PRESET = {"30 hari": "30h", "1 tahun": "1t", "5 tahun": "5t", "Semua": "semua"}
KOLOM_HARIAN = ["tanggal", "pasar", "jumlah_produk", "median", "indeks_berantai",
                "median_rasio", "lonjak_pasar", "naik", "turun"]
KOLOM_TITIK = ["jumlah_produk", "median", "indeks_berantai", "median_rasio",
               "naik", "turun", "lonjak_pasar", "berdata"]
KUSTOM = [("2027-02-20", "2027-03-20"), ("2027-01-01", "2027-06-30"), ("2027-12-01", "2028-03-15"), ("2028-02-29", "2029-02-28")]


def fungsi_notebook(harian: pd.DataFrame) -> dict:
    """Namespace berisi fungsi Langkah 2 notebook, dengan `harian` sebagai data globalnya."""
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sel = next("".join(c["source"]) for c in nb["cells"]
               if c["cell_type"] == "code" and "def deret(" in "".join(c["source"]))
    ns = {"pd": pd, "np": np, "harian": harian, "baris": None,
          "mdates": None, "plt": None, "mtick": None, "sns": None}
    exec(sel, ns)
    return ns


def angka(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    return float(v)


def tgl(t) -> str:
    return pd.Timestamp(t).strftime("%Y-%m-%d")


def sintetis() -> pd.DataFrame:
    rng = np.random.default_rng(13)
    akhir = pd.Timestamp("2029-12-31")
    kosong = set(pd.date_range("2027-03-01", "2027-03-07"))
    potong = []
    for pasar, mulai in [("blibli", "2026-11-07"), ("tokopedia", "2026-11-08"), ("semua", "2026-11-07")]:
        hari = pd.date_range(mulai, akhir)
        median = 30_000 * np.cumprod(1 + rng.normal(0, 0.03, len(hari)))
        indeks = 30_000 * np.cumprod(1 + rng.normal(0, 0.02, len(hari)))
        rasio = 1 + rng.normal(0, 0.04, len(hari))
        rasio[:7] = np.nan
        df = pd.DataFrame({
            "tanggal": hari, "pasar": pasar,
            "jumlah_produk": rng.integers(5, 30, len(hari)),
            "median": median.round(2), "indeks_berantai": indeks.round(4),
            "median_rasio": rasio.round(6),
            "naik": rng.integers(0, 4, len(hari)), "turun": rng.integers(0, 4, len(hari)),
        })
        df["lonjak_pasar"] = (df["median_rasio"] - 1).abs().ge(0.05).fillna(False)
        buang = rng.random(len(hari)) < 0.05
        buang[0] = False                                   # hari pertama tetap ada (batas data)
        df = df[~buang & ~df["tanggal"].isin(kosong)]
        potong.append(df)
    harian = pd.concat(potong, ignore_index=True)
    harian["rata_rata"] = harian["median"]
    harian["tertimbang"] = harian["median"]
    return harian


def asli() -> pd.DataFrame:
    with duckdb.connect(str(FOLDER / "warehouse" / "harga_buah.duckdb"), read_only=True) as con:
        _, harian = hitung(con)
    harian = harian.to_pandas()
    harian["tanggal"] = pd.to_datetime(harian["tanggal"])
    return harian


def titik(d: pd.DataFrame) -> list[dict]:
    hasil = []
    for t, r in d.iterrows():
        baris = {"tanggal": tgl(t)}
        for k in KOLOM_TITIK:
            v = angka(r[k])
            baris[k] = None if v is None else (int(v) if k in ("lonjak_pasar", "berdata") else v)
        hasil.append(baris)
    return hasil


def ekspor(harian: pd.DataFrame) -> dict:
    nb = fungsi_notebook(harian)
    status, kasus, rentang = {}, [], []
    for pasar in ["semua", "blibli", "tokopedia"]:
        if not (harian["pasar"] == pasar).any():
            continue
        awal, akhir = nb["batas_data"](pasar)
        st = nb["status_preset"](pasar)
        status[pasar] = {PRESET[n]: {"terbuka": bool(b), "pesan": p} for n, (b, p) in st.items()}
        rentang_uji = []
        for nama, kode in PRESET.items():
            mulai, sampai = nb["rentang_preset"](pasar, nama)
            rentang.append({"pasar": pasar, "preset": kode, "mulai": tgl(mulai), "akhir": tgl(sampai)})
            if nama == "Semua" or st[nama][0]:
                rentang_uji.append((mulai, sampai))
        for dari, sampai in KUSTOM:
            dari, sampai = pd.Timestamp(dari), pd.Timestamp(sampai)
            if awal <= dari and sampai <= akhir:
                rentang_uji.append((dari, sampai))
        for mulai, sampai in rentang_uji:
            d, satuan = nb["deret"](pasar, mulai, sampai)
            kasus.append({"pasar": pasar, "mulai": tgl(mulai), "akhir": tgl(sampai),
                          "satuan": satuan, "titik": titik(d)})
    baris = [{k: (tgl(r[k]) if k == "tanggal" else r[k] if k == "pasar" else angka(r[k])) for k in KOLOM_HARIAN}
             for _, r in harian[KOLOM_HARIAN].iterrows()]
    return {"harian": baris, "status": status, "kasus": kasus, "rentang": rentang}


def main():
    data = {"asli": ekspor(asli()), "sintetis": ekspor(sintetis())}
    KELUARAN.write_text(json.dumps({"data": data}, indent=1, ensure_ascii=False), encoding="utf-8")
    for nama, d in data.items():
        satuan = sorted({k["satuan"] for k in d["kasus"]})
        print(f"{nama}: {len(d['harian'])} baris harian, {len(d['kasus'])} kasus, satuan {satuan}")
    print(f"{KELUARAN} · {KELUARAN.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
