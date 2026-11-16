import { expect, test } from "vitest";
import { ambilBatas, ambilDaftarWilayah, ambilHarian, ambilLonjakanHalaman, ambilProdukRentang, ambilSemua } from "./pasarData";

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

/** Klien Supabase palsu: mencatat setiap panggilan builder; setiap query selesai dengan 0 baris dan `count` = `jumlah`. */
const klienPalsu = (jumlah = 0) => {
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
              return (ok: (v: unknown) => unknown) => Promise.resolve({ data: [], error: null, count: jumlah }).then(ok);
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

const panggil = (q: { panggilan: [string, unknown[]][] }, nama: string) =>
  q.panggilan.filter(([n]) => n === nama).map(([, a]) => a);

test("bacaan produk dan lonjakan tanpa wilayah: tanpa saringan kode", async () => {
  const { sb, catatan } = klienPalsu();
  await ambilProdukRentang(sb, "semua", "2026-11-07", "2026-11-14");
  await ambilLonjakanHalaman(sb, { ...LONJAK, pasar: "semua" });
  for (const q of catatan) {
    expect(panggil(q, "in")).toEqual([]);
    expect(panggil(q, "eq").filter((a) => String(a[0]).endsWith("_kode"))).toEqual([]);
  }
});

test("bacaan produk dan lonjakan ikut wilayah: provinsi_kode atau kabkota_kode in kode", async () => {
  const { sb, catatan } = klienPalsu();
  const prov = { kolom: "provinsi_kode" as const, kode: ["35"] };
  const kel = { kolom: "kabkota_kode" as const, kode: ["31.71", "32.76"] };
  await ambilProdukRentang(sb, "blibli", "2026-11-07", "2026-11-14", prov);
  await ambilLonjakanHalaman(sb, { ...LONJAK, pasar: "blibli", wilayah: prov });
  await ambilProdukRentang(sb, "semua", "2026-11-07", "2026-11-14", kel);
  await ambilLonjakanHalaman(sb, { ...LONJAK, pasar: "semua", wilayah: kel });
  // jumlah 0: lonjakan hanya mengirim query hitung, jadi 1 query per panggilan
  expect(catatan.map((q) => q.tabel)).toEqual(Array(4).fill("pasar_manalagi"));
  for (const q of catatan.slice(0, 2)) expect(panggil(q, "in")).toEqual([["provinsi_kode", ["35"]]]);
  for (const q of catatan.slice(2)) expect(panggil(q, "in")).toEqual([["kabkota_kode", ["31.71", "32.76"]]]);
});

const LONJAK = { pasar: "semua" as const, mulai: "2026-11-07", akhir: "2026-11-14", urut: "baru" as const, baris: 10, hal: 1 };

test("lonjakan: 0 baris = hanya hitung, tanpa permintaan range (PostgREST 416)", async () => {
  const { sb, catatan } = klienPalsu(0);
  const r = await ambilLonjakanHalaman(sb, { ...LONJAK, hal: 3 });
  expect(r).toEqual({ daftar: [], jumlah: 0, hal: 1 });
  expect(catatan.flatMap((q) => panggil(q, "range"))).toEqual([]);
});

test("lonjakan: hitung dan halaman memakai saringan yang sama", async () => {
  const { sb, catatan } = klienPalsu(37);
  await ambilLonjakanHalaman(sb, { ...LONJAK, pasar: "tokopedia", wilayah: { kolom: "provinsi_kode", kode: ["35"] } });
  expect(catatan).toHaveLength(2);
  const saring = (q: (typeof catatan)[number]) => q.panggilan.filter(([n]) => ["eq", "gte", "lte", "in"].includes(n));
  expect(saring(catatan[0])).toEqual(saring(catatan[1]));
  expect(panggil(catatan[0], "select")[0][1]).toEqual({ count: "exact", head: true });
});

test("lonjakan: halaman dijepit dan urutan stabil", async () => {
  const { sb, catatan } = klienPalsu(37);
  const r = await ambilLonjakanHalaman(sb, { ...LONJAK, pasar: "blibli", urut: "turun", hal: 9 });
  expect(r.hal).toBe(4);
  expect(r.jumlah).toBe(37);
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

test("lonjakan: urutan naik dan baru; halaman 2 dari 25 baris", async () => {
  const naik = klienPalsu(37);
  await ambilLonjakanHalaman(naik.sb, { ...LONJAK, urut: "naik", baris: 25, hal: 2 });
  expect(panggil(naik.catatan.at(-1)!, "order")[0]).toEqual(["rasio_jendela", { ascending: false, nullsFirst: false }]);
  expect(panggil(naik.catatan.at(-1)!, "range")).toEqual([[25, 49]]);
  const baru = klienPalsu(37);
  await ambilLonjakanHalaman(baru.sb, LONJAK);
  expect(panggil(baru.catatan.at(-1)!, "order")).toEqual([
    ["tanggal", { ascending: false }],
    ["produk_key", { ascending: true }],
  ]);
  expect(panggil(baru.catatan.at(-1)!, "range")).toEqual([[0, 9]]);
});

test("ambilDaftarWilayah: pasar_wilayah untuk pasar terpilih", async () => {
  const { sb, catatan } = klienPalsu();
  await ambilDaftarWilayah(sb, "tokopedia");
  expect(catatan[0].tabel).toBe("pasar_wilayah");
  expect(panggil(catatan[0], "eq")).toEqual([["pasar", "tokopedia"]]);
});
