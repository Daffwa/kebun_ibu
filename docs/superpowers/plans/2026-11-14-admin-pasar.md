# Halaman `/admin/pasar` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Halaman admin yang menampilkan grafik 1, 2, 3, 6 harga Mangga Manalagi dari tabel Supabase `pasar_manalagi` dan `pasar_manalagi_harian`, dengan filter marketplace dan rentang.

**Architecture:** Filter di URL. Server Component membaca Supabase (sesi pengguna, RLS), menghitung dengan fungsi murni di `src/lib/pasar.ts` (port Langkah 2 notebook), lalu mengirim angka siap gambar ke komponen grafik Recharts (`"use client"`). Hasil port diuji silang dengan keluaran notebook lewat fixture JSON.

**Tech Stack:** Next.js 16.3.5 (App Router), React 19.2.8, Supabase (`@supabase/ssr`), Recharts 3.10.1, Tailwind 4, vitest 5, Python + pandas (hanya untuk membuat fixture).

**Spec:** `docs/superpowers/specs/2026-11-14-admin-pasar-web-design.md` (web) dan `docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md` (aturan grafik). Acuan perilaku: `data-science/dashboard_contoh.ipynb` sel 6 (Langkah 2).

## Global Constraints

- Kerja di cabang git biasa `admin-pasar` dari `main`, **bukan worktree**. Satu commit per task, tidak di-push.
- **Jangan pernah `git commit -am` atau `git add .`/`-A`.** Selalu `git add` file yang tepat. Folder ini punya perubahan lain yang belum di-commit (`eslint.config.mjs`, `tsconfig.json`, `docs/rencana-data-science.md`, perbaikan data-science dari sesi lain) yang tidak boleh masuk commit web. Periksa `git diff --cached --stat` sebelum setiap commit.
- Next.js 16: `searchParams` adalah `Promise`; ikuti pola `src/app/admin/page.tsx` (`export const revalidate = 0`).
- Baca lewat `supabaseServer()` (`src/lib/supabase/server.ts`), **jangan** `supabase/admin.ts`.
- Setiap baca tabel lewat fungsi paging 1000 baris (`max_rows = 1000`), termasuk potret. Paging selalu dengan `order` yang stabil.
- Tanggal = teks `YYYY-MM-DD`; aritmetika memakai `Date.UTC`/`getUTC*`. Dilarang `new Date("…")` lalu `getDate()` lokal.
- Tahun = kalender (seperti `pd.DateOffset(years=n)`): `2028-02-29` + 1 tahun = `2029-02-28`.
- Kerapatan: ≤ 90 hari → hari; `mulai + 2 tahun > akhir` → minggu (pandas `W`, berakhir Minggu, label Minggu); selain itu bulan (pandas `MS`, label tanggal 1).
- Gabung: `jumlah_produk`, `median`, `indeks_berantai`, `median_rasio` = median; `naik`, `turun`, `berdata` = jumlah; `lonjak_pasar` = maks; periode tanpa data → `naik`, `turun`, `lonjak_pasar` = null.
- `HARGA_IBUK = 30_000` dengan komentar `// CONTOH: ganti dengan harga jual Ibuk per kg`.
- `AMBANG_PASAR = 0.05`, `AMBANG_TOKO = 0.10`, `JENDELA_HARI = 7` (hanya untuk teks dan pita grafik; hitungan sudah di laptop).
- Warna grafik: biru `#2a78d6`, oranye `#eb6834`, merah `#e34948`, grid `#e1e0d9`, sumbu `#c3c2b7`, teks redup `#898781`. Teks memakai tinta situs (`text-daun-tua`, `text-daun`), bukan warna seri.
- Rupiah memakai `rupiah()` dari `src/lib/format.ts`.
- Teks UI dalam bahasa Indonesia, sama dengan notebook (misalnya "Terbuka setelah 30 hari data (sekarang 8/30)").

