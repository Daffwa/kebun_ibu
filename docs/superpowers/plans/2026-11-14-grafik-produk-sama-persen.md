# Grafik produk yang sama dalam persen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chart 3 on `/admin/pasar` and Grafik 3 in the notebook show both lines as percent change since the first point that has both values, instead of a rupiah line pinned to the last day.

**Architecture:** One pure function in `src/lib/pasar.ts` turns the chart's points into two percent series plus a summary for the title. `GrafikTren` draws percents. `page.tsx` builds the title and caption. The notebook's `grafik_tren` gets the same rule.

**Tech Stack:** Next.js 16.3.5, Recharts, vitest 5; Python notebook (pandas, matplotlib).

**Spec:** `docs/superpowers/specs/2026-11-14-grafik-produk-sama-persen-design.md`

## Global Constraints

- Base point: the first point in the range with both `indeks_berantai` and `median`. Produk yang sama = `indeks_berantai / dasar − 1`; semua produk = `median / dasar − 1`. Points before the base, and points without data, are empty (the line breaks).
- Title: "Perubahan harga sejak {tanggal dasar}: produk yang sama {±x,x%}, semua produk {±x,x%}", using the last point that has both values. With fewer than 2 such points, the title is just "Perubahan harga".
- Legend: "Produk yang sama", "Semua produk (median)". Colours unchanged (blue, orange).
- Tooltip: "Produk yang sama +0,0%", "Semua produk +16,0% (median Rp 30.000)".
- Caption: "Garis biru hanya bergerak kalau produk yang sama berubah harga. Kalau garis oranye naik tapi biru datar, harga naik karena produk yang muncul berganti, bukan karena penjual menaikkan harga."
- Y axis is in percent, with a thicker 0% line and limits symmetric around 0.
- No data changes (Supabase and laptop stay as they are).
- Tests run through PowerShell (`powershell.exe -NoProfile -Command "npm test"`); vitest fails from Git Bash here. Commit with explicit paths only.

## Review Focus

1. The first day has `median` but no `indeks_berantai` (7 Nov in real data had only Blibli): the base must move to the first day with both values, not start at an empty line. Test in Task 1.
2. A range with only 1 point that has both values gives no title numbers and no crash. Test in Task 1.
3. A range where every point is empty gives all-null series and the plain title. Test in Task 1.
4. A monthly range (more than 90 days) uses the same rule on monthly points. The function receives points, not dates, so no test is needed beyond Task 1.
5. Negative percent text: a drop must show "-23,1%", not "+-23,1%". Test in Task 1 (`persenUbah`).

---

### Task 1: Web: percent series, chart, title

**Files:**
- Modify: `src/lib/pasar.ts` (replace `geserIndeks` and `ringkasTren` with `ubahSejakDasar`; add `persenUbah`)
- Modify: `src/lib/pasar.test.ts:136-143` (replace the geserIndeks test)
- Modify: `src/app/admin/pasar/GrafikTren.tsx`
- Modify: `src/app/admin/pasar/page.tsx` (chart 3 card; its local `persen` becomes `persenUbah`)

**Interfaces:**
- Produces:
  - `ubahSejakDasar(titik: Titik[]): { dasar: string | null; sama: (number | null)[]; semua: (number | null)[]; ringkas: { sama: number; semua: number } | null }`. Values are fractions (0.1 = +10%). `ringkas` comes from the last point after the base that has both values; it's null when no such point exists.
  - `persenUbah(fraksi: number): string`, which turns 0.1 into "+10,0%", 0 into "0,0%" and −0.231 into "-23,1%".

- [ ] **Step 1: Write the failing tests** (replace the `geserIndeks` test):

