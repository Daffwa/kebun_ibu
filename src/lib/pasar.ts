/**
 * Dashboard harga Mangga Manalagi (/admin/pasar): saringan, kunci rentang, kerapatan titik.
 * Port dari Langkah 2 `data-science/dashboard_contoh.ipynb`; hasilnya diuji sama dengan notebook
 * lewat `pasar.fixture.json` (dibuat `data-science/ekspor_uji_web.py`).
 * Aturan: docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md.
 *
 * Tanggal selalu teks "YYYY-MM-DD" dan dihitung dengan UTC, jadi zona waktu server/HP
 * (WIB, WITA, UTC di Vercel) tidak pernah menggeser hari.
 */

// Parameter detektor lonjakan; hitungannya di laptop (data-science/dashboard_manalagi.py).
// Di sini hanya untuk teks dan pita grafik, jadi samakan kalau di sana diubah.
export const JENDELA_HARI = 7;
export const AMBANG_TOKO = 0.1;
export const AMBANG_PASAR = 0.05;

export type Pasar = "semua" | "blibli" | "tokopedia";
export type Preset = "30h" | "1t" | "5t";
export type Rentang = Preset | "semua" | "kustom";
export type Satuan = "hari" | "minggu" | "bulan";

/** Satu baris tabel `pasar_manalagi_harian`. */
export type HarianBaris = {
  tanggal: string;
  pasar: Pasar;
  jumlah_produk: number;
  median: number;
  indeks_berantai: number;
  median_rasio: number | null;
  lonjak_pasar: boolean;
  naik: number;
  turun: number;
};

/** Satu titik grafik tren: satu hari, minggu, atau bulan. null = tidak ada data. */
export type Titik = {
  tanggal: string;
  jumlah_produk: number | null;
  median: number | null;
  indeks_berantai: number | null;
  median_rasio: number | null;
  naik: number | null;
  turun: number | null;
  lonjak_pasar: 0 | 1 | null;
  berdata: number;
};

export type Filter = { pasar: Pasar; rentang: Rentang; dari: string | null; sampai: string | null };

export const NAMA_PASAR: Record<Pasar, string> = {
  semua: "Semua marketplace",
  tokopedia: "Tokopedia",
  blibli: "Blibli",
};

export const NAMA_RENTANG: Record<Rentang, string> = {
  "30h": "30 hari",
  "1t": "1 tahun",
  "5t": "5 tahun",
  semua: "Semua",
  kustom: "Kustom",
};

const PRESET: Preset[] = ["30h", "1t", "5t"];
const HARI_MS = 86_400_000;

// ---------------------------------------------------------------- tanggal

function urai(t: string): [number, number, number] {
  return [Number(t.slice(0, 4)), Number(t.slice(5, 7)), Number(t.slice(8, 10))];
}