## Review Focus

1. **Lompat tahun kabisat** — rentang `1 tahun` yang berakhir 29 Feb atau dimulai 29 Feb harus sama dengan pandas. Uji di Task 2 (`tambahTahun`) dan fixture sintetis yang melewati Feb 2028.
2. **Minggu/bulan tanpa data sama sekali** — titik tetap ada, garis putus, batang `naik/turun` kosong (bukan 0). Fixture sintetis punya satu minggu penuh kosong; diuji di Task 2.
3. **Tepat 1000 baris** di satu halaman — paging harus meminta halaman berikutnya dan berhenti saat kosong, bukan berhenti karena "pas 1000". Uji di Task 4.
4. **Potret satu harga saja / satu produk** — histogram tetap satu kelompok, tidak crash, tidak kosong. Uji di Task 3.
5. **URL buatan tangan** (`?rentang=1t` saat terkunci, `?pasar=shopee`, `?dari=abc`, Dari > Sampai) — jatuh ke bawaan atau pesan "Rentang kosong", tidak error 500. Uji di Task 2 (`bacaFilter`, `pilihRentang`).

---

### Task 1: Fixture uji silang dari notebook

**Files:**
- Create: `data-science/ekspor_uji_web.py`
- Create (hasil skrip): `src/lib/pasar.fixture.json`

**Interfaces:**
- Produces: `src/lib/pasar.fixture.json` dengan bentuk
  ```ts
  {
    data: Record<"asli" | "sintetis", {
      harian: HarianBaris[];                         // semua pasar, kolom tabel Supabase
      status: Record<Pasar, Record<"30h"|"1t"|"5t", { terbuka: boolean; pesan: string }>>;
      kasus: { pasar: Pasar; mulai: string; akhir: string; satuan: Satuan; titik: Titik[] }[];
      rentang: { pasar: Pasar; preset: "30h"|"1t"|"5t"|"semua"; mulai: string; akhir: string }[];
    }>
  }
  ```
  NaN → `null`; tanggal → `YYYY-MM-DD`; `lonjak_pasar` di `titik` = `0 | 1 | null`.

- [ ] **Step 1: Tulis `ekspor_uji_web.py`**

  - Fungsi notebook diambil dengan `exec` sel kode yang berisi `def deret(` dari `dashboard_contoh.ipynb` ke namespace `{"pd": pd, "np": np, "harian": harian, "mdates": None, "plt": None, "mtick": None, "sns": None}` — satu sumber kebenaran, tidak disalin. Nama preset notebook (`"30 hari"`, `"1 tahun"`, `"5 tahun"`, `"Semua"`) dipetakan ke `30h`, `1t`, `5t`, `semua`.
  - `ATURAN` notebook juga menggabung `rata_rata` dan `tertimbang`, jadi `harian` yang diberikan ke `deret` harus punya kedua kolom itu (sintetis: isi sama dengan `median`). Yang ditulis ke JSON hanya kolom tabel Supabase.
  - **asli**: `hitung()` dari `dashboard_manalagi.py` pada `warehouse/harga_buah.duckdb` (`read_only=True`).
  - **sintetis**: `np.random.default_rng(13)`, Blibli mulai `2026-11-07`, Tokopedia `2026-11-08`, sampai `2029-12-31`; median acak-jalan ±3%; ±5% hari dihapus acak; **seluruh minggu 2027-03-01…2027-03-07 dihapus untuk semua pasar**; `naik`/`turun` acak 0–3; `lonjak_pasar` saat |median_rasio−1| ≥ 0.05. Baris `semua` = gabungan hari yang ada di salah satu sumber.
  - Kasus per data per pasar: setiap preset yang terbuka + `semua`, plus kustom `2027-02-20…2027-03-20` (hari, minggu kosong), `2027-12-01…2028-03-15` (minggu, lewat 29 Feb), `2028-02-29…2029-02-28` (minggu). Kasus yang di luar data dilewati.
  - Tulis JSON dengan `indent=1`, `ensure_ascii=False`.

