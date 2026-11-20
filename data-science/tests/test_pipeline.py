"""Tes integrasi run.py: fixture asli disalin ke tmp_path, tanpa internet."""
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

import run
from extract.http import HasilTarik
from load import duckdb_loader

DASAR = Path(__file__).resolve().parent.parent
FIXTURE = DASAR / "tests" / "fixtures"
TANGGAL = date(2026, 11, 8)
KEDUANYA = ["blibli", "tokopedia"]
TL = {"transform", "load"}


@pytest.fixture
def akar(tmp_path):
    akar = tmp_path / "data_lake"
    for sumber in KEDUANYA:
        folder = f"date={TANGGAL:%Y-%m-%d}"
        shutil.copytree(FIXTURE / sumber / folder, akar / "raw" / sumber / folder)
    return akar


@pytest.fixture
def db(tmp_path):
    return tmp_path / "warehouse" / "harga_buah.duckdb"


def baca(db: Path, sql: str, param: list | None = None) -> list[tuple]:
    with duckdb.connect(str(db), read_only=True) as con:
        return con.execute(sql, param or []).fetchall()


def jumlah_tabel(db: Path) -> dict[str, int]:
    return {t: baca(db, f"SELECT count(*) FROM {t}")[0][0] for t in duckdb_loader.TABEL}


def fakta(db: Path, sumber: str) -> int:
    return baca(db, "SELECT count(*) FROM fakta_harga WHERE sumber = ?", [sumber])[0][0]


def penarik_palsu(hasil: HasilTarik):
    return lambda tanggal, akar: hasil


def test_transform_load_dari_mentah_yang_ada(akar, db):
    runs = run.jalankan(KEDUANYA, TANGGAL, TL, akar, db)

    assert [r["sumber"] for r in runs] == KEDUANYA
    for r in runs:
        assert r["status"] == "berhasil", r["pesan_galat"]
        assert r["halaman_ditarik"] == 0
        assert r["baris_mentah"] > 0
        assert r["baris_dimuat"] + r["baris_karantina"] == r["baris_mentah"]
        assert fakta(db, r["sumber"]) == r["baris_dimuat"]
    tersimpan = baca(db, "SELECT sumber, status, baris_dimuat FROM pipeline_runs ORDER BY sumber")
    assert tersimpan == [(r["sumber"], "berhasil", r["baris_dimuat"]) for r in runs]


def test_isi_baris_run(akar, db):
    (r,) = run.jalankan(["tokopedia"], TANGGAL, TL, akar, db)

    assert len(r["run_id"]) == 36                       # UUID4 dengan tanda hubung
    assert r["tanggal"] == TANGGAL
    assert isinstance(r["mulai"], datetime) and r["mulai"] <= r["selesai"]
    assert r["pesan_galat"] is None
    assert set(r) == set(duckdb_loader.KOLOM_RUN)


def test_jalan_dua_kali_hasil_sama(akar, db):
    run.jalankan(KEDUANYA, TANGGAL, TL, akar, db)
    sekali = jumlah_tabel(db)
    run.jalankan(KEDUANYA, TANGGAL, TL, akar, db)
    dua_kali = jumlah_tabel(db)

    assert dua_kali.pop("pipeline_runs") == 4           # setiap run tetap dicatat
    sekali.pop("pipeline_runs")
    assert dua_kali == sekali


def test_extract_gagal_tidak_memuat_apa_pun(akar, db):
    # mentah lama dari fixture masih ada di folder, tetapi tidak boleh dimuat
    penarik = {"blibli": penarik_palsu(HasilTarik(0, "gagal", "diblokir"))}
    (r,) = run.jalankan(["blibli"], TANGGAL, {"extract", "transform", "load"}, akar, db, penarik)

    assert r["status"] == "gagal"
    assert r["pesan_galat"] == "diblokir"
    assert fakta(db, "blibli") == 0
    assert baca(db, "SELECT status FROM pipeline_runs") == [("gagal",)]


def test_extract_sebagian_tetap_dimuat(akar, db):
    penarik = {"tokopedia": penarik_palsu(HasilTarik(2, "sebagian", "halaman 3: diblokir"))}
    (r,) = run.jalankan(["tokopedia"], TANGGAL, {"extract", "transform", "load"}, akar, db, penarik)

    assert r["status"] == "sebagian"
    assert r["halaman_ditarik"] == 2
    assert r["pesan_galat"] == "halaman 3: diblokir"
    assert fakta(db, "tokopedia") == r["baris_dimuat"] > 0


def folder_mentah(akar: Path, sumber: str) -> Path:
    return akar / "raw" / sumber / f"date={TANGGAL:%Y-%m-%d}"


