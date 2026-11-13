"""Pipeline harga buah: extract -> transform -> load, satu baris pipeline_runs per sumber.

Contoh:
    python run.py                                   # semua sumber, hari ini, ketiga tahap
    python run.py --tahap transform,load --tanggal 2026-11-08
    python run.py --sumber tokopedia

Tanpa --tanggal, run juga menyusulkan tanggal tertinggal: tanggal sebelum hari ini
(mulai MULAI_GUDANG) yang punya folder `_SUKSES` di data_lake/ atau data_lake_vps/
tetapi belum pernah dimuat. Kalau folder laptop tidak bertanda `_SUKSES` tetapi
salinan VPS ada, salinan VPS yang dipakai (status `sebagian` kalau tanpa halaman varian).

Extract dilewati kalau tanggal itu sudah punya penanda `_SUKSES` (dari
tarik_harian.py atau run.py sebelumnya), karena siapkan_folder menghapus folder
tanggal itu sebelum menarik. Tarik ulang paksa: `python tarik_harian.py --ulang <sumber>`.

Arti angka di pipeline_runs:
- baris_mentah    = baris lapisan 1 (sesudah buang ganda, sebelum validasi);
- baris_dimuat    = baris yang lolos validasi lapisan 1 dan SkemaFakta (= baris fakta_harga);
- baris_karantina = baris yang ditahan, jadi dimuat + karantina = mentah.
  Baris cek H (berat_dikali) hanya disalin ke produk_karantina dan tetap dimuat,
  jadi tidak dihitung di sini.
"""
import argparse
import logging
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import duckdb
import polars as pl

from extract import blibli as tarik_blibli
from extract import tokopedia as tarik_tokopedia
from extract.http import HasilTarik
from load import duckdb_loader
from tarik_harian import PENANDA, folder_tanggal
from transform import blibli, model, skema, tokopedia

DASAR = Path(__file__).resolve().parent
SUMBER = ["blibli", "tokopedia"]
TAHAP = ["extract", "transform", "load"]
AKAR_VPS = DASAR / "data_lake_vps"
# Tanggal pertama yang lengkap (harga semua opsi), keputusan pengguna 9 Nov.
MULAI_GUDANG = {"blibli": date(2026, 11, 7), "tokopedia": date(2026, 11, 8)}
# Subfolder harga opsi selain bawaan; VPS menjalankan versi lama tanpa subfolder ini.
SUB_VARIAN = {"blibli": "varian", "tokopedia": "halaman"}

PENARIK: dict[str, Callable[[date, Path], HasilTarik]] = {
    "blibli": tarik_blibli.tarik,
    "tokopedia": tarik_tokopedia.tarik,
}
_UBAH = {
    "blibli": (blibli.ubah, skema.SkemaBlibli),
    "tokopedia": (tokopedia.ubah, skema.SkemaTokopedia),
}

log = logging.getLogger("run")


class _ExtractGagal(Exception):
    """Extract berstatus `gagal`: transform/load tidak dijalankan."""


def _pilih_folder(sumber: str, tanggal: date, akar: Path, akar_vps: Path | None) -> tuple[Path, bool]:
    """Folder laptop kalau bertanda `_SUKSES`; kalau tidak, salinan VPS yang bertanda `_SUKSES`.

    Mengembalikan (folder, dari_vps). Tanpa keduanya: folder laptop (bisa tarikan `sebagian`).
    """
    laptop = folder_tanggal(akar, sumber, tanggal)
    if akar_vps is not None and not (laptop / PENANDA).exists():
        vps = folder_tanggal(akar_vps, sumber, tanggal)
        if (vps / PENANDA).exists():
            return vps, True
    return laptop, False