function tulis(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

function ms(t: string): number {
  const [y, m, d] = urai(t);
  return Date.UTC(y, m - 1, d);
}

export function tambahHari(t: string, n: number): string {
  const [y, m, d] = urai(t);
  return tulis(Date.UTC(y, m - 1, d + n));
}

/** Seperti `pd.DateOffset(years=n)`: tanggal yang tidak ada (29 Feb) dijepit ke akhir bulan. */
export function tambahTahun(t: string, n: number): string {
  const [y, m, d] = urai(t);
  const akhirBulan = new Date(Date.UTC(y + n, m, 0)).getUTCDate();
  return tulis(Date.UTC(y + n, m - 1, Math.min(d, akhirBulan)));
}

/** sampai − dari, dalam hari. */
export function selisihHari(dari: string, sampai: string): number {
  return Math.round((ms(sampai) - ms(dari)) / HARI_MS);
}

function tanggalSah(t: unknown): t is string {
  return typeof t === "string" && /^\d{4}-\d{2}-\d{2}$/.test(t) && tambahHari(t, 0) === t;
}

const maks = (a: string, b: string) => (a > b ? a : b);
const min = (a: string, b: string) => (a < b ? a : b);

// ---------------------------------------------------------------- saringan dan rentang

export function bacaFilter(sp: Record<string, string | string[] | undefined>): Filter {
  const pasar = sp.pasar;
  const rentang = sp.rentang;
  return {
    pasar: pasar === "blibli" || pasar === "tokopedia" ? pasar : "semua",
    rentang: typeof rentang === "string" && rentang in NAMA_RENTANG ? (rentang as Rentang) : "semua",
    dari: tanggalSah(sp.dari) ? sp.dari : null,
    sampai: tanggalSah(sp.sampai) ? sp.sampai : null,
  };
}

/** Tanggal `t` digeser sejauh panjang preset (n = 1 maju, −1 mundur). */
function geserPreset(t: string, p: Preset, n: 1 | -1): string {
  if (p === "30h") return tambahHari(t, 30 * n);
  return tambahTahun(t, (p === "1t" ? 1 : 5) * n);
}

/** Preset terkunci kalau data marketplace terpilih lebih pendek dari preset (tahun kalender). */
export function statusPreset(awal: string, akhir: string): Record<Preset, { terbuka: boolean; pesan: string }> {
  const ada = selisihHari(awal, akhir) + 1;
  const hasil = {} as Record<Preset, { terbuka: boolean; pesan: string }>;
  for (const p of PRESET) {
    const perlu = selisihHari(awal, geserPreset(awal, p, 1));
    const terbuka = ada >= perlu;
    hasil[p] = {
      terbuka,
      pesan: terbuka ? "" : `${NAMA_RENTANG[p]}: terbuka setelah ${perlu} hari data (sekarang ${ada}/${perlu})`,
    };
  }
  return hasil;
}

export function rentangPreset(awal: string, akhir: string, r: Preset | "semua"): [string, string] {
  if (r === "semua") return [awal, akhir];
  return [maks(awal, tambahHari(geserPreset(akhir, r, -1), 1)), akhir];
}

/** Rentang yang benar-benar digambar. Preset terkunci jatuh ke Semua; Kustom dijepit ke tanggal data. */
export function pilihRentang(
  f: Filter,
  awal: string,
  akhir: string,
): { rentang: Rentang; mulai: string; akhir: string } | { rentang: "kustom"; kosong: "terbalik" | "diluar" } {
  if (f.rentang === "kustom") {
    // "terbalik" = pengguna memilih Dari sesudah Sampai; "diluar" = rentangnya tidak menyentuh data
    // pasar ini (misalnya pindah dari Blibli ke Tokopedia yang mulai sehari kemudian).
    if (f.dari && f.sampai && f.dari > f.sampai) return { rentang: "kustom", kosong: "terbalik" };
    const mulai = maks(f.dari ?? awal, awal);
    const sampai = min(f.sampai ?? akhir, akhir);
    if (mulai > sampai) return { rentang: "kustom", kosong: "diluar" };
    return { rentang: "kustom", mulai, akhir: sampai };
  }
  const rentang = f.rentang !== "semua" && !statusPreset(awal, akhir)[f.rentang].terbuka ? "semua" : f.rentang;
  const [mulai, sampai] = rentangPreset(awal, akhir, rentang);
  return { rentang, mulai, akhir: sampai };
}

// ---------------------------------------------------------------- kerapatan dan deret

export function kerapatan(mulai: string, akhir: string): Satuan {
  if (selisihHari(mulai, akhir) + 1 <= 90) return "hari";
  if (tambahTahun(mulai, 2) > akhir) return "minggu";
  return "bulan";
}

function median(nilai: number[]): number | null {
  if (nilai.length === 0) return null;
  const urut = [...nilai].sort((a, b) => a - b);
  const tengah = Math.floor(urut.length / 2);
  return urut.length % 2 ? urut[tengah] : (urut[tengah - 1] + urut[tengah]) / 2;
}

/** Label periode: Minggu penutup minggunya (pandas "W") atau tanggal 1 bulannya (pandas "MS"). */
function labelPeriode(t: string, satuan: Exclude<Satuan, "hari">): string {
  if (satuan === "bulan") return `${t.slice(0, 7)}-01`;
  const hari = new Date(ms(t)).getUTCDay(); // 0 = Minggu
  return tambahHari(t, (7 - hari) % 7);
}

function langkahPeriode(t: string, satuan: Exclude<Satuan, "hari">): string {
  if (satuan === "minggu") return tambahHari(t, 7);
  const [y, m] = urai(t);
  return tulis(Date.UTC(y, m, 1));
}

function harianKeTitik(tanggal: string, h: HarianBaris | undefined): Titik {
  if (!h) {
    return {
      tanggal, jumlah_produk: null, median: null, indeks_berantai: null, median_rasio: null,
      naik: null, turun: null, lonjak_pasar: null, berdata: 0,
    };
  }
  return {
    tanggal,
    jumlah_produk: h.jumlah_produk,
    median: h.median,
    indeks_berantai: h.indeks_berantai,
    median_rasio: h.median_rasio,
    naik: h.naik,
    turun: h.turun,
    lonjak_pasar: h.lonjak_pasar ? 1 : 0,
    berdata: 1,
  };
}

function gabung(tanggal: string, hari: Titik[]): Titik {
  const ada = <K extends keyof Titik>(k: K) =>
    hari.map((t) => t[k]).filter((v): v is NonNullable<Titik[K]> => v !== null) as number[];
  const jumlah = (k: "naik" | "turun" | "berdata") => ada(k).reduce((a, b) => a + b, 0);
  const berdata = jumlah("berdata");
  const lonjak = ada("lonjak_pasar");
  return {
    tanggal,
    jumlah_produk: median(ada("jumlah_produk")),
    median: median(ada("median")),
    indeks_berantai: median(ada("indeks_berantai")),
    median_rasio: median(ada("median_rasio")),
    // Periode tanpa data: kosong, bukan 0, supaya tidak terbaca "tidak ada toko berubah".
    naik: berdata ? jumlah("naik") : null,
    turun: berdata ? jumlah("turun") : null,
    lonjak_pasar: berdata && lonjak.length ? (Math.max(...lonjak) as 0 | 1) : null,
    berdata,
  };
}

/**
 * Titik grafik tren untuk rentang [mulai, akhir]. `harian` sudah disaring ke satu pasar.
 * Hari tanpa data tetap ada sebagai titik kosong (garis putus, tidak disambung).
 */
export function deret(harian: HarianBaris[], mulai: string, akhir: string): { titik: Titik[]; satuan: Satuan } {
  const perTanggal = new Map(harian.map((h) => [h.tanggal, h]));
  const hari: Titik[] = [];
  for (let t = mulai; t <= akhir; t = tambahHari(t, 1)) hari.push(harianKeTitik(t, perTanggal.get(t)));

  const satuan = kerapatan(mulai, akhir);
  if (satuan === "hari") return { titik: hari, satuan };

  const kelompok = new Map<string, Titik[]>();
  const akhirLabel = labelPeriode(akhir, satuan);
  for (let l = labelPeriode(mulai, satuan); l <= akhirLabel; l = langkahPeriode(l, satuan)) kelompok.set(l, []);
  for (const t of hari) kelompok.get(labelPeriode(t.tanggal, satuan))!.push(t);
  return { titik: [...kelompok].map(([l, isi]) => gabung(l, isi)), satuan };
}

// ---------------------------------------------------------------- potret (grafik 1 dan 2)

/** Satu baris tabel `pasar_manalagi` (kolom yang dibaca grafik 1 dan 2). */
export type Produk = {
  tanggal: string;
  sumber: "blibli" | "tokopedia";
  produk_key: string;
  nama_toko: string | null;
  harga_per_kg: number;
  terjual_min: number | null;
};

/**
 * Grafik 1 dan 2 memakai SELURUH rentang: setiap produk dihitung sekali, dengan harga = median
 * `harga_per_kg` selama hari-hari ia muncul di rentang, dan `terjual_min` + `nama_toko` dari hari
 * terakhirnya di rentang (boleh null; null/0 tidak ikut rata-rata tertimbang).
 * `tanggal` hasil = hari terakhir produk itu. Urut `produk_key`.
 */
export function ringkasProduk(baris: Produk[]): Produk[] {
  const perProduk = new Map<string, Produk[]>();
  for (const b of baris) {
    const daftar = perProduk.get(b.produk_key);
    if (daftar) daftar.push(b);
    else perProduk.set(b.produk_key, [b]);
  }
  return [...perProduk.keys()].sort().map((k) => {
    const hari = perProduk.get(k)!;
    const terakhir = hari.reduce((a, b) => (b.tanggal > a.tanggal ? b : a));
    return { ...terakhir, harga_per_kg: median(hari.map((h) => h.harga_per_kg))! };
  });
}

/**
 * Grafik 1, di atas hasil `ringkasProduk`. `tertimbang` berbobot `terjual_min` (null dan 0 dilewati);
 * null kalau tidak ada produk laku. Produk = `produk_key` berbeda; toko = `nama_toko` berbeda.
 */
export function angkaUtama(produk: Produk[]): {
  median: number;
  rataRata: number;
  tertimbang: number | null;
  jumlahProduk: number;
  jumlahToko: number;
} {
  const harga = produk.map((p) => p.harga_per_kg);
  const laku = produk.filter((p) => (p.terjual_min ?? 0) > 0);
  const bobot = laku.reduce((a, p) => a + p.terjual_min!, 0);
  return {
    median: median(harga) ?? NaN,
    rataRata: harga.reduce((a, b) => a + b, 0) / harga.length,
    tertimbang: laku.length ? laku.reduce((a, p) => a + p.harga_per_kg * p.terjual_min!, 0) / bobot : null,
    jumlahProduk: produk.length,
    jumlahToko: new Set(produk.map((p) => p.nama_toko).filter((t) => t !== null)).size,
  };
}

const LEBAR_KELOMPOK = 5_000;

/**
 * Grafik 2. Batas kelompok seperti `np.arange(floor(min/5000)*5000, max+5000, 5000)` lalu
 * `np.histogram`: kelompok [dari, sampai), kecuali yang terakhir juga memuat `sampai`.
 */
export function histogram(
  harga: number[],
): { kelompok: { dari: number; sampai: number; jumlah: number }[]; median: number; total: number } {
  const terkecil = Math.min(...harga);
  const terbesar = Math.max(...harga);
  const batas: number[] = [];
  for (let b = Math.floor(terkecil / LEBAR_KELOMPOK) * LEBAR_KELOMPOK; b < terbesar + LEBAR_KELOMPOK; b += LEBAR_KELOMPOK) {
    batas.push(b);
  }
  if (batas.length < 2) batas.push(batas[0] + LEBAR_KELOMPOK); // semua harga sama: satu kelompok
  const kelompok = batas.slice(0, -1).map((dari, i) => ({ dari, sampai: batas[i + 1], jumlah: 0 }));
  for (const h of harga) {
    const i = Math.min(Math.floor((h - batas[0]) / LEBAR_KELOMPOK), kelompok.length - 1);
    kelompok[i].jumlah += 1;
  }
  return {
    kelompok,
    median: median(harga) ?? NaN,
    total: harga.length,
  };
}

// ---------------------------------------------------------------- tren (grafik 3)

/**
 * Indeks berantai digeser supaya ujung kanannya = median hari terakhir yang punya keduanya:
 * garis = "harga pasar sekarang, mundur hanya mengikuti perubahan harga produk yang sama".
 */
export function geserIndeks(titik: Titik[]): (number | null)[] {
  const jangkar = titik.findLastIndex((t) => t.indeks_berantai !== null && t.median !== null);
  if (jangkar < 0) return titik.map(() => null);
  const faktor = titik[jangkar].median! / titik[jangkar].indeks_berantai!;
  return titik.map((t) => (t.indeks_berantai === null ? null : t.indeks_berantai * faktor));
}

/** Judul grafik 3: nilai terakhir dan perubahan sejak titik berdata pertama; null kalau < 2 titik. */
export function ringkasTren(
  nilai: (number | null)[],
  tanggal: string[],
): { akhir: number; ubah: number; sejak: string } | null {
  const ada = nilai.flatMap((v, i) => (v === null ? [] : [{ v, t: tanggal[i] }]));
  if (ada.length < 2) return null;
  const akhir = ada[ada.length - 1].v;
  return { akhir, ubah: akhir / ada[0].v - 1, sejak: ada[0].t };
}

// ---------------------------------------------------------------- label

const BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];