def test_extract_dilewati_kalau_sudah_sukses(akar, db):
    # siapkan_folder menghapus folder tanggal itu, jadi tarikan yang sudah sukses tidak boleh ditimpa
    (folder_mentah(akar, "blibli") / "_SUKSES").touch()
    sebelum = sorted(p.name for p in folder_mentah(akar, "blibli").rglob("*"))

    def tidak_boleh_dipanggil(tanggal, akar):
        raise AssertionError("penarik dipanggil padahal tanggal ini sudah sukses")

    (r,) = run.jalankan(["blibli"], TANGGAL, {"extract", "transform", "load"}, akar, db,
                        {"blibli": tidak_boleh_dipanggil})

    assert r["status"] == "berhasil", r["pesan_galat"]
    assert r["halaman_ditarik"] == 0
    assert fakta(db, "blibli") == r["baris_dimuat"] > 0
    assert sorted(p.name for p in folder_mentah(akar, "blibli").rglob("*")) == sebelum


def test_extract_berhasil_menulis_penanda(akar, db):
    penarik = {"tokopedia": penarik_palsu(HasilTarik(100, "berhasil"))}
    run.jalankan(["tokopedia"], TANGGAL, {"extract", "transform", "load"}, akar, db, penarik)

    assert (folder_mentah(akar, "tokopedia") / "_SUKSES").exists()


def test_extract_sebagian_tanpa_penanda(akar, db):
    # tanpa penanda, tarik_harian.py masih boleh mencoba lagi hari itu
    penarik = {"tokopedia": penarik_palsu(HasilTarik(2, "sebagian", "halaman 3: diblokir"))}
    run.jalankan(["tokopedia"], TANGGAL, {"extract", "transform", "load"}, akar, db, penarik)

    assert not (folder_mentah(akar, "tokopedia") / "_SUKSES").exists()


def test_penarik_melempar_galat_dicatat_gagal(akar, db):
    def meledak(tanggal, akar):
        raise RuntimeError("koneksi putus")

    (r,) = run.jalankan(["blibli"], TANGGAL, {"extract", "transform", "load"}, akar, db,
                        {"blibli": meledak})

    assert r["status"] == "gagal"
    assert "koneksi putus" in r["pesan_galat"]
    assert fakta(db, "blibli") == 0


def test_satu_sumber_gagal_sumber_lain_jalan(akar, db):
    shutil.rmtree(akar / "raw" / "blibli")              # Blibli tidak punya data mentah

    blibli, tokopedia = run.jalankan(KEDUANYA, TANGGAL, TL, akar, db)

    assert blibli["status"] == "gagal" and blibli["pesan_galat"]
    assert tokopedia["status"] == "berhasil"
    assert fakta(db, "tokopedia") == tokopedia["baris_dimuat"] > 0
    assert baca(db, "SELECT count(*) FROM pipeline_runs")[0][0] == 2


def ubah_harga_tokopedia(akar: Path, harga: dict[str, int]) -> None:
    """Ganti `price.number` kartu tertentu di mentah Tokopedia yang sudah disalin."""
    for berkas in (akar / "raw" / "tokopedia" / f"date={TANGGAL:%Y-%m-%d}").glob("page_*.json"):
        isi = json.loads(berkas.read_text(encoding="utf-8"))
        for p in isi[0]["data"]["searchProductV5"]["data"]["products"]:
            if str(p["id"]) in harga:
                p["price"]["number"] = harga[str(p["id"])]
        berkas.write_text(json.dumps(isi), encoding="utf-8")


PIR_1KG, JERUK_1KG = "869816887", "2652345561"


def test_karantina_lapisan1_dan_fakta_tidak_dimuat(akar, db):
    # harga 0 → gagal lapisan 1; Rp1.000 untuk 1 kg → lolos lapisan 1, gagal SkemaFakta (harga_per_kg)
    ubah_harga_tokopedia(akar, {PIR_1KG: 0, JERUK_1KG: 1_000})

    (r,) = run.jalankan(["tokopedia"], TANGGAL, TL, akar, db)

    assert r["status"] == "berhasil"
    assert r["baris_karantina"] == 2
    assert r["baris_dimuat"] + r["baris_karantina"] == r["baris_mentah"]
    assert fakta(db, "tokopedia") == r["baris_dimuat"]
    dikarantina = baca(db, "SELECT produk_id, alasan FROM produk_karantina ORDER BY alasan")
    assert [a.split(":")[0] for _, a in dikarantina] == ["harga", "harga_per_kg"]
    assert dikarantina[0][0] == PIR_1KG
    dimuat = {k for (k,) in baca(db, "SELECT item_sku FROM fakta_harga")}
    assert PIR_1KG not in dimuat and JERUK_1KG not in dimuat
    assert JERUK_1KG in {k for (k,) in baca(db, "SELECT produk_id FROM tokopedia_produk")}