- [ ] **Step 2: Jalankan dan periksa**

  Run: `cd data-science; python ekspor_uji_web.py`
  Expected: mencetak jumlah kasus per data (sintetis ≥ 20, minimal satu `satuan` = `bulan`), file `src/lib/pasar.fixture.json` < 3 MB.

- [ ] **Step 3: Commit**

```bash
git add data-science/ekspor_uji_web.py src/lib/pasar.fixture.json
git commit -m "Fixture uji silang /admin/pasar dari notebook dashboard"
```

---

### Task 2: Tanggal, filter, kunci rentang, deret (`src/lib/pasar.ts`)

**Files:**
- Create: `src/lib/pasar.ts`
- Test: `src/lib/pasar.test.ts`

**Interfaces:**
- Consumes: `src/lib/pasar.fixture.json` (Task 1).
- Produces:
  ```ts
  export type Pasar = "semua" | "blibli" | "tokopedia";
  export type Preset = "30h" | "1t" | "5t";
  export type Rentang = Preset | "semua" | "kustom";
  export type Satuan = "hari" | "minggu" | "bulan";
  export type HarianBaris = { tanggal: string; pasar: Pasar; jumlah_produk: number; median: number;
    indeks_berantai: number; median_rasio: number | null; lonjak_pasar: boolean; naik: number; turun: number };
  export type Titik = { tanggal: string; jumlah_produk: number | null; median: number | null;
    indeks_berantai: number | null; median_rasio: number | null; naik: number | null;
    turun: number | null; lonjak_pasar: 0 | 1 | null; berdata: number };
  export type Filter = { pasar: Pasar; rentang: Rentang; dari: string | null; sampai: string | null };
  export const HARGA_IBUK, AMBANG_PASAR, AMBANG_TOKO, JENDELA_HARI;
  export const NAMA_PASAR: Record<Pasar, string>;          // "Semua marketplace", "Tokopedia", "Blibli"
  export const NAMA_RENTANG: Record<Rentang, string>;      // "30 hari", "1 tahun", "5 tahun", "Semua", "Kustom"
  export function tambahHari(t: string, n: number): string;
  export function tambahTahun(t: string, n: number): string;
  export function selisihHari(dari: string, sampai: string): number;   // sampai − dari
  export function bacaFilter(sp: Record<string, string | string[] | undefined>): Filter;
  export function statusPreset(awal: string, akhir: string): Record<Preset, { terbuka: boolean; pesan: string }>;
  export function rentangPreset(awal: string, akhir: string, r: Preset | "semua"): [string, string];
  export function pilihRentang(f: Filter, awal: string, akhir: string):
    { rentang: Rentang; mulai: string; akhir: string } | { rentang: "kustom"; kosong: true };
  export function kerapatan(mulai: string, akhir: string): Satuan;
  export function deret(harian: HarianBaris[], mulai: string, akhir: string): { titik: Titik[]; satuan: Satuan };
  ```
  `harian` di `deret` sudah disaring ke satu pasar.

- [ ] **Step 1: Tulis tes yang gagal**