def _transform_load(
    con: duckdb.DuckDBPyConnection, sumber: str, tanggal: date, akar: Path, muat: bool, run: dict,
    akar_vps: Path | None = None,
) -> None:
    folder, dari_vps = _pilih_folder(sumber, tanggal, akar, akar_vps)
    if not folder.is_dir():
        raise FileNotFoundError(f"data mentah tidak ada: {folder}")
    if dari_vps:
        lengkap = (folder / SUB_VARIAN[sumber]).is_dir()
        run["pesan_galat"] = "data dari data_lake_vps" + ("" if lengkap else " (tanpa halaman varian)")
        if not lengkap:
            run["status"] = "sebagian"
        log.info("%s: %s", sumber, run["pesan_galat"])
    ubah, skema_lapisan1 = _UBAH[sumber]

    mentah = ubah(folder, tanggal)
    if mentah.height == 0:  # tarikan gagal sesudah folder dibuat (11 Nov: DNS putus)
        raise ValueError(f"data mentah kosong: {folder}")
    lolos, karantina = skema.pisahkan(mentah, skema_lapisan1, sumber)
    if sumber == "blibli":
        bintang = model.bangun(lolos, None)
    else:   # induk dari gudang hanya dipakai sampai BATAS_PETA_INDUK
        bintang = model.bangun(None, lolos, peta_induk=duckdb_loader.peta_induk(con, tanggal))
    fakta, karantina_fakta = skema.pisahkan(bintang.fakta_harga, skema.SkemaFakta, sumber)

    tahan_lapisan1 = mentah.height - lolos.height
    tahan_fakta = bintang.fakta_harga.height - fakta.height
    bintang.fakta_harga = fakta
    run["baris_mentah"] = mentah.height
    run["baris_dimuat"] = fakta.height
    run["baris_karantina"] = tahan_lapisan1 + tahan_fakta
    log.info("%s: mentah %d, dimuat %d, karantina %d (lapisan 1 %d, fakta %d)", sumber,
             mentah.height, fakta.height, run["baris_karantina"], tahan_lapisan1, tahan_fakta)

    if muat:
        semua_karantina = pl.concat([karantina, karantina_fakta])
        duckdb_loader.muat(con, sumber, tanggal, lolos, semua_karantina, bintang)
        log.info("%s: dimuat ke gudang", sumber)


def _satu_sumber(
    con: duckdb.DuckDBPyConnection,
    run_id: str,
    sumber: str,
    tanggal: date,
    tahap: set[str],
    akar: Path,
    penarik: dict[str, Callable[[date, Path], HasilTarik]],
    akar_vps: Path | None = None,
) -> dict:
    run = {
        "run_id": run_id, "mulai": datetime.now(), "selesai": None,
        "sumber": sumber, "tanggal": tanggal, "halaman_ditarik": 0, "baris_mentah": 0,
        "baris_dimuat": 0, "baris_karantina": 0, "status": "berhasil", "pesan_galat": None,
    }
    try:
        penanda = folder_tanggal(akar, sumber, tanggal) / PENANDA
        if "extract" in tahap and penanda.exists():
            log.info("%s: extract dilewati, %s sudah sukses", sumber, tanggal)
        elif "extract" in tahap:
            hasil = penarik[sumber](tanggal, akar)
            run["halaman_ditarik"] = hasil.halaman
            log.info("%s: extract %s, %d halaman %s", sumber, hasil.status, hasil.halaman, hasil.pesan or "")
            if hasil.status == "berhasil":
                penanda.touch()
            else:
                run["status"], run["pesan_galat"] = hasil.status, hasil.pesan
            if hasil.status == "gagal":
                raise _ExtractGagal(hasil.pesan)
        if "transform" in tahap:
            _transform_load(con, sumber, tanggal, akar, "load" in tahap, run, akar_vps)
    except _ExtractGagal:
        pass
    except Exception as galat:
        log.exception("%s: galat", sumber)
        run["status"], run["pesan_galat"] = "gagal", str(galat)
    run["selesai"] = datetime.now()
    return run


def jalankan(
    sumber: list[str],
    tanggal: date,
    tahap: set[str],
    akar: Path,
    db: Path,
    penarik: dict[str, Callable[[date, Path], HasilTarik]] | None = None,
    folder_log: Path | None = None,
    akar_vps: Path | None = None,
) -> list[dict]:
    """Jalankan pipeline untuk setiap sumber; satu sumber gagal tidak menghentikan yang lain.

    `folder_log`: kalau diisi, setiap run juga ditulis ke `run_<run_id>.log` di sana.
    `akar_vps`: kalau diisi, salinan VPS dipakai saat folder laptop tidak bertanda `_SUKSES`.
    """
    if "load" in tahap and "transform" not in tahap:
        raise ValueError("tahap load butuh tahap transform")
    penarik = PENARIK if penarik is None else penarik
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    runs = []
    with duckdb.connect(str(db)) as con:
        duckdb_loader.siapkan(con)
        for s in sumber:
            run_id = str(uuid.uuid4())
            berkas_log = _pasang_log(folder_log, run_id)
            try:
                run = _satu_sumber(con, run_id, s, tanggal, tahap, akar, penarik, akar_vps)
                log.info("%s: selesai %s run_id=%s", s, run["status"], run_id)
                duckdb_loader.catat_run(con, run)
            finally:
                _lepas_log(berkas_log)
            runs.append(run)
    return runs