def test_transform_saja_tidak_memuat(akar, db):
    (r,) = run.jalankan(["blibli"], TANGGAL, {"transform"}, akar, db)

    assert r["status"] == "berhasil"
    assert r["baris_dimuat"] + r["baris_karantina"] == r["baris_mentah"] > 0
    assert fakta(db, "blibli") == 0
    assert baca(db, "SELECT count(*) FROM pipeline_runs")[0][0] == 1


def test_load_tanpa_transform_ditolak(akar, db):
    with pytest.raises(ValueError, match="transform"):
        run.jalankan(KEDUANYA, TANGGAL, {"load"}, akar, db)


def test_log_satu_berkas_per_run(akar, db, tmp_path):
    folder_log = tmp_path / "logs"
    runs = run.jalankan(KEDUANYA, TANGGAL, TL, akar, db, folder_log=folder_log)

    for r in runs:
        isi = (folder_log / f"run_{r['run_id']}.log").read_text(encoding="utf-8")
        assert r["sumber"] in isi and "berhasil" in isi


def test_baca_argumen():
    a = run.baca_argumen(["--sumber", "tokopedia", "--tanggal", "2026-11-08",
                          "--tahap", "transform,load", "--akar", "x", "--db", "y.duckdb"])

    assert a.sumber == ["tokopedia"]
    assert a.tanggal == TANGGAL
    assert a.tahap == {"transform", "load"}
    assert a.akar == Path("x") and a.db == Path("y.duckdb")


def test_baca_argumen_bawaan():
    a = run.baca_argumen([])

    assert a.sumber == KEDUANYA
    assert a.tanggal is None                            # None = hari ini + tanggal tertinggal
    assert a.tahap == {"extract", "transform", "load"}


def test_baca_argumen_menolak_nilai_asing():
    with pytest.raises(SystemExit):
        run.baca_argumen(["--sumber", "shopee"])
    with pytest.raises(SystemExit):
        run.baca_argumen(["--tahap", "transform,muat"])


def test_cli_bantuan():
    hasil = subprocess.run([sys.executable, "run.py", "--help"], cwd=DASAR,
                           capture_output=True, text=True)

    assert hasil.returncode == 0
    assert "--tahap" in hasil.stdout


# --- 11 Nov 2026: folder kosong tercatat berhasil, cadangan VPS tidak pernah dimuat ---

def salin_ke_vps(tmp_path: Path, sumber: str, tanpa_varian: bool = False) -> Path:
    """Salinan fixture di data_lake_vps/, bertanda _SUKSES seperti hasil sinkron_vps.py."""
    akar_vps = tmp_path / "data_lake_vps"
    tujuan = akar_vps / "raw" / sumber / f"date={TANGGAL:%Y-%m-%d}"
    shutil.copytree(FIXTURE / sumber / f"date={TANGGAL:%Y-%m-%d}", tujuan)
    if tanpa_varian:
        shutil.rmtree(tujuan / run.SUB_VARIAN[sumber])
    (tujuan / "_SUKSES").touch()
    return akar_vps


def test_mentah_kosong_dicatat_gagal(akar, db):
    # 11 Nov: tarikan Blibli gagal (DNS) setelah folder dibuat → folder kosong, dulu tercatat "berhasil"
    shutil.rmtree(folder_mentah(akar, "blibli"))
    folder_mentah(akar, "blibli").mkdir()

    (r,) = run.jalankan(["blibli"], TANGGAL, TL, akar, db)

    assert r["status"] == "gagal"
    assert "kosong" in r["pesan_galat"]
    assert fakta(db, "blibli") == 0


def test_cadangan_vps_dipakai_kalau_laptop_tidak_sukses(akar, db, tmp_path):
    shutil.rmtree(folder_mentah(akar, "tokopedia"))     # tarikan laptop gagal sebelum folder dibuat
    akar_vps = salin_ke_vps(tmp_path, "tokopedia", tanpa_varian=True)

    (r,) = run.jalankan(["tokopedia"], TANGGAL, TL, akar, db, akar_vps=akar_vps)

    assert r["status"] == "sebagian"                    # VPS tidak menarik halaman varian
    assert "data_lake_vps" in r["pesan_galat"]
    assert fakta(db, "tokopedia") == r["baris_dimuat"] > 0


