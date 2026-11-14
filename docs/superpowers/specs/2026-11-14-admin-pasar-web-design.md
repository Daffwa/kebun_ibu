# Halaman `/admin/pasar` — desain web

Tanggal: 14 Nov 2026 · Melengkapi `2026-11-13-dashboard-manalagi-design.md` (aturan grafik, filter,
rumus, tabel Supabase). Dokumen ini hanya mengisi bagian yang khusus web.

## Tujuan

Ibuk membuka `/admin/pasar` di HP, melihat harga pasar Mangga Manalagi (grafik 1, 2, 3, 6), lalu
memutuskan apakah harga jualnya perlu diubah. Semua aturan grafik mengikuti dokumen desain 13 Nov;
prototipe acuannya `data-science/dashboard_contoh.ipynb` (Langkah 2).

**Bukan tujuan:** tren wilayah, riwayat harga Ibuk, mengubah harga Ibuk dari halaman, mode gelap
(situs ini hanya mode terang), unduh CSV.

**Gagal walau jalan:** angka di web berbeda dari notebook untuk data yang sama; tanggal bergeser
satu hari karena zona waktu; halaman diam-diam memotong data di 1000 baris.

## Pendekatan (dipilih pengguna 14 Nov: A)

| | Pendekatan | Untung | Rugi |
|---|---|---|---|
| **A** | **Recharts 3.10.1** | sumbu, tooltip, ukuran otomatis sudah ada; teman bisa mengubah gaya dari dokumentasinya; mendukung React 19 | satu dependensi; grafik dijalankan di browser |
| B | SVG tulis tangan | tanpa dependensi, kontrol penuh | ±2× kode untuk ditulis dan dipelajari |

## Alur

1. **Filter di URL** (`?pasar=semua|tokopedia|blibli&rentang=30h|1t|5t|semua|kustom&dari=&sampai=`),
   seperti saringan Kotak masuk. Tombol preset = tautan; Kustom = form GET dengan dua
   `<input type="date">` (min/maks = tanggal data). Jalan tanpa JavaScript.
2. **Server Component** `src/app/admin/pasar/page.tsx` membaca Supabase lewat `supabaseServer()`
   (sesi pengguna, RLS `is_pengelola()`), menghitung, lalu mengirim angka siap gambar ke komponen
   grafik.
3. **Komponen grafik** (`"use client"`, Recharts) hanya menggambar; tidak menghitung.

## Membaca data (batas 1000 baris)

Supabase mengembalikan **paling banyak 1000 baris per permintaan** (`max_rows = 1000`). 5 tahun
satu pasar ≈ 1.826 baris. Maka:

| Permintaan | Isi | Ukuran |
|---|---|---|
| batas data | `tanggal` pertama dan terakhir di `pasar_manalagi_harian` untuk pasar terpilih | 2 × 1 baris |
| deret | `pasar_manalagi_harian` pasar terpilih dalam rentang | dibaca per 1000 sampai habis |
| potret | `pasar_manalagi` pada hari berdata terakhir dalam rentang (+ `sumber` kalau bukan Semua) | ±30 baris hari ini; dibaca per 1000 juga (fungsi paging yang sama), karena setiap toko baru menambah baris per hari |
| tabel lonjakan | `pasar_manalagi` `lonjak_toko` dalam rentang, terbaru dulu, 20 baris + jumlah total | ≤ 20 baris |

Tidak perlu migrasi baru.

## Logika (`src/lib/pasar.ts`, fungsi murni, diuji vitest)

Port dari notebook: `statusPreset`, `rentangPreset`, `kerapatan`, `deret`, `angkaUtama`,
`histogram`, `geserIndeks`.

- **Tanggal = teks `YYYY-MM-DD`**, dihitung dengan UTC. Tidak ada `new Date()` lokal, jadi WIB/WITA
  tidak menggeser hari.
- **Tahun kalender** seperti `pd.DateOffset(years=n)`: 29 Feb + 1 tahun = 28 Feb.
- **Minggu** seperti pandas `W` (minggu berakhir hari Minggu, label = tanggal Minggu itu);
  **bulan** seperti `MS` (label = tanggal 1).
- **Uji silang dengan notebook**: skrip Python kecil mengekspor `harian` dan hasil `deret()` notebook
  untuk beberapa rentang (data asli + data sintetis 3 tahun) ke JSON; vitest memastikan hasil TS sama.

## Tampilan (satu kolom, HP dulu, lebar maks 3xl seperti halaman admin lain)

```
Pasar
Harga Mangga Manalagi di Blibli dan Tokopedia.
[Semua][Tokopedia][Blibli]
[30 hari][1 tahun][5 tahun][Semua][Kustom]   ← terkunci = abu-abu + alasan di bawahnya
Terkunci · 30 hari: terbuka setelah 30 hari data (sekarang 8/30)
Semua marketplace · 7 Nov – 14 Nov 2026 · 8 hari, 8 berdata · satu titik = 1 hari

┌ 14 Nov 2026 · 27 produk, 21 toko ────────────┐
│ Median Rp32.000  Rata-rata …  Tertimbang …   │  grafik 1 (kotak angka, HTML)
└──────────────────────────────────────────────┘
┌ Sebaran harga per kg ────────────────────────┐  grafik 2
┌ Harga per kg produk yang sama ───────────────┐  grafik 3
┌ Lonjakan harga ──────────────────────────────┐  grafik 6 (garis atas + batang bawah)
│ Toko yang melonjak (20 terbaru) — tabel      │
└──────────────────────────────────────────────┘
```

- Menu admin dapat tab **Pasar**.
- Warna = palet notebook (biru `#2a78d6`, oranye `#eb6834`, merah `#e34948`); lolos validator
  dataviz di mode terang. Teks memakai warna tinta situs, bukan warna seri.
- Tooltip saat disentuh/diarahkan di semua grafik. Label langsung hanya yang ada di notebook: garis
  median dan harga Ibuk (grafik 2), "Lonjakan pasar +x%" (grafik 6), jumlah naik/turun kalau ≤ 31 titik.
- `HARGA_IBUK = 30_000` di `src/lib/pasar.ts` dengan catatan "CONTOH" (keputusan 14 Nov).

## Keadaan kosong

- Belum ada data sama sekali untuk pasar terpilih: kotak putus-putus "Belum ada data …".
- Kustom dengan Dari sesudah Sampai: pesan "Rentang kosong", grafik tidak digambar.
- Preset terkunci di URL (misalnya `rentang=1t` sebelum setahun): jatuh ke Semua, seperti notebook.

## Keputusan saya (bisa dikoreksi)

1. Grafik 3 dan 6 tidak punya tabel data terpisah; tooltip + tabel lonjakan dianggap cukup.
2. Pesan kunci ditulis di bawah tombol (HP tidak punya hover untuk tooltip tombol).
3. Recharts dipasang dengan versi pasti `3.10.1`.

## Diserahkan ke pembuat

Ukuran huruf sumbu, jarak antar kartu, format tanggal sumbu untuk mingguan/bulanan.
