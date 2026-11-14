/**
 * Membaca tabel dashboard Manalagi untuk /admin/pasar lewat klien sesi pengguna (RLS
 * `is_pengelola()`), bukan service role.
 *
 * Supabase mengembalikan paling banyak 1000 baris per permintaan (`max_rows`), dan memotongnya
 * diam-diam. Maka setiap bacaan yang bisa tumbuh dibaca per halaman lewat `ambilSemua`.
 */
import type { supabaseServer } from "./supabase/server";
import type { HarianBaris, Pasar, Produk } from "./pasar";
import type { Urut } from "./tabelLonjakan";
import type { Wilayah, saringanProduk } from "./wilayah";

type SupabaseClient = Awaited<ReturnType<typeof supabaseServer>>;
/** Hasil `saringanProduk`; null/tidak diisi = semua wilayah. */
type SaringanProduk = ReturnType<typeof saringanProduk>;

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
const KOLOM_PRODUK = "tanggal, produk_key, sumber, nama_toko, harga_per_kg, terjual_min";
const KOLOM_WILAYAH = "wilayah, nama, tingkat, provinsi_kode, kata_kunci, jumlah_toko";
const KOLOM_LONJAKAN = "tanggal, nama_toko, sumber, kota, median_jendela, harga_per_kg, rasio_jendela";

function periksa<T>({ data, error }: { data: unknown; error: { message: string } | null }): T {
  if (error) throw new Error(error.message);
  return data as T;
}

/**
 * Tanggal pertama dan terakhir yang berdata untuk pasar dan wilayah ini; null kalau belum ada data.
 * Setiap bacaan `pasar_manalagi_harian` wajib menyaring `wilayah`: tabel itu menyimpan satu deret
 * per wilayah, jadi tanpa saringan deret semua wilayah tercampur.
 */
export async function ambilBatas(
  sb: SupabaseClient,
  pasar: Pasar,
  wilayah = "semua",
): Promise<{ awal: string; akhir: string } | null> {
  const ujung = (naik: boolean) =>
    sb
      .from("pasar_manalagi_harian")
      .select("tanggal")
      .eq("pasar", pasar)
      .eq("wilayah", wilayah)
      .order("tanggal", { ascending: naik })
      .limit(1);
  const [awal, akhir] = (await Promise.all([ujung(true), ujung(false)])).map((r) =>
    periksa<{ tanggal: string }[]>(r),
  );
  if (!awal.length || !akhir.length) return null;
  return { awal: awal[0].tanggal, akhir: akhir[0].tanggal };
}

export async function ambilHarian(
  sb: SupabaseClient,
  pasar: Pasar,
  mulai: string,
  akhir: string,
  wilayah = "semua",
): Promise<HarianBaris[]> {
  return ambilSemua<HarianBaris>((dari, sampai) =>
    sb
      .from("pasar_manalagi_harian")
      .select(KOLOM_HARIAN)
      .eq("pasar", pasar)
      .eq("wilayah", wilayah)
      .gte("tanggal", mulai)
      .lte("tanggal", akhir)
      .order("tanggal")
      .range(dari, sampai)
      .overrideTypes<HarianBaris[], { merge: false }>(),
  );
}

/** Daftar wilayah kotak cari untuk pasar ini (±200 baris, tetap dibaca per halaman). */
export async function ambilDaftarWilayah(sb: SupabaseClient, pasar: Pasar): Promise<Wilayah[]> {
  return ambilSemua<Wilayah>((dari, sampai) =>
    sb
      .from("pasar_wilayah")
      .select(KOLOM_WILAYAH)
      .eq("pasar", pasar)
      .order("wilayah")
      .range(dari, sampai)
      .overrideTypes<Wilayah[], { merge: false }>(),
  );
}

/** Semua baris produk dalam rentang (grafik 1 dan 2; diringkas dengan `ringkasProduk`). */
export async function ambilProdukRentang(
  sb: SupabaseClient,
  pasar: Pasar,
  mulai: string,
  akhir: string,
  wilayah?: SaringanProduk,
): Promise<Produk[]> {
  return ambilSemua<Produk>((dari, sampai) => {
    let q = sb.from("pasar_manalagi").select(KOLOM_PRODUK).gte("tanggal", mulai).lte("tanggal", akhir);
    if (pasar !== "semua") q = q.eq("sumber", pasar);
    if (wilayah) q = q.in(wilayah.kolom, wilayah.kode);
    return q.order("tanggal").order("produk_key").range(dari, sampai).overrideTypes<Produk[], { merge: false }>();
  });
}

/**
 * Satu halaman tabel lonjakan toko. Dihitung dulu (`head`), lalu halaman dijepit ke halaman
 * terakhir: PostgREST menjawab offset di luar data dengan galat 416 (PGRST103), bukan daftar kosong.
 * Urutan stabil: urutan pilihan, lalu tanggal terbaru, lalu `produk_key` (kunci utama = tanggal, produk_key).
 */
export async function ambilLonjakanHalaman(
  sb: SupabaseClient,
  q: { pasar: Pasar; mulai: string; akhir: string; wilayah?: SaringanProduk; urut: Urut; baris: number; hal: number },
): Promise<{ daftar: Lonjakan[]; jumlah: number; hal: number }> {
  const saring = (kolom: string, opsi?: { count: "exact"; head: true }) => {
    let b = sb.from("pasar_manalagi").select(kolom, opsi).eq("lonjak_toko", true).gte("tanggal", q.mulai).lte("tanggal", q.akhir);
    if (q.pasar !== "semua") b = b.eq("sumber", q.pasar);
    if (q.wilayah) b = b.in(q.wilayah.kolom, q.wilayah.kode);
    return b;
  };
  const hitung = await saring("tanggal", { count: "exact", head: true });
  if (hitung.error) throw new Error(hitung.error.message);
  const jumlah = hitung.count ?? 0;
  const hal = Math.min(Math.max(q.hal, 1), Math.max(1, Math.ceil(jumlah / q.baris)));
  if (jumlah === 0) return { daftar: [], jumlah, hal };

  let b = saring(KOLOM_LONJAKAN);
  if (q.urut !== "baru") b = b.order("rasio_jendela", { ascending: q.urut === "turun", nullsFirst: false });
  const hasil = await b
    .order("tanggal", { ascending: false })
    .order("produk_key", { ascending: true })
    .range((hal - 1) * q.baris, hal * q.baris - 1);
  return { daftar: periksa<Lonjakan[]>(hasil), jumlah, hal };
}
