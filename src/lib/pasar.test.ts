import { describe, expect, test } from "vitest";
import fixture from "./pasar.fixture.json";
import {
  bacaFilter,
  deret,
  pilihRentang,
  rentangPreset,
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
    .toEqual({ rentang: "kustom", kosong: true });
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