```ts
test("tambahTahun mengikuti DateOffset", () => {
  expect(tambahTahun("2028-02-29", 1)).toBe("2029-02-28");
  expect(tambahTahun("2029-02-28", -1)).toBe("2028-02-28");
  expect(tambahHari("2026-12-31", 1)).toBe("2027-01-01");
  expect(selisihHari("2026-11-07", "2026-11-14")).toBe(7);
});

test("bacaFilter: nilai asing jatuh ke bawaan", () => {
  expect(bacaFilter({ pasar: "shopee", rentang: "x", dari: "abc" }))
    .toEqual({ pasar: "semua", rentang: "semua", dari: null, sampai: null });
  expect(bacaFilter({ pasar: "blibli", rentang: "kustom", dari: "2026-11-08", sampai: "2026-11-10" }))
    .toEqual({ pasar: "blibli", rentang: "kustom", dari: "2026-11-08", sampai: "2026-11-10" });
});

test("statusPreset: 8 hari data, 30 hari terkunci", () => {
  expect(statusPreset("2026-11-07", "2026-11-14")["30h"])
    .toEqual({ terbuka: false, pesan: "30 hari: terbuka setelah 30 hari data (sekarang 8/30)" });
});

test("pilihRentang: preset terkunci jatuh ke semua; Dari > Sampai kosong; kustom dijepit", () => {
  const f = (x: Partial<Filter>) => ({ pasar: "semua", rentang: "semua", dari: null, sampai: null, ...x }) as Filter;
  expect(pilihRentang(f({ rentang: "1t" }), "2026-11-07", "2026-11-14"))
    .toEqual({ rentang: "semua", mulai: "2026-11-07", akhir: "2026-11-14" });
  expect(pilihRentang(f({ rentang: "kustom", dari: "2026-11-12", sampai: "2026-11-09" }), "2026-11-07", "2026-11-14"))
    .toEqual({ rentang: "kustom", kosong: true });
  expect(pilihRentang(f({ rentang: "kustom", dari: "2026-01-01", sampai: null }), "2026-11-07", "2026-11-14"))
    .toEqual({ rentang: "kustom", mulai: "2026-11-07", akhir: "2026-11-14" });
});

describe.each(["asli", "sintetis"] as const)("sama dengan notebook (%s)", (nama) => {
  const d = fixture.data[nama];
  test("statusPreset & rentangPreset", () => { /* tiap pasar: batas dari d.harian, bandingkan d.status dan d.rentang */ });
  test.each(d.kasus.map((k) => [k.pasar, k.mulai, k.akhir, k]))("deret %s %s–%s", (pasar, mulai, akhir, k) => {
    const hasil = deret(d.harian.filter((h) => h.pasar === pasar), mulai, akhir);
    expect(hasil.satuan).toBe(k.satuan);
    expect(hasil.titik.map((t) => t.tanggal)).toEqual(k.titik.map((t) => t.tanggal));
    hasil.titik.forEach((t, i) => expectTitikDekat(t, k.titik[i]));   // angka: toBeCloseTo(…, 6); null tetap null
  });
});
```

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `npx vitest run src/lib/pasar.test.ts`
  Expected: FAIL (`pasar.ts` belum ada).

- [ ] **Step 3: Tulis `src/lib/pasar.ts`**

  `bacaFilter`: tanggal sah hanya kalau cocok `/^\d{4}-\d{2}-\d{2}$/` dan `tambahHari(t, 0) === t`. `pilihRentang`: preset terkunci → `semua`; kustom: `mulai = max(dari ?? awal, awal)`, `akhir = min(sampai ?? akhir, akhir)`, kosong kalau `mulai > akhir`. Minggu `deret`: label periode = Minggu pertama ≥ tanggal (`tambahHari(t, (7 − hariUTC) % 7)`), label dari Minggu ≥ `mulai` sampai Minggu ≥ `akhir`, setiap minggu di antaranya ada. Median: rata-rata dua nilai tengah untuk jumlah genap; null kalau tidak ada nilai.

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: `npx vitest run src/lib/pasar.test.ts`
  Expected: PASS semua, termasuk semua kasus fixture.

- [ ] **Step 5: Commit**

```bash
git add src/lib/pasar.ts src/lib/pasar.test.ts
git commit -m "pasar.ts: filter, kunci rentang, kerapatan, deret (sama dengan notebook)"
```

---

### Task 3: Hitungan potret dan tren (`src/lib/pasar.ts`)

**Files:**
- Modify: `src/lib/pasar.ts`
- Test: `src/lib/pasar.test.ts`

