import { expect, test } from "vitest";
import { ambilSemua } from "./pasarData";

/** Tabel palsu berisi `total` angka 0..total-1; `gagalDi` = nomor panggilan (mulai 0) yang galat. */
const palsu = (total: number, gagalDi = -1) => {
  const panggilan: [number, number][] = [];
  const halaman = async (dari: number, sampai: number) => {
    panggilan.push([dari, sampai]);
    if (panggilan.length - 1 === gagalDi) return { data: null, error: { message: "putus" } };
    const n = Math.max(0, Math.min(sampai, total - 1) - dari + 1);
    return { data: Array.from({ length: n }, (_, i) => dari + i), error: null };
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