```ts
const tt = (tanggal: string, indeks: number | null, median: number | null) =>
  ({ tanggal, indeks_berantai: indeks, median }) as Titik;

test("ubahSejakDasar: kedua garis dari titik pertama yang punya keduanya", () => {
  const r = ubahSejakDasar([tt("a", null, 26000), tt("b", 100, 30000), tt("c", 100, 33000), tt("d", null, null)]);
  expect(r.dasar).toBe("b");
  expect(r.sama).toEqual([null, 0, 0, null]);
  expect(r.semua.map((v) => (v === null ? null : Math.round(v * 1000) / 1000))).toEqual([null, 0, 0.1, null]);
  expect(r.ringkas).toEqual({ sama: 0, semua: expect.closeTo(0.1, 10) });
});

test("ubahSejakDasar: satu titik berdata = tanpa ringkasan; kosong semua = dasar null", () => {
  expect(ubahSejakDasar([tt("a", 100, 30000), tt("b", null, null)]).ringkas).toBeNull();
  const kosong = ubahSejakDasar([tt("a", null, null)]);
  expect([kosong.dasar, kosong.sama, kosong.semua, kosong.ringkas]).toEqual([null, [null], [null], null]);
});

test("persenUbah: tanda plus hanya untuk naik", () => {
  expect([persenUbah(0.1), persenUbah(0), persenUbah(-0.231)]).toEqual(["+10,0%", "0,0%", "-23,1%"]);
});
```

- [ ] **Step 2: Run them.** `powershell.exe -NoProfile -Command "npx vitest run src/lib/pasar.test.ts"`. Expected: FAIL (the functions aren't exported).

- [ ] **Step 3: Implement** both functions in `src/lib/pasar.ts`. Delete `geserIndeks` and `ringkasTren` once nothing imports them.

- [ ] **Step 4: Chart and page.**
  - `GrafikTren` takes `titik: { tanggal: string; sama: number | null; semua: number | null; median: number | null }[]` and `satuan`.
  - Draw `sama` (blue) and `semua` (orange), both in percent.
  - Y ticks use the same format as the chart 3 axis in `GrafikLonjakan` (`v ? persen : "0%"`, on percent numbers).
  - Domain: `[-m, m]` with `m = max(5, ceil(max|v%| × 1.25))`.
  - Add a `ReferenceLine y={0}` with stroke width 2.
  - Tooltip and legend text follow Global Constraints. The median in rupiah uses `rupiah`.
  - `page.tsx`: build the title and the caption from Global Constraints. Use `persenUbah` and drop the page's local `persen`.

- [ ] **Step 5: Verify.**
  - Tests, `npx tsc --noEmit` and `npx eslint src` all pass.
  - On the existing local dev server (:3100, local Supabase), `/admin/pasar` shows the new title. Expect "sejak 7 Nov 2026: produk yang sama 0,0%, semua produk +x,x%". Both lines start at 0%.

- [ ] **Step 6: Commit** the 4 files. Message: "Grafik 3: persen sejak titik pertama, bukan rupiah yang dipaku ke hari terakhir".

### Task 2: Notebook Grafik 3 in percent

**Files:**
- Modify: `data-science/dashboard_contoh.ipynb`: the `grafik_tren` function in cell `8fc6520f`, and the markdown cell that explains Grafik 3 (find it by searching for "produk yang sama").

**Interfaces:**
- Consumes: none. Same rule as Task 1, rewritten in pandas.

- [ ] **Step 1: Rewrite `grafik_tren(d, satuan)`.**
  - Base: `d[["indeks_berantai", "median"]].dropna().index.min()`.
  - Two series × 100.
  - Title: "Grafik 3 · Perubahan harga sejak {dd Mon YYYY}: produk yang sama {+x.x%}, semua produk {+x.x%}", or "Grafik 3 · Perubahan harga" when there are fewer than 2 points.
  - Legend labels from Global Constraints.
  - `ax.axhline(0, linewidth=2)`.
  - Symmetric `ylim` using the same rule as Task 1.
  - Y axis via `matplotlib.ticker.PercentFormatter()`.
  - Update the markdown explanation so it matches the caption.

- [ ] **Step 2: Verify** by running the notebook headless: `cd data-science; .venv/Scripts/python -m jupyter nbconvert --to notebook --execute dashboard_contoh.ipynb --output-dir ../.superpowers/nb-uji`. Expected: no error. Then grep the output for "Perubahan harga sejak". If `jupyter` isn't installed in the venv, exec the cell's code with `MPLBACKEND=Agg` on the warehouse data instead, call `grafik_tren` on the 7–14 Nov `semua` series, and print the title. Leave the committed notebook's saved outputs as they were.

- [ ] **Step 3: Commit** `data-science/dashboard_contoh.ipynb`. Message: "Notebook Grafik 3: persen sejak titik pertama (sama dengan web)".
