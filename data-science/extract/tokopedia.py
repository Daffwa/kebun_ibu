import json
import time
import urllib.parse
from datetime import date
from functools import partial
from pathlib import Path
from typing import Callable


from curl_cffi import requests

from transform.parser import mangga_manalagi

from extract.http import (
    AmbilGagal,
    HasilTarik,
    KesalahanSementara,
    ambil_dengan_coba_ulang,
    jeda_sopan,
    siapkan_folder,
    simpan_json,
)

URL = "https://gql.tokopedia.com/graphql/SearchProductV5Query"

PARAM_DASAR = {
    "source": "directory",
    "identifier": "makanan-minuman_buah_buah-buahan",
    "sc": 2705,
    "q": "",
    "rows": 60,
    "ob": 23,
    "device": "desktop",
    "st": "product",
    "safe_search": "false",
    "user_id": 0,
    "related": "true",
}

HALAMAN_MAKS = 100

KEPALA = {
    "Content-Type": "application/json",
    "Origin": "https://www.tokopedia.com",
    "Referer": "https://www.tokopedia.com/p/makanan-minuman/buah/buah-buahan",
    "X-Source": "tokopedia-lite",
    "X-Tkpd-Lite-Service": "zeus",
    "X-Device": "desktop-0.0",
    
}

QUERY = """ 
query SearchProductV5Query($params: String!) {
    searchProductV5(params: $params) {
        header { totalData }
        data{
            products {
                id name url
                price { number original discountPercentage }
                shop { id name city tier }
                category { breadcrumb }
                rating
                labelGroups { position title }
            }
        }
    }
}
"""

def buat_sesi() -> requests.Session:
    sesi = requests.Session(impersonate="chrome")
    sesi.get("https://www.tokopedia.com/", timeout=60)
    return sesi

def ambil_halaman_http(sesi: requests.Session, halaman: int) -> list:
    param = dict(PARAM_DASAR, page=halaman, start=(halaman - 1) * PARAM_DASAR["rows"])
    badan = [
        {
            "operationName": "SearchProductV5Query",
            "variables": {"params": urllib.parse.urlencode(param)},
            "query":QUERY,
        }
    ]
    try:
        jawaban = sesi.post(URL, json=badan, headers=KEPALA, timeout=60)
        
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as galat:
        raise KesalahanSementara(str(galat)) from galat
    
    if jawaban.status_code == 429 or jawaban.status_code >= 500:
        raise KesalahanSementara(f"HTTP {jawaban.status_code}")
    jawaban.raise_for_status()
    
    isi = jawaban.json()
    if isi[0].get("errors"):
        pesan = "; ".join(e.get("message", "?") for e in isi[0]["errors"])
        raise RuntimeError(f"GraphQL Tokopedia: {pesan}")
    return isi

def produk_dari_jawaban(jawaban: list) -> list[dict]:
    return jawaban[0]["data"]["searchProductV5"]["data"]["products"] or []


# ---- Halaman produk Mangga Manalagi (spec 4.2, keputusan 13 #11 = a) ----

PENANDA_CACHE = "window.__cache="


def cache_dari_html(teks: str) -> dict:
    """HTML halaman produk -> JSON `window.__cache`.

    Tokopedia kadang mengirim halaman kosong (tanpa cache, atau cache tanpa
    `pdpBasicInfo`); itu dianggap KesalahanSementara supaya dicoba ulang.
    """
    if PENANDA_CACHE not in teks:
        raise KesalahanSementara("halaman produk kosong (tanpa window.__cache)")
    awal = teks.index(PENANDA_CACHE) + len(PENANDA_CACHE)
    cache, _ = json.JSONDecoder().raw_decode(teks[awal:])
    if not any(isinstance(v, dict) and v.get("__typename") == "pdpBasicInfo" for v in cache.values()):
        raise KesalahanSementara("halaman produk kosong (tanpa pdpBasicInfo)")
    return cache


def ambil_produk_http(url: str) -> dict:
    """Satu halaman produk dengan sesi baru (sesi lama sering terus dapat halaman kosong)."""
    try:
        jawaban = buat_sesi().get(url, timeout=60)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as galat:
        raise KesalahanSementara(str(galat)) from galat
    if jawaban.status_code == 429 or jawaban.status_code >= 500:
        raise KesalahanSementara(f"HTTP {jawaban.status_code}")
    jawaban.raise_for_status()
    return cache_dari_html(jawaban.text)


def tarik_halaman_produk(
    folder: Path,
    produk: dict[str, str],
    ambil_produk: Callable[[str], dict],
    tidur: Callable[[float], None],
) -> tuple[int, int]:
    """Simpan halaman produk ke `folder/halaman/<id>.json`. `produk` = {id: url}.
    Mengembalikan (jumlah berhasil, jumlah gagal)."""
    folder_halaman = folder / "halaman"
    folder_halaman.mkdir(exist_ok=True)
    berhasil = gagal = 0
    for id_, url in produk.items():
        try:
            cache = ambil_dengan_coba_ulang(lambda: ambil_produk(url), tidur=tidur)
            simpan_json(folder_halaman, f"{id_}.json", cache)
            berhasil += 1
        except (AmbilGagal, requests.exceptions.HTTPError):
            gagal += 1
        jeda_sopan(tidur)
    return berhasil, gagal


def tarik(
    tanggal: date,
    akar: Path,
    ambil_halaman: Callable[[int], list] | None = None,
    ambil_produk: Callable[[str], dict] = ambil_produk_http,
    tidur: Callable[[float], None] = time.sleep,
) -> HasilTarik:
    if ambil_halaman is None:
        ambil_halaman = partial(ambil_halaman_http, buat_sesi())

    folder = siapkan_folder(akar, "tokopedia", tanggal)
    jumlah = 0
    manalagi: dict[str, str] = {}

    for n in range(1, HALAMAN_MAKS + 1):
        try:
            jawaban = ambil_dengan_coba_ulang(lambda: ambil_halaman(n), tidur=tidur)
        except AmbilGagal as galat:
            status = "gagal" if jumlah == 0 else "sebagian"
            return HasilTarik(jumlah, status, f"halaman {n}: {galat}")

        produk = produk_dari_jawaban(jawaban)
        if not produk:
            break

        simpan_json(folder, f"page_{n:03d}.json", jawaban)
        jumlah += 1
        for p in produk:
            if mangga_manalagi(p.get("name")):
                manalagi.setdefault(str(p["id"]), p["url"].split("?")[0])
        jeda_sopan(tidur)

    if not manalagi:
        return HasilTarik(jumlah, "berhasil")
    berhasil, gagal = tarik_halaman_produk(folder, manalagi, ambil_produk, tidur)
    status = "sebagian" if berhasil == 0 else "berhasil"
    return HasilTarik(jumlah, status, f"halaman produk: {berhasil}, {gagal} gagal")