def test_laptop_sukses_didahulukan_atas_vps(akar, db, tmp_path):
    (folder_mentah(akar, "tokopedia") / "_SUKSES").touch()
    akar_vps = salin_ke_vps(tmp_path, "tokopedia", tanpa_varian=True)

    (r,) = run.jalankan(["tokopedia"], TANGGAL, TL, akar, db, akar_vps=akar_vps)

    assert r["status"] == "berhasil"
    assert r["pesan_galat"] is None


def test_harian_memuat_tanggal_tertinggal(akar, db, tmp_path):
    # tokopedia TANGGAL hanya ada di VPS dan belum pernah dimuat; besoknya run terjadwal harus menyusulkannya
    shutil.rmtree(folder_mentah(akar, "tokopedia"))
    (folder_mentah(akar, "blibli") / "_SUKSES").touch()
    akar_vps = salin_ke_vps(tmp_path, "tokopedia")
    besok = TANGGAL + timedelta(days=1)
    mulai = {"blibli": TANGGAL, "tokopedia": TANGGAL}

    assert run.tanggal_tertinggal(db, KEDUANYA, besok, akar, akar_vps, mulai) == [
        (TANGGAL, "blibli"), (TANGGAL, "tokopedia")]

    runs = run.jalankan_harian(KEDUANYA, besok, TL, akar, db, akar_vps=akar_vps, mulai=mulai)

    dimuat = {(r["tanggal"], r["sumber"]) for r in runs if r["baris_dimuat"] > 0}
    assert dimuat == {(TANGGAL, "blibli"), (TANGGAL, "tokopedia")}
    assert {(r["tanggal"], r["status"]) for r in runs if r["tanggal"] == besok} == {(besok, "gagal")}
    assert run.tanggal_tertinggal(db, KEDUANYA, besok, akar, akar_vps, mulai) == []


def test_tanggal_tertinggal_tidak_sebelum_mulai_gudang(akar, db, tmp_path):
    # tanggal sebelum batas gudang (keputusan 9 Nov: hanya tanggal lengkap) tidak boleh disusulkan
    (folder_mentah(akar, "blibli") / "_SUKSES").touch()
    mulai = {"blibli": TANGGAL + timedelta(days=1), "tokopedia": TANGGAL}

    assert run.tanggal_tertinggal(db, ["blibli"], TANGGAL + timedelta(days=3), akar, None, mulai) == []


# --- 16 Nov 2026: tarikan laptop putus di halaman 68, salinan VPS lengkap datang besoknya tapi tidak dimuat ---

def test_harian_memuat_ulang_dari_vps_kalau_yang_dimuat_tarikan_laptop_sebagian(akar, db, tmp_path):
    # Hari itu: folder laptop tanpa _SUKSES (tarikan putus) tetap dimuat, salinan VPS belum ada.
    (folder_mentah(akar, "blibli") / "_SUKSES").touch()
    (pertama,) = run.jalankan(["tokopedia"], TANGGAL, TL, akar, db, akar_vps=tmp_path / "data_lake_vps")
    assert pertama["pesan_galat"] is None and pertama["baris_dimuat"] > 0
    # Besoknya sinkron_vps.py membawa salinan VPS yang lengkap.
    akar_vps = salin_ke_vps(tmp_path, "tokopedia")
    besok = TANGGAL + timedelta(days=1)
    mulai = {"blibli": TANGGAL, "tokopedia": TANGGAL}
    run.jalankan(["blibli"], TANGGAL, TL, akar, db)

    assert run.tanggal_tertinggal(db, KEDUANYA, besok, akar, akar_vps, mulai) == [(TANGGAL, "tokopedia")]

    runs = run.jalankan_harian(KEDUANYA, besok, TL, akar, db, akar_vps=akar_vps, mulai=mulai)

    (susulan,) = [r for r in runs if r["tanggal"] == TANGGAL]
    assert "data_lake_vps" in susulan["pesan_galat"]
    assert run.tanggal_tertinggal(db, KEDUANYA, besok, akar, akar_vps, mulai) == []


def test_tanggal_manual_memakai_salinan_vps(monkeypatch):
    # `python run.py --tanggal X` dulu tidak pernah melihat data_lake_vps/
    dipanggil = {}
    monkeypatch.setattr(run, "jalankan", lambda *a, **k: dipanggil.update(k) or [])
    monkeypatch.setattr(sys, "argv", ["run.py", "--tahap", "transform,load", "--tanggal", "2026-11-16"])

    assert run.main() == 0
    assert dipanggil["akar_vps"] == run.AKAR_VPS
