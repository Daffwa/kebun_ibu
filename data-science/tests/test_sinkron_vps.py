import subprocess

from sinkron_vps import jalankan, perlu_disalin, salin_folder, urai_daftar
from tarik_harian import PENANDA

KELUARAN_FIND = (
    "/root/kebun-ibu/data_lake/raw/tokopedia/date=2026-10-27/_SUKSES\n"
    "/root/kebun-ibu/data_lake/raw/tokopedia/date=2026-10-28/_SUKSES\n"
    "\n"
)


def scp_palsu(dipanggil=None):
    """Meniru scp -r: membuat folder tujuan berisi satu halaman dan penanda."""

    def scp(perintah, cwd, **_):
        tujuan = cwd / perintah[-1]
        if dipanggil is not None:
            dipanggil.append(perintah[-2])
        tujuan.mkdir()
        (tujuan / "page_001.json").write_text("{}")
        (tujuan / PENANDA).touch()

    return scp


def test_urai_daftar_mengambil_sumber_dan_folder():
    assert urai_daftar(KELUARAN_FIND) == [
        ("tokopedia", "date=2026-10-27"),
        ("tokopedia", "date=2026-10-28"),
    ]


def test_perlu_disalin_melewati_yang_sudah_lengkap_di_laptop(tmp_path):
    lengkap = tmp_path / "raw" / "tokopedia" / "date=2026-10-27"
    lengkap.mkdir(parents=True)
    (lengkap / PENANDA).touch()

    assert perlu_disalin(urai_daftar(KELUARAN_FIND), tmp_path) == [("tokopedia", "date=2026-10-28")]


def test_salin_folder_menaruh_hasil_di_tempat_akhir(tmp_path):
    dipanggil = []

    salin_folder("tokopedia", "date=2026-10-28", tmp_path, scp_palsu(dipanggil))

    akhir = tmp_path / "raw" / "tokopedia" / "date=2026-10-28"
    assert (akhir / PENANDA).exists()
    assert not (akhir.parent / "date=2026-10-28.sementara").exists()
    assert dipanggil == ["root@202.134.242.170:/root/kebun-ibu/data_lake/raw/tokopedia/date=2026-10-28"]


def test_salin_folder_mengganti_sisa_salinan_yang_terputus(tmp_path):
    sisa = tmp_path / "raw" / "tokopedia" / "date=2026-10-28"
    sisa.mkdir(parents=True)
    (sisa / "page_050.json").write_text("{}")

    salin_folder("tokopedia", "date=2026-10-28", tmp_path, scp_palsu())

    assert not (sisa / "page_050.json").exists()
    assert (sisa / PENANDA).exists()


def test_salin_gagal_tidak_meninggalkan_folder_akhir(tmp_path):
    def scp_putus(perintah, cwd, **_):
        (cwd / perintah[-1]).mkdir()
        raise subprocess.CalledProcessError(1, perintah)

    try:
        salin_folder("tokopedia", "date=2026-10-28", tmp_path, scp_putus)
    except subprocess.CalledProcessError:
        pass

    assert not (tmp_path / "raw" / "tokopedia" / "date=2026-10-28").exists()


def test_jalankan_menghitung_gagal_dan_lanjut_ke_folder_berikutnya(tmp_path):
    dipanggil = []

    def salin(sumber, folder, akar):
        dipanggil.append(folder)
        if folder == "date=2026-10-27":
            raise subprocess.CalledProcessError(1, ["scp"])

    gagal = jalankan(urai_daftar(KELUARAN_FIND), tmp_path, salin)

    assert gagal == 1
    assert dipanggil == ["date=2026-10-27", "date=2026-10-28"]
