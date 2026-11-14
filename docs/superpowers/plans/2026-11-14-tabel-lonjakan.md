# Tabel lonjakan berdiri sendiri + grafik per bulan — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The "Lonjakan toko" table on `/admin/pasar` gets its own card with its own filters, sort, rows per page and pages. Ranges longer than 90 days are drawn per month.

**Architecture:** All table state lives in URL parameters prefixed `t_`. The server page reads them and fetches one page of rows: a head count first, then `.range()`. The existing `Saringan` filter row is reused with a prefix. A pure URL helper keeps the other group's parameters, so the chart filters and the table filters never wipe each other.

**Tech Stack:** Next.js 16.3.5 (App Router, server page plus client controls), supabase-js, vitest 5, Python notebook + `ekspor_uji_web.py` for the cross-checked fixture.

**Spec:** `docs/superpowers/specs/2026-11-14-tabel-lonjakan-design.md`

## Global Constraints

- Table parameters: `t_pasar`, `t_rentang`, `t_dari`, `t_sampai`, `t_wilayah`, `t_urut` (`baru` | `turun` | `naik`), `t_baris` (10 | 25 | 50 | 100), `t_hal` (≥ 1). Unknown values fall back to the defaults: semua / semua / no region / `baru` / 10 / 1.
- Table defaults do not copy the chart filters.
- Changing the table's filters, sort or rows per page resets `t_hal` to 1. A `t_hal` past the last page is clamped to the last page.
- Stable order: the chosen order, then `tanggal` desc, then `produk_key` asc. `rasio_jendela` nulls go last.
- At most 100 rows per request (below Supabase `max_rows` = 1000).
- `kerapatan`: ≤ 90 days → `"hari"`, otherwise `"bulan"`. Weeks are removed from both copies (notebook and `src/lib/pasar.ts`).
- The spike rule, the table columns, Supabase and the laptop side stay unchanged.
- Copy is Indonesian. Empty table: "Tidak ada toko yang melonjak untuk saringan ini."
- Never run plain `npm run dev` (`.env.local` = production). Commit with explicit paths only, never `-am`.

## Review Focus

1. A chart filter change (including its Kustom date form) must keep every `t_*` parameter, and the reverse. Tests are in Task 2 (`alamatPasar`, `isianTersembunyi`).
2. `t_hal` = 0, −3, "abc", 9999, and `t_baris` = 1000 or "abc", must give a valid page, never a request over 100 rows or a 416 error. Tests are in Task 2 (`bacaTabel`) and Task 3 (clamp).
3. Zero matching rows must send no range request: PostgREST answers an offset past the end with **416 PGRST103** (verified locally on 14 Nov). Test is in Task 3.
4. A `t_wilayah` that doesn't exist for the chosen `t_pasar` must fall back to all regions. `pilihWilayah` already does this; Task 4 must call it with the table's own list.
5. Changing chart pages must not change the table's count (the data is independent). This is checked by hand in Task 4, step 4.

---

### Task 1: `kerapatan` per bulan beyond 90 days (notebook + web)

**Files:**
- Modify: `data-science/dashboard_contoh.ipynb` (the cell containing `def kerapatan(`)
- Regenerate: `src/lib/pasar.fixture.json` (via `data-science/ekspor_uji_web.py`)
- Modify: `src/lib/pasar.ts:20,167-191` (`Satuan`, `kerapatan`, `labelPeriode`, `langkahPeriode`)
- Test: `src/lib/pasar.test.ts`

**Interfaces:**
- Produces: `type Satuan = "hari" | "bulan"`; `kerapatan(mulai: string, akhir: string): Satuan`.

- [ ] **Step 1: Write the failing test** in `src/lib/pasar.test.ts`; export `kerapatan` in the import list.

