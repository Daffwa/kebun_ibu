# Catatan Scraping: Cara yang Berhasil dan Kelemahan VPS — 7 November 2026

Hasil uji langsung, bukan tebakan. Pakai catatan ini sebelum menambah
penarik baru atau memindahkan penarik ke server.

## 1. Ringkasan

| Cara mengambil halaman | Laptop | VPS (DomaiNesia, Jakarta) |
|---|---|---|
| `curl_cffi` (`impersonate="chrome"`) | ✅ | ✅ (Tokopedia) |
| `requests` biasa (tanpa sidik jari Chrome) | belum diuji | ❌ Tokopedia tidak menjawab (timeout 3/3) |
| Selenium + Chrome headless | belum diuji | ❌ Tokopedia: "This site can't be reached" 3/3 |

**Yang dipakai: `curl_cffi` untuk mengambil, lalu `json` (atau
BeautifulSoup) untuk membaca.** BeautifulSoup hanya membaca HTML; ia
tidak mengambil halaman. Jadi BeautifulSoup jalan di mana saja. Yang
menentukan berhasil atau tidak adalah **cara mengambil**.

## 2. Per situs

| Situs | Data | Laptop | VPS |
|---|---|---|---|
| Blibli | hasil cari (`/backend/search/products`) | ✅ | ❌ HTTP 403 Cloudflare: IP pusat data diblokir, sejak 27 Okt |
| Blibli | opsi varian (`/backend/product-detail/products/ps--<id>/_summary`, `is--<itemSku>/_summary`) | ✅ | tidak diuji (situsnya sudah memblokir VPS) |
| Tokopedia | hasil cari (GraphQL `SearchProductV5Query`) | ✅ | ✅ |
| Tokopedia | halaman produk (HTML, data di `window.__cache`) | ✅ | ✅ |

## 3. Halaman produk Tokopedia

- Data ada di HTML sebagai JSON `window.__cache=…`. **Tidak perlu
  browser.** Isinya: berat + satuan, stok, harga + harga coret,
  jumlah terjual pasti, jumlah rating, kampanye, `isVariant`/`parentID`.
- **Kadang kosong:** halaman ±22 KB dengan `__cache` kosong (normalnya
  ±200 KB). Acak, bukan per produk. Coba ulang sampai 3 kali dengan jeda
  6 detik: 22/22 berhasil pada uji 7 Nov.
- Makin banyak permintaan dalam sehari, makin sering kosong. Jaga jumlah
  halaman per hari kecil (misalnya hanya Mangga Manalagi, ±23 produk).
- Berat diisi penjual, bisa salah (contoh: "1KG" tertulis 0,01 kg).
  Pakai sebagai cadangan, bukan pengganti berat dari nama.

## 4. Kelemahan VPS (Cloud VPS Lite 1 GB, Ubuntu 26.04)

| Kelemahan | Akibat |
|---|---|
| RAM 956 MB, tanpa swap, ±510 MB bebas | Chrome headless memakai ±560 MB saat jalan: hampir habis |
| `/tmp` adalah tmpfs (RAM) 479 MB | Unduhan besar ke `/tmp` gagal "No space left on device". Pakai `TMPDIR` di disk |
| Tidak ada pustaka browser (libnss3, libgbm1, libcairo2, …) | Selenium butuh 14 paket + 32 dependensi dari `apt` |
| IP pusat data | Blibli memblokir; Tokopedia masih menerima (dengan `curl_cffi`) |
| 1 CPU | Chrome mulai 5,8 detik, satu halaman ±6 detik |

## 5. Bersih-bersih

Semua sisa uji Selenium sudah dihapus dari VPS pada 7 Nov: folder
`/root/uji_scrape`, cache Chrome `/root/.cache/selenium` (431 MB), dan
46 paket `apt` yang dipasang untuk uji itu. `/root/kebun-ibu` dan cron
tidak berubah.

Uji Selenium dengan user agent Chrome biasa (bukan `HeadlessChrome`)
**tidak dijalankan**: diblokir oleh pemeriksaan izin Claude Code karena
termasuk mengakali deteksi bot.
