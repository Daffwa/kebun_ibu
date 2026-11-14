/**
 * Filter wilayah /admin/pasar: daftar dari tabel `pasar_wilayah`, pencarian kotak cari, dan
 * saringan baris `pasar_manalagi`. Desain: docs/superpowers/specs/2026-11-14-filter-wilayah-design.md.
 */

export type Tingkat = "kelompok" | "provinsi" | "kabkota";

/** Satu baris `pasar_wilayah` untuk pasar terpilih. "semua" tidak ada di tabel; di sini = null. */
export type Wilayah = {
  wilayah: string;
  nama: string;
  tingkat: Tingkat;
  provinsi_kode: string | null;
  kata_kunci: string | null;
  jumlah_toko: number;
};

/**
 * Anggota kelompok (kode kab/kota Kepmendagri). Salinan `KELOMPOK` di
 * `data-science/transform/wilayah.py`, karena `pasar_wilayah` tidak menyimpan anggota. Uji
 * `wilayah.test.ts` membaca berkas Python itu dan gagal kalau keduanya berbeda.
 */
export const KELOMPOK: Record<string, readonly string[]> = {
  jabodetabek: [
    "31.01", "31.71", "31.72", "31.73", "31.74", "31.75", // DKI Jakarta
    "32.01", "32.71", "32.76", "32.16", "32.75", // Bogor, Depok, Bekasi
    "36.03", "36.71", "36.74", // Tangerang, Tangerang Selatan
  ],
};

const TINGKAT_TEKS: Record<Tingkat, string> = { kelompok: "kelompok", provinsi: "provinsi", kabkota: "kab/kota" };

const urutToko = (a: Wilayah, b: Wilayah) => b.jumlah_toko - a.jumlah_toko || a.nama.localeCompare(b.nama, "id");

/** Isi daftar saat kotak cari diklik tanpa teks: provinsi dengan toko terbanyak. */
export function teratas(daftar: Wilayah[], n = 5): Wilayah[] {
  return daftar.filter((w) => w.tingkat === "provinsi").sort(urutToko).slice(0, n);
}

/**
 * Cocok sebagian tanpa beda huruf besar/kecil pada nama dan kata kunci, di semua tingkat.
 * Urutan: yang cocok di awal kata dulu, lalu toko terbanyak, lalu nama. Teks kosong = `teratas`.
 */
export function cariWilayah(daftar: Wilayah[], teks: string, n = 10): Wilayah[] {
  const t = teks.trim().toLowerCase().replace(/\s+/g, " ");
  if (!t) return teratas(daftar);
  const skor = (w: Wilayah): number | null => {
    const isi = `${w.nama} ${w.kata_kunci ?? ""}`.toLowerCase();
    if (!isi.includes(t)) return null;
    return isi.startsWith(t) || isi.split(" ").some((kata) => kata.startsWith(t)) ? 0 : 1;
  };
  return daftar
    .map((w) => ({ w, s: skor(w) }))
    .filter((x): x is { w: Wilayah; s: number } => x.s !== null)
    .sort((a, b) => a.s - b.s || urutToko(a.w, b.w))
    .slice(0, n)
    .map((x) => x.w);
}

/** "Jawa Timur · provinsi · 7 toko". */
export function labelWilayah(w: Wilayah): string {
  return `${w.nama} · ${TINGKAT_TEKS[w.tingkat]} · ${w.jumlah_toko} toko`;
}

/** `?wilayah=` dari URL. Hanya wilayah yang ada di daftar pasar ini yang sah; lainnya = semua (null). */
export function pilihWilayah(nilai: string | string[] | undefined, daftar: Wilayah[]): Wilayah | null {
  if (typeof nilai !== "string") return null;
  return daftar.find((w) => w.wilayah === nilai) ?? null;
}

/** Kolom dan kode untuk menyaring `pasar_manalagi`; null = semua wilayah (tanpa saringan). */
export function saringanProduk(w: Wilayah | null): { kolom: "provinsi_kode" | "kabkota_kode"; kode: string[] } | null {
  if (!w) return null;
  if (w.tingkat === "provinsi") return { kolom: "provinsi_kode", kode: [w.wilayah] };
  if (w.tingkat === "kabkota") return { kolom: "kabkota_kode", kode: [w.wilayah] };
  const anggota = KELOMPOK[w.wilayah];
  if (!anggota) throw new Error(`Kelompok "${w.wilayah}" belum ada di KELOMPOK (src/lib/wilayah.ts); samakan dengan transform/wilayah.py.`);
  return { kolom: "kabkota_kode", kode: [...anggota] };
}