**Interfaces:**
- Consumes: `Titik` (Task 2).
- Produces:
  ```ts
  export type Produk = { tanggal: string; sumber: "blibli" | "tokopedia"; produk_key: string;
    nama_toko: string | null; kota: string | null; harga_per_kg: number; terjual_min: number | null };
  export function angkaUtama(snap: Produk[]): { median: number; rataRata: number;
    tertimbang: number | null; jumlahProduk: number; jumlahToko: number };
  export function histogram(harga: number[], hargaIbuk: number): { kelompok: { dari: number; sampai: number; jumlah: number }[];
    median: number; lebihMurah: number; total: number };
  export function geserIndeks(titik: Titik[]): (number | null)[];
  export function ringkasTren(nilai: (number | null)[], tanggal: string[]): { akhir: number; ubah: number; sejak: string } | null;
  ```

- [ ] **Step 1: Tulis tes yang gagal**

```ts
const p = (harga: number, terjual: number | null = null, toko = "A") =>
  ({ tanggal: "2026-11-14", sumber: "blibli", produk_key: `${toko}${harga}`, nama_toko: toko, kota: null, harga_per_kg: harga, terjual_min: terjual }) as Produk;

test("angkaUtama: tertimbang hanya produk laku", () => {
  expect(angkaUtama([p(20000, 10, "A"), p(30000, 30, "B"), p(40000, null, "B")]))
    .toEqual({ median: 30000, rataRata: 30000, tertimbang: 27500, jumlahProduk: 3, jumlahToko: 2 });
  expect(angkaUtama([p(20000, 0)]).tertimbang).toBeNull();
});

test("histogram: kelompok Rp5.000, kelompok terakhir menutup kanan", () => {
  const h = histogram([20000, 22000, 34999, 40000], 30000);
  expect(h.kelompok).toEqual([
    { dari: 20000, sampai: 25000, jumlah: 2 }, { dari: 25000, sampai: 30000, jumlah: 0 },
    { dari: 30000, sampai: 35000, jumlah: 1 }, { dari: 35000, sampai: 40000, jumlah: 1 }]);
  expect([h.median, h.lebihMurah, h.total]).toEqual([28499.5, 2, 4]);
});

test("histogram: satu harga saja tetap satu kelompok", () => {
  expect(histogram([30000, 30000], 30000).kelompok).toEqual([{ dari: 30000, sampai: 35000, jumlah: 2 }]);
});

test("geserIndeks: ujung kanan = median hari terakhir yang punya keduanya", () => {
  const t = (indeks: number | null, median: number | null) => ({ indeks_berantai: indeks, median }) as Titik;
  expect(geserIndeks([t(100, 30000), t(110, 33000), t(null, null)])).toEqual([30000, 33000, null]);
  const r = ringkasTren([30000, 33000, null], ["2026-11-07", "2026-11-08", "2026-11-09"])!;
  expect([r.akhir, r.sejak]).toEqual([33000, "2026-11-07"]);
  expect(r.ubah).toBeCloseTo(0.1, 10);
  expect(ringkasTren([null, 33000], ["a", "b"])).toBeNull();     // < 2 titik
});
```

  Batas histogram mengikuti `np.arange(floor(min/5000)*5000, max+5000, 5000)` lalu `np.histogram`; kalau batas < 2, satu kelompok `[batas, batas+5000]`.

- [ ] **Step 2: Jalankan, pastikan gagal** — `npx vitest run src/lib/pasar.test.ts`, Expected: FAIL (fungsi belum ada).
- [ ] **Step 3: Tambahkan fungsi-fungsi di atas ke `src/lib/pasar.ts`.**
- [ ] **Step 4: Jalankan, pastikan lulus** — Expected: PASS.
- [ ] **Step 5: Commit** — `git add src/lib/pasar.ts src/lib/pasar.test.ts && git commit -m "pasar.ts: angka utama, histogram, indeks digeser"`

---

