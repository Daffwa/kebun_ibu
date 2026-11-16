import { describe, expect, test } from "vitest";
import fixture from "./pasar.fixture.json";
import {
  angkaUtama,
  bacaFilter,
  geserIndeks,
  histogram,
  kerapatan,
  labelSumbu,
  tanggalPanjang,
  ringkasTren,
  type Produk,
  deret,
  pilihRentang,
  rentangPreset,
  ringkasProduk,
  rentangTeks,
  tanggalTerbuka,
  rupiahRingkas,
  selisihHari,
  statusPreset,
  tambahHari,
  tambahTahun,
  type Filter,
  type HarianBaris,
  type Pasar,
  type Preset,
  type Titik,
} from "./pasar";

type Kasus = { pasar: Pasar; mulai: string; akhir: string; satuan: string; titik: Titik[] };
type DataUji = {
  harian: HarianBaris[];
  status: Record<string, Record<Preset, { terbuka: boolean; pesan: string }>>;
  kasus: Kasus[];
  rentang: { pasar: Pasar; preset: Preset | "semua"; mulai: string; akhir: string }[];
};
const data = fixture.data as unknown as Record<"asli" | "sintetis", DataUji>;

const KOLOM: (keyof Titik)[] = [
  "jumlah_produk", "median", "indeks_berantai", "median_rasio", "naik", "turun", "lonjak_pasar", "berdata",
];

function expectTitikDekat(hasil: Titik, harap: Titik) {
  for (const k of KOLOM) {
    const h = hasil[k] as number | null;
    const e = harap[k] as number | null;
    if (e === null) expect(h, `${harap.tanggal} ${k}`).toBeNull();
    else expect(h, `${harap.tanggal} ${k}`).toBeCloseTo(e, 6);
  }
}

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
  expect(bacaFilter({ dari: "2026-02-30", sampai: ["2026-11-10", "x"] }))
    .toEqual({ pasar: "semua", rentang: "semua", dari: null, sampai: null });
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
    .toEqual({ rentang: "kustom", kosong: "terbalik" });
  expect(pilihRentang(f({ rentang: "kustom", dari: "2026-01-01", sampai: null }), "2026-11-07", "2026-11-14"))
    .toEqual({ rentang: "kustom", mulai: "2026-11-07", akhir: "2026-11-14" });
});

describe.each(["asli", "sintetis"] as const)("sama dengan notebook (%s)", (nama) => {
  const d = data[nama];
  const batas = (pasar: Pasar) => {
    const t = d.harian.filter((h) => h.pasar === pasar).map((h) => h.tanggal).sort();
    return [t[0], t[t.length - 1]] as const;
  };

  test("statusPreset", () => {
    for (const [pasar, harap] of Object.entries(d.status)) {
      expect(statusPreset(...batas(pasar as Pasar))).toEqual(harap);
    }
  });

  test("rentangPreset", () => {
    for (const r of d.rentang) {
      expect(rentangPreset(...batas(r.pasar), r.preset), `${r.pasar} ${r.preset}`).toEqual([r.mulai, r.akhir]);
    }
  });

  test.each(d.kasus.map((k) => [k.pasar, k.mulai, k.akhir, k] as const))("deret %s %s–%s", (pasar, mulai, akhir, k) => {
    const hasil = deret(d.harian.filter((h) => h.pasar === pasar), mulai, akhir);
    expect(hasil.satuan).toBe(k.satuan);
    expect(hasil.titik.map((t) => t.tanggal)).toEqual(k.titik.map((t) => t.tanggal));
    hasil.titik.forEach((t, i) => expectTitikDekat(t, k.titik[i]));
  });
});

const p = (harga: number, terjual: number | null = null, toko = "A") =>
  ({ tanggal: "2026-11-14", sumber: "blibli", produk_key: `${toko}${harga}`, nama_toko: toko,
     harga_per_kg: harga, terjual_min: terjual }) as Produk;

test("angkaUtama: median, rata-rata, jumlah produk dan toko (tanpa tertimbang, dihapus 16 Nov)", () => {
  expect(angkaUtama([p(20000, 10, "A"), p(30000, 30, "B"), p(40000, null, "B")]))
    .toEqual({ median: 30000, rataRata: 30000, jumlahProduk: 3, jumlahToko: 2 });
});

test("histogram: kelompok Rp5.000, kelompok terakhir menutup kanan", () => {
  // Tanpa harga Ibuk (14 Nov): Ibuk bisa menjual lebih dari satu produk Manalagi.
  expect(histogram([20000, 22000, 34999, 40000])).toEqual({
    kelompok: [
      { dari: 20000, sampai: 25000, jumlah: 2 }, { dari: 25000, sampai: 30000, jumlah: 0 },
      { dari: 30000, sampai: 35000, jumlah: 1 }, { dari: 35000, sampai: 40000, jumlah: 1 }],
    median: 28499.5,
    total: 4,
  });
});

test("histogram: satu harga saja tetap satu kelompok", () => {
  expect(histogram([30000, 30000]).kelompok).toEqual([{ dari: 30000, sampai: 35000, jumlah: 2 }]);
});

