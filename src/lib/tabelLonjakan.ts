/**
 * Keadaan tabel "Lonjakan toko" di URL /admin/pasar. Tabel berdiri sendiri dari grafik:
 * parameternya berawalan `t_`, dan kedua kelompok saling menjaga parameter kelompok lain.
 * Desain: docs/superpowers/specs/2026-11-14-tabel-lonjakan-design.md
 */
import { bacaFilter, type Filter } from "./pasar";

export type Urut = "baru" | "turun" | "naik";
export type Awalan = "" | "t_";

export const BARIS = [10, 25, 50, 100] as const;

export const NAMA_URUT: Record<Urut, string> = {
  baru: "Tanggal terbaru dulu",
  turun: "Perubahan terendah dulu",
  naik: "Perubahan tertinggi dulu",
};

type Sp = Record<string, string | string[] | undefined>;

/** Parameter saringan grafik (tanpa awalan). Kelompok tabel = semua kunci berawalan `t_`. */
const KUNCI_GRAFIK = ["pasar", "rentang", "wilayah", "dari", "sampai"];

const milikKelompok = (kunci: string, awalan: Awalan) =>
  awalan === "t_" ? kunci.startsWith("t_") : KUNCI_GRAFIK.includes(kunci);

export function bacaTabel(sp: Sp): { filter: Filter; wilayah: string | string[] | undefined; urut: Urut; baris: number; hal: number } {
  const urut = sp.t_urut === "turun" || sp.t_urut === "naik" ? sp.t_urut : "baru";
  const baris = BARIS.find((b) => String(b) === sp.t_baris) ?? 10;
  const hal = typeof sp.t_hal === "string" && /^\d+$/.test(sp.t_hal) && Number(sp.t_hal) >= 1 ? Number(sp.t_hal) : 1;
  return { filter: bacaFilter(sp, "t_"), wilayah: sp.t_wilayah, urut, baris, hal };
}

/**
 * Alamat baru: parameter kelompok `awalan` dibuang lalu diisi dari `grup` (kunci sudah berawalan;
 * nilai undefined = tidak ditulis). Parameter kelompok lain dibiarkan apa adanya.
 */
export function alamatPasar(query: string, awalan: Awalan, grup: Record<string, string | undefined>): string {
  const sekarang = new URLSearchParams(query);
  const p = new URLSearchParams();
  for (const [k, v] of sekarang) if (!milikKelompok(k, awalan)) p.append(k, v);
  for (const [k, v] of Object.entries(grup)) if (v !== undefined) p.set(k, v);
  return `/admin/pasar?${p}`;
}

/** Parameter tabel (`t_*`) yang sedang berlaku, tanpa `t_hal`: dasar tautan halaman dan pengaturan. */
export function paramTabel(query: string): Record<string, string> {
  return Object.fromEntries([...new URLSearchParams(query)].filter(([k]) => k.startsWith("t_") && k !== "t_hal"));
}

/** Isian tersembunyi untuk form Kustom (GET) kelompok `awalan`: semua parameter kelompok lain + `tambahan`. */
export function isianTersembunyi(query: string, awalan: Awalan, tambahan: Record<string, string> = {}): [string, string][] {
  const lain: [string, string][] = [...new URLSearchParams(query)].filter(
    ([k]) => !milikKelompok(k, awalan) && (awalan === "t_" ? KUNCI_GRAFIK.includes(k) : k.startsWith("t_")),
  );
  return [...lain, ...Object.entries(tambahan)];
}

/** Nomor halaman yang ditampilkan: pertama, terakhir, sekarang ±1; celah ≥ 2 halaman = "…". */
export function nomorHalaman(hal: number, total: number): (number | "…")[] {
  const tampil = [...new Set([1, hal - 1, hal, hal + 1, total])].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
  const hasil: (number | "…")[] = [];
  for (const n of tampil) {
    const sebelum = hasil.at(-1);
    if (typeof sebelum === "number" && n - sebelum === 2) hasil.push(sebelum + 1);
    else if (typeof sebelum === "number" && n - sebelum > 2) hasil.push("…");
    hasil.push(n);
  }
  return hasil;
}
