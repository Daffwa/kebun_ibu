import { expect, test } from "vitest";
import { alamatPasar, bacaTabel, isianTersembunyi, nomorHalaman } from "./tabelLonjakan";

const param = (url: string) => new URLSearchParams(url.split("?")[1]);

test("bacaTabel: bawaan dan nilai asing", () => {
  expect(bacaTabel({})).toMatchObject({ urut: "baru", baris: 10, hal: 1, filter: { pasar: "semua", rentang: "semua" } });
  for (const hal of ["0", "-3", "abc", "1.5"]) expect(bacaTabel({ t_hal: hal }).hal).toBe(1);
  expect(bacaTabel({ t_hal: "9999" }).hal).toBe(9999); // dijepit nanti, sesudah jumlah diketahui
  for (const b of ["1000", "abc", "7"]) expect(bacaTabel({ t_baris: b }).baris).toBe(10);
  expect(bacaTabel({ t_baris: "50", t_urut: "turun" })).toMatchObject({ baris: 50, urut: "turun" });
  expect(bacaTabel({ t_urut: "acak" }).urut).toBe("baru");
  expect(bacaTabel({ pasar: "blibli", t_pasar: "tokopedia" }).filter.pasar).toBe("tokopedia");
  expect(bacaTabel({ rentang: "30h" }).filter.rentang).toBe("semua"); // bawaan tidak menyalin grafik
  expect(bacaTabel({ t_rentang: "kustom", t_dari: "2026-11-08", t_sampai: "2026-11-10" }).filter).toEqual({
    pasar: "semua", rentang: "kustom", dari: "2026-11-08", sampai: "2026-11-10",
  });
  expect(bacaTabel({ t_wilayah: "35" }).wilayah).toBe("35");
});

test("alamatPasar: saringan grafik menjaga semua t_*", () => {
  const q = "pasar=semua&rentang=semua&t_pasar=blibli&t_urut=turun&t_hal=3";
  const u = param(alamatPasar(q, "", { pasar: "tokopedia", rentang: "30h" }));
  expect([u.get("pasar"), u.get("t_pasar"), u.get("t_urut"), u.get("t_hal")]).toEqual(["tokopedia", "blibli", "turun", "3"]);
});

test("alamatPasar: kelompok grafik dibuang dulu (wilayah/dari lama tidak tertinggal)", () => {
  const q = "pasar=blibli&rentang=kustom&dari=2026-11-08&sampai=2026-11-10&wilayah=35";
  const u = param(alamatPasar(q, "", { pasar: "blibli", rentang: "semua", wilayah: undefined }));
  expect([...u.keys()]).toEqual(["pasar", "rentang"]);
});

test("alamatPasar: saringan tabel menjaga grafik dan mengulang t_hal", () => {
  const q = "pasar=blibli&wilayah=35&t_pasar=semua&t_hal=4&t_baris=25";
  const url = alamatPasar(q, "t_", { t_pasar: "tokopedia", t_baris: "25" });
  expect(url.startsWith("/admin/pasar?")).toBe(true);
  const u = param(url);
  expect([u.get("pasar"), u.get("wilayah"), u.get("t_pasar"), u.get("t_baris"), u.get("t_hal")]).toEqual([
    "blibli", "35", "tokopedia", "25", null,
  ]);
});

test("isianTersembunyi: form Kustom satu kelompok membawa kelompok lain", () => {
  const q = "pasar=blibli&rentang=kustom&dari=2026-11-08&sampai=2026-11-10&t_pasar=tokopedia&t_urut=naik";
  expect(isianTersembunyi(q, "")).toEqual([
    ["t_pasar", "tokopedia"],
    ["t_urut", "naik"],
  ]);
  expect(isianTersembunyi(q, "t_", { t_baris: "25" })).toEqual([
    ["pasar", "blibli"],
    ["rentang", "kustom"],
    ["dari", "2026-11-08"],
    ["sampai", "2026-11-10"],
    ["t_baris", "25"],
  ]);
});

test("nomorHalaman", () => {
  expect(nomorHalaman(1, 1)).toEqual([1]);
  expect(nomorHalaman(1, 4)).toEqual([1, 2, 3, 4]);
  expect(nomorHalaman(5, 9)).toEqual([1, "…", 4, 5, 6, "…", 9]);
  expect(nomorHalaman(1, 9)).toEqual([1, 2, "…", 9]);
  expect(nomorHalaman(3, 9)).toEqual([1, 2, 3, 4, "…", 9]); // celah satu halaman ditulis angkanya
});
