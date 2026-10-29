"""Menyalin tarikan dari VPS ke laptop, dijalankan Task Scheduler setelah tarik_harian.py.

Hasil VPS disimpan di data_lake_vps/ (bukan data_lake/) supaya tidak menimpa
tarikan laptop untuk tanggal yang sama. Hanya folder bertanda _SUKSES yang disalin,
dan folder yang sudah lengkap di laptop dilewati, jadi tanggal yang terlewat
(laptop mati, VPS belum selesai) ikut tersalin pada jalan berikutnya.
Butuh kunci SSH tanpa sandi (BatchMode): tidak pernah menunggu ketikan sandi.
"""
import logging
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Callable

from tarik_harian import PENANDA

DASAR = Path(__file__).resolve().parent
AKAR_VPS = DASAR / "data_lake_vps"
LOG = DASAR / "logs" / "sinkron_vps.log"
VPS = "root@202.134.242.170"
RAW_VPS = "/root/kebun-ibu/data_lake/raw"

# pythonw (Task Scheduler) tidak punya konsol; tanpa ini ssh/scp memunculkan jendela hitam.
TANPA_JENDELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

log = logging.getLogger("sinkron_vps")


def urai_daftar(teks: str) -> list[tuple[str, str]]:
    """Mengubah keluaran `find .../raw -name _SUKSES` menjadi pasangan (sumber, folder tanggal)."""
    hasil = []
    for baris in teks.splitlines():
        if baris.strip():
            bagian = PurePosixPath(baris.strip()).parts
            hasil.append((bagian[-3], bagian[-2]))
    return sorted(hasil)


def daftar_sukses_vps() -> list[tuple[str, str]]:
    keluaran = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", VPS, f"find {RAW_VPS} -mindepth 3 -maxdepth 3 -name {PENANDA}"],
        capture_output=True, text=True, check=True, timeout=120, creationflags=TANPA_JENDELA,
    )
    return urai_daftar(keluaran.stdout)


def perlu_disalin(daftar: list[tuple[str, str]], akar: Path) -> list[tuple[str, str]]:
    return [(sumber, folder) for sumber, folder in daftar if not (Path(akar) / "raw" / sumber / folder / PENANDA).exists()]


def jalankan_scp(perintah: list[str], cwd: Path) -> None:
    subprocess.run(perintah, cwd=cwd, check=True, capture_output=True, timeout=600, creationflags=TANPA_JENDELA)


def salin_folder(sumber: str, folder: str, akar: Path, scp: Callable[..., None] = jalankan_scp) -> None:
    """Menyalin ke folder .sementara dulu, baru diganti nama setelah scp selesai.

    Jadi salinan yang putus di tengah jalan tidak pernah terlihat sebagai folder tanggal yang lengkap.
    """
    induk = Path(akar) / "raw" / sumber
    induk.mkdir(parents=True, exist_ok=True)
    sementara = induk / f"{folder}.sementara"
    akhir = induk / folder
    if sementara.exists():
        shutil.rmtree(sementara)
    # Nama tujuan relatif terhadap cwd: path Windows "C:\..." punya titik dua yang bisa dikira nama host oleh scp.
    try:
        scp(["scp", "-r", "-q", "-o", "BatchMode=yes", f"{VPS}:{RAW_VPS}/{sumber}/{folder}", sementara.name], cwd=induk)
    except Exception:
        shutil.rmtree(sementara, ignore_errors=True)
        raise
    if akhir.exists():
        shutil.rmtree(akhir)
    sementara.rename(akhir)


def jalankan(
    daftar: list[tuple[str, str]],
    akar: Path,
    salin: Callable[[str, str, Path], None] = salin_folder,
) -> int:
    """Menyalin setiap folder sukses di VPS yang belum lengkap di laptop. Mengembalikan jumlah yang gagal."""
    gagal = 0
    baru = perlu_disalin(daftar, akar)
    if not baru:
        log.info("tidak ada folder baru di VPS")
    for sumber, folder in baru:
        try:
            salin(sumber, folder, akar)
        except Exception:
            log.exception("%s/%s: gagal disalin", sumber, folder)
            gagal += 1
            continue
        log.info("%s/%s: disalin", sumber, folder)
    return gagal


def main() -> int:
    LOG.parent.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG, encoding="utf-8"), logging.StreamHandler()],
    )
    try:
        daftar = daftar_sukses_vps()
    except Exception:
        log.exception("gagal membaca daftar folder di VPS")
        return 1
    gagal = jalankan(daftar, AKAR_VPS)
    log.info("selesai, %d folder gagal", gagal)
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
