import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "vitest";
import { KELOMPOK, cariWilayah, labelWilayah, pilihWilayah, saringanProduk, teratas, type Wilayah } from "./wilayah";

const w = (wilayah: string, nama: string, tingkat: Wilayah["tingkat"], jumlah_toko: number, kata_kunci: string | null = null): Wilayah => ({
  wilayah,
  nama,
  tingkat,
  provinsi_kode: tingkat === "kabkota" ? wilayah.slice(0, 2) : null,
  kata_kunci,
  jumlah_toko,
});

const DAFTAR: Wilayah[] = [
  w("jabodetabek", "Jabodetabek", "kelompok", 23),
  w("31", "DKI Jakarta", "provinsi", 12, "dki jakarta"),
  w("32", "Jawa Barat", "provinsi", 9, "jabar"),
  w("33", "Jawa Tengah", "provinsi", 3, "jateng"),
  w("35", "Jawa Timur", "provinsi", 7, "jatim"),
  w("36", "Banten", "provinsi", 4, "banten"),
  w("51", "Bali", "provinsi", 4, "bali"),
  w("63", "Kalimantan Selatan", "provinsi", 1, "kalsel"),
  w("32.01", "Kabupaten Bogor", "kabkota", 2),
  w("32.71", "Kota Bogor", "kabkota", 3),
  w("35.78", "Kota Surabaya", "kabkota", 5),
  w("63.72", "Kota Banjarbaru", "kabkota", 20),
];

test("KELOMPOK sama dengan kamus Python (transform/wilayah.py)", () => {
  const py = readFileSync(join(process.cwd(), "data-science/transform/wilayah.py"), "utf8");
  const blok = py.slice(py.indexOf("KELOMPOK:"), py.indexOf("\n}\n", py.indexOf("KELOMPOK:")));
  const dariPy: Record<string, string[]> = {};
  for (const m of blok.matchAll(/"([a-z]+)": \("[^"]+", frozenset\(\{([^}]*)\}\)\)/g))
    dariPy[m[1]] = [...m[2].matchAll(/"(\d{2}\.\d{2})"/g)].map((x) => x[1]).sort();
  expect(Object.keys(dariPy)).not.toHaveLength(0);
  expect(Object.fromEntries(Object.entries(KELOMPOK).map(([k, v]) => [k, [...v].sort()]))).toEqual(dariPy);
});

test("teratas: 5 provinsi dengan toko terbanyak; seri diurutkan nama", () => {
  expect(teratas(DAFTAR).map((x) => x.nama)).toEqual(["DKI Jakarta", "Jawa Barat", "Jawa Timur", "Bali", "Banten"]);
});

test("cariWilayah: kosong atau spasi saja = 5 provinsi teratas", () => {
  expect(cariWilayah(DAFTAR, "")).toEqual(teratas(DAFTAR));
  expect(cariWilayah(DAFTAR, "   ")).toEqual(teratas(DAFTAR));
});

test("cariWilayah: cocok sebagian, tanpa beda huruf besar/kecil, termasuk kata kunci", () => {
  expect(cariWilayah(DAFTAR, "jatim").map((x) => x.wilayah)).toEqual(["35"]);
  expect(cariWilayah(DAFTAR, "BOGOR").map((x) => x.nama)).toEqual(["Kota Bogor", "Kabupaten Bogor"]);
  expect(cariWilayah(DAFTAR, "sura").map((x) => x.nama)).toEqual(["Kota Surabaya"]);
  expect(cariWilayah(DAFTAR, "jabo").map((x) => x.nama)).toEqual(["Jabodetabek"]);
  expect(cariWilayah(DAFTAR, "zzz")).toEqual([]);
});

test("cariWilayah: awal kata didahulukan dari tengah kata, lalu toko terbanyak", () => {
  // "Kota Banjarbaru" punya toko terbanyak, tetapi "bar" ada di tengah katanya.
  expect(cariWilayah(DAFTAR, "bar").map((x) => x.nama)).toEqual(["Jawa Barat", "Kota Banjarbaru"]);
});

test("cariWilayah: paling banyak 10 hasil", () => {
  const banyak = Array.from({ length: 15 }, (_, i) => w(`35.${10 + i}`, `Kota Uji ${i}`, "kabkota", i));
  expect(cariWilayah(banyak, "uji")).toHaveLength(10);
});

test("labelWilayah", () => {
  expect(labelWilayah(DAFTAR[4])).toBe("Jawa Timur · provinsi · 7 toko");
  expect(labelWilayah(DAFTAR[10])).toBe("Kota Surabaya · kab/kota · 5 toko");
  expect(labelWilayah(DAFTAR[0])).toBe("Jabodetabek · kelompok · 23 toko");
});

test("pilihWilayah: hanya wilayah yang ada di daftar pasar ini; lainnya = semua (null)", () => {
  expect(pilihWilayah("35", DAFTAR)?.nama).toBe("Jawa Timur");
  expect(pilihWilayah("99", DAFTAR)).toBeNull();
  expect(pilihWilayah("semua", DAFTAR)).toBeNull();
  expect(pilihWilayah(undefined, DAFTAR)).toBeNull();
  expect(pilihWilayah(["35", "32"], DAFTAR)).toBeNull();
});

test("saringanProduk: kolom dan kode untuk setiap tingkat", () => {
  expect(saringanProduk(null)).toBeNull();
  expect(saringanProduk(DAFTAR[4])).toEqual({ kolom: "provinsi_kode", kode: ["35"] });
  expect(saringanProduk(DAFTAR[10])).toEqual({ kolom: "kabkota_kode", kode: ["35.78"] });
  expect(saringanProduk(DAFTAR[0])).toEqual({ kolom: "kabkota_kode", kode: [...KELOMPOK.jabodetabek] });
});

test("saringanProduk: kelompok yang belum dikenal web = galat, bukan diam-diam kosong", () => {
  expect(() => saringanProduk(w("gerbangkertosusila", "Gerbangkertosusila", "kelompok", 3))).toThrow(/KELOMPOK/);
});
