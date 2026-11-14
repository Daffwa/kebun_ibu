/**
 * Membaca tabel dashboard Manalagi untuk /admin/pasar lewat klien sesi pengguna (RLS
 * `is_pengelola()`), bukan service role.
 *
 * Supabase mengembalikan paling banyak 1000 baris per permintaan (`max_rows`), dan memotongnya
 * diam-diam. Maka setiap bacaan yang bisa tumbuh dibaca per halaman lewat `ambilSemua`.
 */
import type { supabaseServer } from "./supabase/server";
import type { HarianBaris, Pasar, Produk } from "./pasar";

type SupabaseClient = Awaited<ReturnType<typeof supabaseServer>>;

export const UKURAN_HALAMAN = 1000;

/**
 * Memanggil `halaman(dari, sampai)` (indeks baris, inklusif, seperti `.range()`) sampai halaman
 * kosong. Maju sebanyak baris yang benar-benar diterima, bukan 1000, dan berhenti hanya pada
 * halaman kosong: kalau `max_rows` server suatu hari diturunkan di bawah 1000, tidak ada baris
 * yang terlewat (biayanya satu permintaan tambahan). Query di dalamnya harus berurutan stabil.
 * Galat di halaman mana pun dilempar: lebih baik halaman error daripada grafik setengah data.
 */
export async function ambilSemua<T>(
  halaman: (dari: number, sampai: number) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>,
): Promise<T[]> {
  const semua: T[] = [];
  for (;;) {
    const dari = semua.length;
    const { data, error } = await halaman(dari, dari + UKURAN_HALAMAN - 1);
    if (error) throw new Error(error.message);
    if (!data || data.length === 0) return semua;
    semua.push(...data);
  }
}

export type Lonjakan = {
  tanggal: string;
  nama_toko: string | null;
  sumber: "blibli" | "tokopedia";
  kota: string | null;
  median_jendela: number | null;
  harga_per_kg: number;
  rasio_jendela: number | null;
};

const KOLOM_HARIAN = "tanggal, pasar, jumlah_produk, median, indeks_berantai, median_rasio, lonjak_pasar, naik, turun";
const KOLOM_PRODUK = "tanggal, sumber, produk_key, nama_toko, kota, harga_per_kg, terjual_min";
const KOLOM_LONJAKAN = "tanggal, nama_toko, sumber, kota, median_jendela, harga_per_kg, rasio_jendela";

function periksa<T>({ data, error }: { data: unknown; error: { message: string } | null }): T {
  if (error) throw new Error(error.message);
  return data as T;
}

/** Tanggal pertama dan terakhir yang berdata untuk pasar ini; null kalau belum ada data. */
export async function ambilBatas(sb: SupabaseClient, pasar: Pasar): Promise<{ awal: string; akhir: string } | null> {
  const ujung = (naik: boolean) =>
    sb.from("pasar_manalagi_harian").select("tanggal").eq("pasar", pasar).order("tanggal", { ascending: naik }).limit(1);
  const [awal, akhir] = (await Promise.all([ujung(true), ujung(false)])).map((r) =>
    periksa<{ tanggal: string }[]>(r),
  );
  if (!awal.length || !akhir.length) return null;
  return { awal: awal[0].tanggal, akhir: akhir[0].tanggal };
}

export async function ambilHarian(sb: SupabaseClient, pasar: Pasar, mulai: string, akhir: string): Promise<HarianBaris[]> {
  return ambilSemua<HarianBaris>((dari, sampai) =>
    sb
      .from("pasar_manalagi_harian")
      .select(KOLOM_HARIAN)
      .eq("pasar", pasar)
      .gte("tanggal", mulai)
      .lte("tanggal", akhir)
      .order("tanggal")
      .range(dari, sampai)
      .overrideTypes<HarianBaris[], { merge: false }>(),
  );
}

/** Semua produk pada satu tanggal (grafik 1 dan 2). */
export async function ambilPotret(sb: SupabaseClient, pasar: Pasar, tanggal: string): Promise<Produk[]> {
  return ambilSemua<Produk>((dari, sampai) => {
    let q = sb.from("pasar_manalagi").select(KOLOM_PRODUK).eq("tanggal", tanggal);
    if (pasar !== "semua") q = q.eq("sumber", pasar);
    return q.order("produk_key").range(dari, sampai).overrideTypes<Produk[], { merge: false }>();
  });
}

/** 20 lonjakan toko terbaru dalam rentang + jumlah seluruhnya. */
export async function ambilLonjakan(
  sb: SupabaseClient,
  pasar: Pasar,
  mulai: string,
  akhir: string,
): Promise<{ daftar: Lonjakan[]; jumlah: number }> {
  let q = sb
    .from("pasar_manalagi")
    .select(KOLOM_LONJAKAN, { count: "exact" })
    .eq("lonjak_toko", true)
    .gte("tanggal", mulai)
    .lte("tanggal", akhir);
  if (pasar !== "semua") q = q.eq("sumber", pasar);
  const hasil = await q.order("tanggal", { ascending: false }).order("produk_key").limit(20);
  const daftar = periksa<Lonjakan[]>(hasil);
  return { daftar, jumlah: hasil.count ?? daftar.length };
}