### Task 4: Baca Supabase dengan paging (`src/lib/pasarData.ts`)

**Files:**
- Create: `src/lib/pasarData.ts`
- Test: `src/lib/pasarData.test.ts`

**Interfaces:**
- Consumes: `Pasar`, `HarianBaris`, `Produk` (Task 2–3).
- Produces:
  ```ts
  export const UKURAN_HALAMAN = 1000;
  export async function ambilSemua<T>(halaman: (dari: number, sampai: number) =>
    PromiseLike<{ data: T[] | null; error: { message: string } | null }>): Promise<T[]>;
  export type Lonjakan = { tanggal: string; nama_toko: string | null; sumber: "blibli" | "tokopedia";
    kota: string | null; median_jendela: number | null; harga_per_kg: number; rasio_jendela: number | null };
  export async function ambilBatas(sb: SupabaseClient, pasar: Pasar): Promise<{ awal: string; akhir: string } | null>;
  export async function ambilHarian(sb: SupabaseClient, pasar: Pasar, mulai: string, akhir: string): Promise<HarianBaris[]>;
  export async function ambilPotret(sb: SupabaseClient, pasar: Pasar, tanggal: string): Promise<Produk[]>;
  export async function ambilLonjakan(sb: SupabaseClient, pasar: Pasar, mulai: string, akhir: string):
    Promise<{ daftar: Lonjakan[]; jumlah: number }>;
  ```
  `SupabaseClient` = tipe hasil `supabaseServer()`.

- [ ] **Step 1: Tulis tes yang gagal** (hanya `ambilSemua`; fungsi lain diuji di Task 6 terhadap Supabase lokal)

```ts
const palsu = (total: number, gagalDi = -1) => {
  const panggilan: [number, number][] = [];
  const halaman = async (dari: number, sampai: number) => {
    panggilan.push([dari, sampai]);
    if (panggilan.length - 1 === gagalDi) return { data: null, error: { message: "putus" } };
    return { data: Array.from({ length: Math.max(0, Math.min(sampai, total - 1) - dari + 1) }, (_, i) => dari + i), error: null };
  };
  return { halaman, panggilan };
};

test("2500 baris: 3 halaman, urutan terjaga", async () => {
  const { halaman, panggilan } = palsu(2500);
  const hasil = await ambilSemua(halaman);
  expect(hasil).toHaveLength(2500);
  expect(hasil[2499]).toBe(2499);
  expect(panggilan).toEqual([[0, 999], [1000, 1999], [2000, 2999]]);
});

test("tepat 1000 baris: meminta halaman kedua yang kosong lalu berhenti", async () => {
  const { halaman, panggilan } = palsu(1000);
  expect(await ambilSemua(halaman)).toHaveLength(1000);
  expect(panggilan).toHaveLength(2);
});

test("galat di halaman kedua dilempar, bukan hasil setengah", async () => {
  await expect(ambilSemua(palsu(2500, 1).halaman)).rejects.toThrow("putus");
});
```

- [ ] **Step 2: Jalankan, pastikan gagal** — `npx vitest run src/lib/pasarData.test.ts`, Expected: FAIL.
- [ ] **Step 3: Tulis `src/lib/pasarData.ts`**

  Setiap query pakai `ambilSemua` + `.range(dari, sampai)` dengan urutan stabil: harian `order("tanggal")`; potret `order("produk_key")`; `ambilBatas` = dua query `.limit(1)` (naik/turun `tanggal`), null kalau kosong; `ambilLonjakan` = `.eq("lonjak_toko", true)`, `order("tanggal", desc)`, `order("produk_key")`, `.limit(20)`, `{ count: "exact" }` (tidak perlu paging, maksimal 20). Filter `sumber` hanya kalau `pasar !== "semua"`. Kolom `select` hanya yang ada di tipe.