```ts
test("kerapatan: ≤90 hari per hari, lebih panjang per bulan (tidak ada minggu)", () => {
  expect(kerapatan("2026-11-01", "2026-11-30")).toBe("hari");
  expect(kerapatan("2026-01-01", "2026-03-31")).toBe("hari");   // 90 hari
  expect(kerapatan("2026-01-01", "2026-04-01")).toBe("bulan");  // 91 hari
  expect(kerapatan("2026-01-01", "2026-12-31")).toBe("bulan");
});
```

Change the `labelSumbu` test at line 144: drop the `"minggu"` assertion and rename it to `"labelSumbu: hari '14 Nov', bulan 'Nov 2027'"`.

- [ ] **Step 2: Run it.** `npx vitest run src/lib/pasar.test.ts`. Expected: FAIL. The 91-day and 1-year cases return `"minggu"`, and TypeScript may flag `"minggu"` in the labelSumbu test.

- [ ] **Step 3: Notebook.** With NotebookEdit, in the `kerapatan` cell, delete the `if mulai + pd.DateOffset(years=2) > akhir: return "W", "minggu"` branch so it returns `"MS", "bulan"` after the 90-day check. Search the notebook for any other `"minggu"` / `"W"` use and remove it.

- [ ] **Step 4: Regenerate the fixture.** `cd data-science; .venv/Scripts/python ekspor_uji_web.py`. Expected: the printed `satuan [...]` lists only `'bulan'` and `'hari'` for both `asli` and `sintetis`.

- [ ] **Step 5: Web.** In `src/lib/pasar.ts`: `Satuan = "hari" | "bulan"`; `kerapatan` returns `"bulan"` after the 90-day check; delete the week branches of `labelPeriode`/`langkahPeriode`; update their doc comments. `npx tsc --noEmit` must show no `"minggu"` leftovers (in `GrafikTren`/`GrafikLonjakan` the `satuan` text just becomes "bulan").

- [ ] **Step 6: Run.** `npm test`. Expected: all pass, including every `deret` fixture case.

- [ ] **Step 7: Commit.**

```bash
git add data-science/dashboard_contoh.ipynb src/lib/pasar.fixture.json src/lib/pasar.ts src/lib/pasar.test.ts
git commit -m "Grafik pasar: lebih dari 90 hari per bulan, tanpa per minggu" -- data-science/dashboard_contoh.ipynb src/lib/pasar.fixture.json src/lib/pasar.ts src/lib/pasar.test.ts
```

### Task 2: Table URL state and the shared URL helper

**Files:**
- Create: `src/lib/tabelLonjakan.ts`
- Modify: `src/lib/pasar.ts` (`bacaFilter` gains an optional prefix)
- Test: `src/lib/tabelLonjakan.test.ts`

**Interfaces:**
- Consumes: `bacaFilter`, `Filter` from `src/lib/pasar.ts`.
- Produces:
  - `bacaFilter(sp, awalan: "" | "t_" = ""): Filter`. It reads `${awalan}pasar`, `${awalan}rentang`, `${awalan}dari`, `${awalan}sampai`.
  - `type Urut = "baru" | "turun" | "naik"`, `const BARIS = [10, 25, 50, 100] as const`, `const NAMA_URUT: Record<Urut, string>`.
  - `bacaTabel(sp): { filter: Filter; wilayah: string | string[] | undefined; urut: Urut; baris: number; hal: number }`.
  - `alamatPasar(query: string, awalan: "" | "t_", grup: Record<string, string | undefined>): string`. It returns `/admin/pasar?...`. It deletes every key of the given group (for `"t_"`, every key starting with `t_`; for `""`, the keys `pasar rentang wilayah dari sampai`), then sets the defined entries of `grup`. Keys in `grup` already carry their prefix.
  - `isianTersembunyi(query: string, awalan: "" | "t_", tambahan?: Record<string, string>): [string, string][]`: the hidden inputs a group's Kustom GET form needs, meaning every parameter of the **other** group plus `tambahan`.
  - `nomorHalaman(hal: number, total: number): (number | "…")[]`.