test("geserIndeks: ujung kanan = median hari terakhir yang punya keduanya", () => {
  const t = (indeks: number | null, median: number | null) => ({ indeks_berantai: indeks, median }) as Titik;
  expect(geserIndeks([t(100, 30000), t(110, 33000), t(null, null)])).toEqual([30000, 33000, null]);
  const r = ringkasTren([30000, 33000, null], ["2026-11-07", "2026-11-08", "2026-11-09"])!;
  expect([r.akhir, r.sejak, r.sampai]).toEqual([33000, "2026-11-07", "2026-11-08"]);
  expect(r.ubah).toBeCloseTo(0.1, 10);
  expect(ringkasTren([null, 33000], ["a", "b"])).toBeNull();
});

test("kerapatan: ≤90 hari per hari, lebih panjang per bulan (tidak ada minggu)", () => {
  expect(kerapatan("2026-11-01", "2026-11-30")).toBe("hari");
  expect(kerapatan("2026-01-01", "2026-03-31")).toBe("hari"); // 90 hari
  expect(kerapatan("2026-01-01", "2026-04-01")).toBe("bulan"); // 91 hari
  expect(kerapatan("2026-01-01", "2026-12-31")).toBe("bulan");
});

test("labelSumbu: hari '14 Nov', bulan 'Nov 2027'", () => {
  expect(labelSumbu("2026-11-14", "hari")).toBe("14 Nov");
  expect(labelSumbu("2027-11-01", "bulan")).toBe("Nov 2027");
  expect(labelSumbu("2027-08-01", "bulan")).toBe("Agu 2027");
});

test("tanggalPanjang", () => {
  expect(tanggalPanjang("2026-11-07")).toBe("7 Nov 2026");
});

test("rupiahRingkas: sumbu ringkas", () => {
  expect([rupiahRingkas(0), rupiahRingkas(500), rupiahRingkas(30000), rupiahRingkas(32500), rupiahRingkas(1_250_000)])
    .toEqual(["0", "500", "30 rb", "32,5 rb", "1,3 jt"]);
});

test("pilihRentang: kustom di luar data pasar ini = 'diluar', bukan 'terbalik'", () => {
  // Blibli 7–7 Nov, lalu pindah ke Tokopedia yang mulai 8 Nov
  const f: Filter = { pasar: "tokopedia", rentang: "kustom", dari: "2026-11-07", sampai: "2026-11-07" };
  expect(pilihRentang(f, "2026-11-08", "2026-11-14")).toEqual({ rentang: "kustom", kosong: "diluar" });
  expect(pilihRentang({ ...f, dari: "2027-01-01", sampai: "2027-02-01" }, "2026-11-08", "2026-11-14"))
    .toEqual({ rentang: "kustom", kosong: "diluar" });
});

test("tanggalTerbuka: hari data terakhir yang membuka preset", () => {
  expect(tanggalTerbuka("2026-11-07", "30h")).toBe("2026-12-06");     // 30 hari data: 7 Nov s/d 6 Des
  expect(tanggalTerbuka("2026-11-07", "1t")).toBe("2027-11-06");
  // cocok dengan statusPreset: sehari sebelumnya terkunci, pada harinya terbuka
  expect(statusPreset("2026-11-07", "2026-12-05")["30h"].terbuka).toBe(false);
  expect(statusPreset("2026-11-07", "2026-12-06")["30h"].terbuka).toBe(true);
});

test("rentangTeks: bulan/tahun yang sama tidak diulang", () => {
  expect(rentangTeks("2026-11-07", "2026-11-14")).toBe("7 – 14 Nov 2026");
  expect(rentangTeks("2026-11-07", "2026-12-03")).toBe("7 Nov – 3 Des 2026");
  expect(rentangTeks("2026-11-07", "2027-01-02")).toBe("7 Nov 2026 – 2 Jan 2027");
  expect(rentangTeks("2026-11-07", "2026-11-07")).toBe("7 Nov 2026");
});

test("ringkasProduk: produk 3 hari dihitung sekali, harga = median, terjual dari hari terakhirnya", () => {
  const b = (produk_key: string, tanggal: string, harga: number, terjual: number | null, nama_toko = "Toko A") =>
    ({ tanggal, sumber: "tokopedia", produk_key, nama_toko, harga_per_kg: harga, terjual_min: terjual }) as Produk;
  const hasil = ringkasProduk([
    b("a", "2026-11-09", 36000, 20),
    b("b", "2026-11-08", 25000, 5, "Toko B"),
    b("a", "2026-11-07", 30000, 10),
    b("a", "2026-11-10", 31000, null), // hari terakhir "a": terjual kosong, bukan 20
  ]);
  expect(hasil).toEqual([
    { tanggal: "2026-11-10", sumber: "tokopedia", produk_key: "a", nama_toko: "Toko A", harga_per_kg: 31000, terjual_min: null },
    { tanggal: "2026-11-08", sumber: "tokopedia", produk_key: "b", nama_toko: "Toko B", harga_per_kg: 25000, terjual_min: 5 },
  ]);
  expect(angkaUtama(hasil)).toEqual({ median: 28000, rataRata: 28000, jumlahProduk: 2, jumlahToko: 2 });
});