- [ ] **Step 4: Jalankan, pastikan lulus** — Expected: PASS.
- [ ] **Step 5: Commit** — `git add src/lib/pasarData.* && git commit -m "pasarData: baca Supabase per 1000 baris"`

---

### Task 5: Komponen grafik Recharts

**Files:**
- Modify: `package.json`, `package-lock.json` (`npm install recharts@3.10.1 --save-exact`)
- Create: `src/app/admin/pasar/GrafikHistogram.tsx`, `GrafikTren.tsx`, `GrafikLonjakan.tsx` (semua `"use client"`)
- Modify: `src/lib/pasar.ts` — tambah `labelSumbu(tanggal: string, satuan: Satuan): string` ("14 Nov" untuk hari/minggu, "Nov 2027" untuk bulan; nama bulan tetap `Jan Feb Mar Apr Mei Jun Jul Agu Sep Okt Nov Des`, dibaca dari teks tanggal, bukan `Date` lokal)
- Test: `src/lib/pasar.test.ts`

**Interfaces:**
- Consumes: `Titik`, `Satuan`, `histogram()` output, `geserIndeks()` output, konstanta (Task 2–3).
- Produces (props):
  ```ts
  GrafikHistogram({ kelompok, median, hargaIbuk, lebihMurah, total, tanggal }: …)
  GrafikTren({ titik: { tanggal: string; indeks: number | null; median: number | null }[], satuan: Satuan })
  GrafikLonjakan({ titik: Titik[], satuan: Satuan })
  ```

- [ ] **Step 1: Tes `labelSumbu`** — `expect(labelSumbu("2026-11-14","hari")).toBe("14 Nov")`, `expect(labelSumbu("2027-11-01","bulan")).toBe("Nov 2027")`, `expect(labelSumbu("2027-01-03","minggu")).toBe("3 Jan")`. Jalankan → FAIL → tulis → PASS.
- [ ] **Step 2: Pasang Recharts** — `npm install recharts@3.10.1 --save-exact`. Expected: `"recharts": "3.10.1"` di `package.json`, tanpa peringatan peer React.
- [ ] **Step 3: Tulis tiga komponen** mengikuti notebook (`grafik_histogram`, `grafik_tren`, `grafik_lonjakan`):
  - Semua: `ResponsiveContainer` lebar 100%, tinggi 260 (lonjakan: 220 + 160, dua grafik `syncId="lonjakan"`), grid horizontal saja, `Tooltip` dengan `rupiah()`/persen dan label tanggal `labelSumbu`, garis 2px, titik r=4 hanya kalau ≤ 31 titik, `connectNulls={false}`, `isAnimationActive={false}`.
  - Histogram: `BarChart`, `XAxis` kategori "Rp20.000–25.000", `ReferenceLine` median (abu putus-putus, label "Median Rp…") dan Ibuk (hitam, label "Harga Ibuk Rp… · X dari N produk lebih murah"). Garis rujukan di sumbu kategori diletakkan pada kelompok yang memuat harga itu; label juga ditulis sebagai teks di atas grafik supaya tidak bertabrakan di HP.
  - Tren: dua `Line` (biru indeks "Produk yang sama", oranye median "Median semua produk"), `Legend` di bawah; sumbu y mulai 0.
  - Lonjakan atas: `(median_rasio − 1) × 100`, `ReferenceArea` ±5 abu, `ReferenceLine` y=0, label "Lonjakan pasar +x%" pada titik `lonjak_pasar = 1`. Bawah: `Bar naik` merah positif, `Bar turun` biru sebagai nilai negatif, `stackOffset="sign"`, sumbu y menampilkan nilai mutlak, label "N naik"/"N turun" kalau ≤ 31 titik.
- [ ] **Step 4: Cek tipe dan lint** — `npx tsc --noEmit` dan `npm run lint`. Expected: tanpa galat.
- [ ] **Step 5: Commit** — `git add package.json package-lock.json src/app/admin/pasar src/lib/pasar.* && git commit -m "Grafik Recharts untuk /admin/pasar"`

