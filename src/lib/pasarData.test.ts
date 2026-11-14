import { expect, test } from "vitest";
import { ambilBatas, ambilHarian, ambilSemua } from "./pasarData";

/** Tabel palsu berisi `total` angka 0..total-1; `gagalDi` = nomor panggilan (mulai 0) yang galat. */
const palsu = (total: number, gagalDi = -1, batasServer = Infinity) => {
  const panggilan: [number, number][] = [];
  const halaman = async (dari: number, sampai: number) => {
    panggilan.push([dari, sampai]);
    if (panggilan.length - 1 === gagalDi) return { data: null, error: { message: "putus" } };
    const n = Math.max(0, Math.min(sampai, total - 1, dari + batasServer - 1) - dari + 1);
    return { data: Array.from({ length: n }, (_, i) => dari + i), error: null };
  };
  return { halaman, panggilan };
};

test("2500 baris: 3 halaman berisi + 1 kosong, urutan terjaga", async () => {
  const { halaman, panggilan } = palsu(2500);
  const hasil = await ambilSemua(halaman);
  expect(hasil).toHaveLength(2500);
  expect(hasil[2499]).toBe(2499);
  expect(panggilan).toEqual([[0, 999], [1000, 1999], [2000, 2999], [2500, 3499]]);
});

test("tepat 1000 baris: meminta halaman kedua yang kosong lalu berhenti", async () => {
  const { halaman, panggilan } = palsu(1000);
  expect(await ambilSemua(halaman)).toHaveLength(1000);
  expect(panggilan).toHaveLength(2);
});

test("galat di halaman kedua dilempar, bukan hasil setengah", async () => {
  await expect(ambilSemua(palsu(2500, 1).halaman)).rejects.toThrow("putus");
});

test("server memotong di bawah 1000 (max_rows diturunkan): tidak ada baris hilang", async () => {
  const { halaman } = palsu(1200, -1, 500);
  const hasil = await ambilSemua(halaman);
  expect(hasil).toHaveLength(1200);
  expect(hasil).toEqual(Array.from({ length: 1200 }, (_, i) => i));
});

/** Klien Supabase palsu: mencatat setiap panggilan builder; setiap query selesai dengan 0 baris. */
const klienPalsu = () => {
  const catatan: { tabel: string; panggilan: [string, unknown[]][] }[] = [];
  const sb = {
    from(tabel: string) {
      const q = { tabel, panggilan: [] as [string, unknown[]][] };
      catatan.push(q);
      const builder: unknown = new Proxy(
        {},
        {
          get(_, nama: string) {
            if (nama === "then")
              return (ok: (v: unknown) => unknown) => Promise.resolve({ data: [], error: null, count: 0 }).then(ok);
            return (...args: unknown[]) => {
              q.panggilan.push([nama, args]);
              return builder;
            };
          },
        },
      );
      return builder;
    },
  };
  return { sb: sb as never, catatan };
};

const eqWilayah = (q: { panggilan: [string, unknown[]][] }) =>
  q.panggilan.filter(([n, a]) => n === "eq" && a[0] === "wilayah").map(([, a]) => a[1]);

test("bacaan harian tanpa wilayah memakai wilayah 'semua'", async () => {
  const { sb, catatan } = klienPalsu();
  await ambilBatas(sb, "semua");
  await ambilHarian(sb, "semua", "2026-11-07", "2026-11-14");
  expect(catatan.map((q) => q.tabel)).toEqual(Array(3).fill("pasar_manalagi_harian"));
  for (const q of catatan) expect(eqWilayah(q)).toEqual(["semua"]);
});

test("bacaan harian memakai wilayah terpilih", async () => {
  const { sb, catatan } = klienPalsu();
  await ambilBatas(sb, "blibli", "35");
  await ambilHarian(sb, "blibli", "2026-11-07", "2026-11-14", "35");
  for (const q of catatan) expect(eqWilayah(q)).toEqual(["35"]);
});