- [ ] **Step 1: Write the failing tests** in `src/lib/tabelLonjakan.test.ts`:

```ts
test("bacaTabel: bawaan dan nilai asing", () => {
  expect(bacaTabel({})).toMatchObject({ urut: "baru", baris: 10, hal: 1, filter: { pasar: "semua", rentang: "semua" } });
  for (const hal of ["0", "-3", "abc", "1.5"]) expect(bacaTabel({ t_hal: hal }).hal).toBe(1);
  expect(bacaTabel({ t_hal: "9999" }).hal).toBe(9999);           // dijepit nanti, sesudah jumlah diketahui
  for (const b of ["1000", "abc", "7"]) expect(bacaTabel({ t_baris: b }).baris).toBe(10);
  expect(bacaTabel({ t_baris: "50", t_urut: "turun" })).toMatchObject({ baris: 50, urut: "turun" });
  expect(bacaTabel({ pasar: "blibli", t_pasar: "tokopedia" }).filter.pasar).toBe("tokopedia");
});

test("alamatPasar: saringan grafik menjaga semua t_*", () => {
  const q = "pasar=semua&rentang=semua&t_pasar=blibli&t_urut=turun&t_hal=3";
  const u = new URLSearchParams(alamatPasar(q, "", { pasar: "tokopedia", rentang: "30h" }).split("?")[1]);
  expect([u.get("pasar"), u.get("t_pasar"), u.get("t_urut"), u.get("t_hal")]).toEqual(["tokopedia", "blibli", "turun", "3"]);
});

test("alamatPasar: saringan tabel menjaga grafik dan mengulang t_hal", () => {
  const q = "pasar=blibli&wilayah=35&t_pasar=semua&t_hal=4&t_baris=25";
  const u = new URLSearchParams(alamatPasar(q, "t_", { t_pasar: "tokopedia", t_baris: "25" }).split("?")[1]);
  expect([u.get("pasar"), u.get("wilayah"), u.get("t_pasar"), u.get("t_baris"), u.get("t_hal")])
    .toEqual(["blibli", "35", "tokopedia", "25", null]);
});

test("isianTersembunyi: form Kustom satu kelompok membawa kelompok lain", () => {
  const q = "pasar=blibli&rentang=kustom&dari=2026-11-08&sampai=2026-11-10&t_pasar=tokopedia&t_urut=naik";
  expect(isianTersembunyi(q, "")).toEqual([["t_pasar", "tokopedia"], ["t_urut", "naik"]]);
  expect(isianTersembunyi(q, "t_", { t_baris: "25" })).toEqual([
    ["pasar", "blibli"], ["rentang", "kustom"], ["dari", "2026-11-08"], ["sampai", "2026-11-10"], ["t_baris", "25"],
  ]);
});

test("nomorHalaman", () => {
  expect(nomorHalaman(1, 1)).toEqual([1]);
  expect(nomorHalaman(1, 4)).toEqual([1, 2, 3, 4]);
  expect(nomorHalaman(5, 9)).toEqual([1, "…", 4, 5, 6, "…", 9]);
  expect(nomorHalaman(1, 9)).toEqual([1, 2, "…", 9]);
});
```

