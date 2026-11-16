"""Tes evaluasi_asal.py: aturan asal_dari_nama dinilai dengan label kategori Blibli."""
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import polars as pl
import pytest

import evaluasi_asal
from transform import blibli

DASAR = Path(__file__).resolve().parent.parent
FIXTURE = DASAR / "tests" / "fixtures"
TANGGAL = date(2026, 11, 8)
LOKAL, IMPOR = "BU-1000190", "BU-1000191"


def buatan(baris: list[tuple[str, str, bool]]) -> pl.DataFrame:
    """(nama, kategori_tarik, opsi_default) → DataFrame kecil."""
    return pl.DataFrame(
        {
            "produk_id": [f"P{i}" for i in range(len(baris))],
            "nama": [b[0] for b in baris],
            "kategori_tarik": [b[1] for b in baris],
            "opsi_default": [b[2] for b in baris],
        }
    )


def test_evaluasi_pada_fixture():
    df = blibli.ubah(FIXTURE / "blibli" / f"date={TANGGAL:%Y-%m-%d}", TANGGAL)

    hasil = evaluasi_asal.evaluasi(df)

    assert hasil["n"] == df.filter(pl.col("opsi_default")).height > 0
    assert 0 <= hasil["ketepatan"] <= 1
    assert 0 <= hasil["cakupan"] <= 1
    isi = sum(j for tebakan in hasil["matriks"].values() for j in tebakan.values())
    assert isi == hasil["n"]
    assert set(hasil["matriks"]) <= {"lokal", "impor"}


def test_aturan_sempurna_bernilai_satu():
    df = buatan([
        ("Apel Fuji Impor 1 kg", IMPOR, True),
        ("Jeruk Lokal Medan 1 kg", LOKAL, True),
    ])

    hasil = evaluasi_asal.evaluasi(df)

    assert hasil == {
        "n": 2, "tepat": 2, "ketepatan": 1.0, "cakupan": 1.0,
        "matriks": {"impor": {"impor": 1}, "lokal": {"lokal": 1}},
    }


def test_tidak_diketahui_tidak_masuk_ketepatan():
    df = buatan([
        ("Apel Fuji Impor", IMPOR, True),
        ("Apel Fuji Impor", LOKAL, True),          # tebakan salah
        ("Pepaya Segar", LOKAL, True),          # aturan tidak menjawab
        ("Pepaya Segar", LOKAL, True),
    ])

    hasil = evaluasi_asal.evaluasi(df)

    assert hasil["n"] == 4
    assert hasil["tepat"] == 1
    assert hasil["ketepatan"] == 0.5               # 1 dari 2 yang terjawab
    assert hasil["cakupan"] == 0.5                 # 2 dari 4 terjawab
    assert hasil["matriks"]["lokal"] == {"impor": 1, "tidak_diketahui": 2}


def test_opsi_lain_tidak_dihitung_dua_kali():
    df = buatan([
        ("Apel Fuji Impor", IMPOR, True),
        ("Apel Fuji Impor", IMPOR, False),         # opsi lain produk yang sama
    ])

    assert evaluasi_asal.evaluasi(df)["n"] == 1


def test_kategori_asing_ditolak():
    df = buatan([("Apel Fuji Impor", "BU-9999999", True)])

    with pytest.raises(ValueError, match="BU-9999999"):
        evaluasi_asal.evaluasi(df)


def test_tanpa_jawaban_ketepatan_none():
    hasil = evaluasi_asal.evaluasi(buatan([("Pepaya Segar", LOKAL, True)]))

    assert hasil["ketepatan"] is None
    assert hasil["cakupan"] == 0.0


def jalankan_cli(akar: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-X", "utf8", "evaluasi_asal.py", "--akar", str(akar),
         "--tanggal", f"{TANGGAL:%Y-%m-%d}"],
        cwd=DASAR, capture_output=True, text=True, encoding="utf-8",
    )


def test_cli_mencetak_angka(tmp_path):
    folder = f"date={TANGGAL:%Y-%m-%d}"
    shutil.copytree(FIXTURE / "blibli" / folder, tmp_path / "raw" / "blibli" / folder)

    hasil = jalankan_cli(tmp_path)

    assert hasil.returncode == 0, hasil.stderr
    for kata in ("n", "tepat", "ketepatan", "cakupan"):
        assert kata in hasil.stdout


def test_cli_folder_tidak_ada(tmp_path):
    hasil = jalankan_cli(tmp_path)

    assert hasil.returncode != 0
    assert "tidak ada" in hasil.stderr
