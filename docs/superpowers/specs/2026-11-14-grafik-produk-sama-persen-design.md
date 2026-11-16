# Grafik "produk yang sama" dalam persen (desain singkat)

> **16 Nov 2026: pengguna mengganti pilihan ke A (ganti kata saja).** Grafik tetap rupiah. Judul jadi
> "Median {tanggal terakhir}: Rp X · produk yang sama berubah ±x,x% sejak {tanggal pertama}", legenda biru
> "Produk yang sama (ujung = median terakhir)", keterangan menjelaskan garis biru bukan harga satu produk.
> Notebook ikut (Grafik 3 dikembalikan ke rupiah dengan kata yang sama). Desain B di bawah tidak dibangun;
> rencana `docs/superpowers/plans/2026-11-14-grafik-produk-sama-persen.md` dibatalkan.

Tanggal: 14 Nov 2026. Halaman: `/admin/pasar` (grafik 3) dan notebook `dashboard_contoh.ipynb` (Grafik 3).

## Maksud

Judul sekarang "Harga per kg produk yang sama: Rp 30.000, 0,0% sejak 7 Nov" menyesatkan: Rp 30.000
terbaca sebagai harga produk yang sama (atau rata-rata 7–14 Nov), padahal itu median hari terakhir
tempat garis biru dipaku. Pertanyaan grafik ini adalah "harga benar-benar berubah, atau campuran
produknya yang berubah?" — pertanyaan persen, bukan rupiah. Harga rupiah sudah ada di angka utama
dan grafik sebaran di atasnya.

## Pendekatan (dipilih pengguna: B)

| | Cara | Untung / rugi |
|---|---|---|
| A. Ganti kata saja | Judul "Median 14 Nov: Rp 30.000 · produk yang sama berubah 0,0%". | Murah; garis biru tetap rupiah yang bukan harga nyata. |
| **B. Persen sejak titik pertama** ✅ | Kedua garis mulai 0% di titik pertama. | Tidak ada angka rupiah karangan; jarak dua garis = pengaruh campuran produk. |
| C. Garis biru dipaku ke hari pertama | Biru mulai di median 7 Nov. | Tetap rupiah, tapi ujungnya juga bukan harga nyata. |

## Keputusan

- **Titik dasar:** titik (hari atau bulan) pertama dalam rentang yang punya `indeks_berantai` **dan**
  `median`. Kedua garis diukur dari titik yang sama itu:
  - produk yang sama = `indeks_berantai / indeks_berantai_dasar − 1`
  - semua produk = `median / median_dasar − 1`
  - Titik sebelum titik dasar dan titik tanpa data = kosong (garis putus, seperti sekarang).
- **Judul:** "Perubahan harga sejak {tanggal dasar}: produk yang sama {±x,x%}, semua produk {±x,x%}"
  (nilai titik terakhir yang punya keduanya). Kurang dari 2 titik berdata: judul "Perubahan harga"
  saja, tanpa angka.
- **Sumbu y:** persen ("+10%", "0%", "−5%"), garis 0% ditebalkan; batas atas/bawah simetris di sekitar
  0 dengan ruang secukupnya (*panggilan saya*).
- **Tooltip:** "Produk yang sama +0,0%", "Semua produk +16,0% (median Rp 30.000)" — rupiah hanya
  untuk median, karena itu harga nyata.
- **Legenda:** "Produk yang sama", "Semua produk (median)". Warna tetap (biru, oranye).
- **Keterangan di bawah grafik:** "Garis biru hanya bergerak kalau produk yang sama berubah harga.
  Kalau garis oranye naik tapi biru datar, harga naik karena produk yang muncul berganti, bukan
  karena penjual menaikkan harga."
- `geserIndeks` dan `ringkasTren` (rupiah) diganti fungsi persen baru; yang lama dibuang bersama
  tesnya kalau tidak dipakai lagi.
- **Notebook:** Grafik 3 di `dashboard_contoh.ipynb` diubah dengan aturan yang sama, supaya notebook
  dan web tetap sama isinya.

## Bukan tujuan

- Tidak mengubah data (`indeks_berantai`, `median` di Supabase dan laptop tetap).
- Tidak mengubah grafik lain.

## Diserahkan ke pembangun

- Nama fungsi persen dan bentuk keluarannya.
- Pembulatan sumbu y.