---

### Task 6: Halaman, filter, menu, dan uji di Supabase lokal

**Files:**
- Create: `src/app/admin/pasar/page.tsx` (Server Component)
- Create: `src/app/admin/pasar/Saringan.tsx` (server; tautan + form GET Kustom)
- Create: `src/app/admin/pasar/AngkaUtama.tsx`, `TabelLonjakan.tsx` (server)
- Modify: `src/app/admin/NavAdmin.tsx` (tambah `{ href: "/admin/pasar", label: "Pasar" }` sebelum Pengaturan)

**Interfaces:**
- Consumes: semua di atas.

- [ ] **Step 1: Tulis halaman** dengan urutan:
  1. `bacaFilter(await searchParams)`; `ambilBatas`. Null → kotak putus-putus "Belum ada data harga Manalagi untuk {NAMA_PASAR}." (pola `riwayat/page.tsx`).
  2. `statusPreset`, `pilihRentang`. Kosong → Saringan + "Rentang kosong: tanggal Dari sesudah Sampai."
  3. `ambilHarian` → `deret`; hari potret = `tanggal` terbesar di hasil `ambilHarian`; `ambilPotret` dan `ambilLonjakan` paralel (`Promise.all`).
  4. Baris cakupan: "{NAMA_PASAR} · 7 Nov – 14 Nov 2026 · 8 hari, 8 berdata · satu titik = 1 hari".
  5. Kartu putih (`rounded-[10px] bg-putih p-4`) per grafik, judul mengikuti notebook (grafik 3: "Harga per kg produk yang sama: Rp…, +x% sejak …"; grafik 6: "Harga pasar vs 7 hari sebelumnya (per hari): tidak ada lonjakan pasar" / "N hari lonjakan pasar").
  6. `TabelLonjakan`: kolom Tanggal, Toko, Pasar, Kota, Sebelumnya, Sekarang, Perubahan; "Lonjakan toko dalam rentang: N (20 terbaru)"; geser horizontal di HP.
- [ ] **Step 2: `Saringan`**: pil marketplace mempertahankan `rentang`/`dari`/`sampai`; pil rentang mempertahankan `pasar`; preset terkunci = `<span aria-disabled>` abu, bukan tautan; pesan "Terkunci · …" di bawahnya; form Kustom `method="get"` dengan `input type="date"` `min`/`max` = batas data, hidden `pasar` dan `rentang=kustom`, tombol "Terapkan".
- [ ] **Step 3: Cek** — `npx vitest run`, `npx tsc --noEmit`, `npm run lint`, `npm run build`. Expected: semua lulus, rute `/admin/pasar` muncul sebagai dinamis (ƒ) di keluaran build.
- [ ] **Step 4: Uji di Supabase lokal** (lihat memori local-supabase-testing; jangan `npm run dev` polos):
  1. Docker hidup, `npx supabase start`, migrasi lokal sudah ada `pasar_manalagi`.
  2. `cd data-science; python kirim_supabase.py` dengan env lokal → log "terkirim N tanggal".
  3. Jalankan dev dengan env lokal, masuk sebagai pengelola, buka `/admin/pasar`, `?pasar=blibli`, `?rentang=1t`, `?rentang=kustom&dari=2026-11-12&sampai=2026-11-09`, `?pasar=shopee`.
  Expected: angka grafik 1 dan "X dari N produk lebih murah" sama dengan `tampilkan("semua", …)` di notebook untuk rentang yang sama; tidak ada error 500; lebar 375px tanpa geser horizontal halaman.
- [ ] **Step 5: Tangkapan layar** 375px dan 1280px, periksa label tidak bertabrakan (langkah 7 skill dataviz).
- [ ] **Step 6: Commit** — `git add src/app/admin && git commit -m "Halaman /admin/pasar: filter, grafik 1-2-3-6, tabel lonjakan"`