def tanggal_tertinggal(
    db: Path,
    sumber: list[str],
    hari_ini: date,
    akar: Path,
    akar_vps: Path | None,
    mulai: dict[str, date] = MULAI_GUDANG,
) -> list[tuple[date, str]]:
    """(tanggal, sumber) sebelum hari ini yang punya folder `_SUKSES` tetapi belum pernah dimuat.

    "Sudah dimuat" = ada baris pipeline_runs `berhasil`/`sebagian` dengan baris_dimuat > 0.
    """
    sudah = set()
    if Path(db).exists():
        with duckdb.connect(str(db), read_only=True) as con:
            ada = con.execute("SELECT count(*) FROM information_schema.tables "
                              "WHERE table_name = 'pipeline_runs'").fetchone()[0]
            if ada:
                sudah = set(con.execute(
                    "SELECT DISTINCT tanggal, sumber FROM pipeline_runs "
                    "WHERE status IN ('berhasil', 'sebagian') AND baris_dimuat > 0").fetchall())
    hasil = set()
    for s in sumber:
        for a in (akar, akar_vps):
            if a is None:
                continue
            for penanda in (Path(a) / "raw" / s).glob(f"date=*/{PENANDA}"):
                try:
                    t = date.fromisoformat(penanda.parent.name.removeprefix("date="))
                except ValueError:
                    continue
                if mulai[s] <= t < hari_ini and (t, s) not in sudah:
                    hasil.add((t, s))
    return sorted(hasil)


def jalankan_harian(
    sumber: list[str],
    hari_ini: date,
    tahap: set[str],
    akar: Path,
    db: Path,
    akar_vps: Path | None = AKAR_VPS,
    folder_log: Path | None = None,
    mulai: dict[str, date] = MULAI_GUDANG,
) -> list[dict]:
    """Run terjadwal: susulkan tanggal tertinggal (transform+load saja), lalu hari ini."""
    runs = []
    if "load" in tahap:
        tertinggal = tanggal_tertinggal(db, sumber, hari_ini, akar, akar_vps, mulai)
        for t in sorted({t for t, _ in tertinggal}):
            susul = [s for u, s in tertinggal if u == t]
            log.info("menyusulkan %s: %s", t, susul)
            runs += jalankan(susul, t, {"transform", "load"}, akar, db,
                             folder_log=folder_log, akar_vps=akar_vps)
    return runs + jalankan(sumber, hari_ini, tahap, akar, db, folder_log=folder_log, akar_vps=akar_vps)


def _pasang_log(folder_log: Path | None, run_id: str) -> logging.Handler | None:
    if folder_log is None:
        return None
    folder_log.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(folder_log / f"run_{run_id}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    if log.level == logging.NOTSET:
        log.setLevel(logging.INFO)
    return handler


def _lepas_log(handler: logging.Handler | None) -> None:
    if handler is not None:
        log.removeHandler(handler)
        handler.close()


def _daftar(pilihan: list[str]) -> Callable[[str], list[str]]:
    def baca(teks: str) -> list[str]:
        nilai = [t.strip() for t in teks.split(",") if t.strip()]
        asing = [n for n in nilai if n not in pilihan]
        if asing or not nilai:
            raise argparse.ArgumentTypeError(f"pilihan: {','.join(pilihan)} (dapat: {teks!r})")
        return nilai
    return baca


def baca_argumen(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sumber", type=_daftar(SUMBER), default=list(SUMBER),
                        help="dipisah koma (bawaan: blibli,tokopedia)")
    parser.add_argument("--tanggal", type=date.fromisoformat, default=None,
                        help="YYYY-MM-DD (bawaan: hari ini + tanggal tertinggal)")
    parser.add_argument("--tahap", type=_daftar(TAHAP), default=list(TAHAP),
                        help="dipisah koma (bawaan: extract,transform,load)")
    parser.add_argument("--akar", type=Path, default=DASAR / "data_lake", help="folder data lake")
    parser.add_argument("--db", type=Path, default=DASAR / "warehouse" / "harga_buah.duckdb",
                        help="berkas DuckDB")
    argumen = parser.parse_args(argv)
    argumen.tahap = set(argumen.tahap)
    return argumen


def main() -> int:
    a = baca_argumen()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.tanggal is None:
        runs = jalankan_harian(a.sumber, date.today(), a.tahap, a.akar, a.db, folder_log=DASAR / "logs")
    else:
        runs = jalankan(a.sumber, a.tanggal, a.tahap, a.akar, a.db, folder_log=DASAR / "logs")
    return 1 if any(r["status"] == "gagal" for r in runs) else 0


if __name__ == "__main__":
    sys.exit(main())