/** Label sumbu x: "14 Nov" per hari/minggu, "Nov 2027" per bulan. Dibaca dari teks, bukan jam lokal. */
export function labelSumbu(tanggal: string, satuan: Satuan): string {
  const [y, m, d] = urai(tanggal);
  return satuan === "bulan" ? `${BULAN[m - 1]} ${y}` : `${d} ${BULAN[m - 1]}`;
}

/** "14 Nov 2026" untuk teks di luar sumbu. */
export function tanggalPanjang(tanggal: string): string {
  const [y, m, d] = urai(tanggal);
  return `${d} ${BULAN[m - 1]} ${y}`;
}

/** "30 rb", "1,3 jt" — sumbu rupiah ringkas supaya muat di HP. */
export function rupiahRingkas(v: number): string {
  const satu = (x: number) => x.toLocaleString("id-ID", { maximumFractionDigits: 1 });
  if (Math.abs(v) >= 1_000_000) return `${satu(v / 1_000_000)} jt`;
  if (Math.abs(v) >= 1_000) return `${satu(v / 1_000)} rb`;
  return String(v);
}

/** Hari data terakhir paling awal yang membuka preset `p` (data mulai `awal`). */
export function tanggalTerbuka(awal: string, p: Preset): string {
  return tambahHari(geserPreset(awal, p, 1), -1);
}

/** "7 – 14 Nov 2026", "7 Nov – 3 Des 2026", "7 Nov 2026 – 2 Jan 2027". */
export function rentangTeks(mulai: string, akhir: string): string {
  if (mulai === akhir) return tanggalPanjang(mulai);
  const [y1, m1, d1] = urai(mulai);
  const [y2, m2] = urai(akhir);
  if (y1 !== y2) return `${tanggalPanjang(mulai)} – ${tanggalPanjang(akhir)}`;
  if (m1 !== m2) return `${d1} ${BULAN[m1 - 1]} – ${tanggalPanjang(akhir)}`;
  return `${d1} – ${tanggalPanjang(akhir)}`;
}