- [ ] **Step 2: Run it.** `npx vitest run src/lib/tabelLonjakan.test.ts`. Expected: FAIL (the module doesn't exist).

- [ ] **Step 3: Implement** the Produces list. `hal` is a positive integer from `/^\d+$/`, else 1. `nomorHalaman` shows the first page, the last page, and the current page ±1, with `"…"` for each gap of 2 or more pages.

- [ ] **Step 4: Run.** `npm test`. Expected: all pass (the existing `bacaFilter` tests unchanged).

- [ ] **Step 5: Commit** (explicit paths: the 2 new files plus `src/lib/pasar.ts`). Message: "Tabel lonjakan: status URL t_* dan alamat yang menjaga saringan lain".

### Task 3: Fetch one page of spikes

**Files:**
- Modify: `src/lib/pasarData.ts` (replace `ambilLonjakan`)
- Test: `src/lib/pasarData.test.ts` (update the 2 tests at lines 88–109 that call `ambilLonjakan`)

**Interfaces:**
- Consumes: `Urut` from Task 2; `SaringanProduk` (already in the file).
- Produces: `ambilLonjakanHalaman(sb, q: { pasar: Pasar; mulai: string; akhir: string; wilayah?: SaringanProduk; urut: Urut; baris: number; hal: number }): Promise<{ daftar: Lonjakan[]; jumlah: number; hal: number }>`. The returned `hal` is the clamped page.

- [ ] **Step 1: Write the failing tests.** Give `klienPalsu` an optional `jumlah = 0` that the fake returns as `count`, then add:

```ts
test("lonjakan: 0 baris = hanya hitung, tanpa permintaan range (PostgREST 416)", async () => {
  const { sb, catatan } = klienPalsu(0);
  const r = await ambilLonjakanHalaman(sb, { pasar: "semua", mulai: "2026-11-07", akhir: "2026-11-14", urut: "baru", baris: 10, hal: 3 });
  expect(r).toEqual({ daftar: [], jumlah: 0, hal: 1 });
  expect(catatan.flatMap((q) => panggil(q, "range"))).toEqual([]);
});

test("lonjakan: halaman dijepit dan urutan stabil", async () => {
  const { sb, catatan } = klienPalsu(37);
  const r = await ambilLonjakanHalaman(sb, { pasar: "blibli", mulai: "2026-11-07", akhir: "2026-11-14", urut: "turun", baris: 10, hal: 9 });
  expect(r.hal).toBe(4);
  const q = catatan.at(-1)!;
  expect(panggil(q, "range")).toEqual([[30, 39]]);
  expect(panggil(q, "order")).toEqual([
    ["rasio_jendela", { ascending: true, nullsFirst: false }],
    ["tanggal", { ascending: false }],
    ["produk_key", { ascending: true }],
  ]);
  expect(panggil(q, "eq")).toContainEqual(["lonjak_toko", true]);
  expect(panggil(q, "eq")).toContainEqual(["sumber", "blibli"]);
});
```

Also keep the region assertions from the old tests, pointed at `ambilLonjakanHalaman`. For `naik`: `["rasio_jendela", { ascending: false, nullsFirst: false }]`. For `baru`: only the `tanggal` and `produk_key` orders.

- [ ] **Step 2: Run it.** `npx vitest run src/lib/pasarData.test.ts`. Expected: FAIL (`ambilLonjakanHalaman` is not exported).

- [ ] **Step 3: Implement.** First query: `select("tanggal", { count: "exact", head: true })` with the same filters. Then `hal = min(max(hal, 1), max(1, ceil(jumlah / baris)))`. If `jumlah === 0`, return without a second query. Otherwise run the page query with `KOLOM_LONJAKAN`, the orders above, and `.range((hal-1)*baris, hal*baris-1)`. Put the shared filters in one local function so both queries use exactly the same ones. Delete `ambilLonjakan`.

- [ ] **Step 4: Run.** `npm test`. Expected: all pass. (`page.tsx` still imports `ambilLonjakan`, so `tsc` fails until Task 4; that's expected.)

- [ ] **Step 5: Commit** `src/lib/pasarData.ts src/lib/pasarData.test.ts`. Message: "Lonjakan: satu halaman per permintaan, hitung dulu, halaman dijepit".

### Task 4: The table card on the page

**Files:**
- Modify: `src/app/admin/pasar/Saringan.tsx` (new props `awalan`, `query`, `tambahan`)
- Create: `src/app/admin/pasar/PengaturanTabel.tsx` (client: sort and rows `<select>`s)
- Modify: `src/app/admin/pasar/TabelLonjakan.tsx` (becomes the whole card: heading, `Saringan`, `PengaturanTabel`, table, pager)
- Modify: `src/app/admin/pasar/page.tsx`

**Interfaces:**
- Consumes: Task 2 (`bacaTabel`, `alamatPasar`, `isianTersembunyi`, `nomorHalaman`, `BARIS`, `NAMA_URUT`) and Task 3 (`ambilLonjakanHalaman`).
- Produces:
  - `Saringan` props add `awalan: "" | "t_"`, `query: string` (the current query string, built in `page.tsx` from `sp`), and `tambahan?: Record<string, string>`. Its `alamat()` is replaced by `alamatPasar(query, awalan, {...prefixed group values, ...tambahan})`. The Kustom form uses prefixed input names, keeps `action="/admin/pasar"`, and adds `isianTersembunyi(query, awalan, tambahan)` as hidden inputs.

- [ ] **Step 1: `Saringan`.** Add the props and wire them as above. The chart passes `awalan=""` and no `tambahan`. The table passes `awalan="t_"` and `tambahan={{ t_urut, t_baris }}`, leaving out default values. Leave the visuals alone.

- [ ] **Step 2: Card.** `TabelLonjakan` (server component). Props: the table's filter state and wilayah list, `batas`, `status`, the `pilihRentang` result, `daftar`, `jumlah`, `hal`, `baris`, `urut`, `query`.
  - Heading: `Lonjakan toko: {jumlah}`.
  - Under it: `Saringan awalan="t_"`, then `PengaturanTabel` (Urutkan: `NAMA_URUT`; Baris per halaman: `BARIS`; both navigate with `alamatPasar(query, "t_", …)`, so `t_hal` resets).
  - Then the existing table markup.
  - Then the pager: `nomorHalaman(hal, ceil(jumlah/baris))` rendered as `next/link` with `alamatPasar(query, "t_", {...group, t_hal: String(n)})`. The current page is `aria-current="page"`. Show ‹ and › links. Tap targets are ≥ 44 px, and at 360 px width it wraps with no page-level horizontal scroll.
  - When there's no data, no range, or zero rows, keep the filter row and show one line instead of the table. Use the spec copy for zero rows.

- [ ] **Step 3: `page.tsx`.**
  - Build `query` from `sp`.
  - Read `bacaTabel(sp)`.
  - Fetch the table's region list (`ambilDaftarWilayah(sb, tabel.filter.pasar)`), then `pilihWilayah`, `ambilBatas`, `statusPreset`, `pilihRentang` and `ambilLonjakanHalaman`, all with the **table's** values. Run them in parallel with the chart reads where they don't depend on each other.
  - Remove `TabelLonjakan` from the chart 3 card. Render the new card as its own `<section>` after chart 3 in every branch where the page renders charts, and also when the chart side is empty: the table is independent, so place it outside the chart `if` branches.
  - Pass `awalan=""` and `query` to the chart `Saringan`.

- [ ] **Step 4: Verify.**
  - `npm test`, `npx tsc --noEmit` and `npm run lint` all pass.
  - Then run against **local** Supabase only (`$env:NEXT_PUBLIC_SUPABASE_URL="http://127.0.0.1:54321"`, plus the local anon and service keys from `npx supabase status`; then `npx next dev --webpack`), log in as `uji@lokal.test`, and check by hand:
    - (a) Changing the chart's marketplace keeps the table's settings, and the reverse.
    - (b) The Kustom form on either side keeps the other side's settings.
    - (c) `?t_hal=999` shows the last page; `?t_baris=1000` shows 10 rows.
    - (d) Changing sort resets to page 1.
    - (e) At 360 px width, no page-level horizontal scroll.
    - (f) The chart's "N berdata" doesn't change when the table changes.

- [ ] **Step 5: Commit** the 4 files with explicit paths. Message: "/admin/pasar: tabel lonjakan jadi kartu sendiri dengan saringan, urutan, baris, halaman".
