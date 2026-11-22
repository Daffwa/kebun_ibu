import Link from "next/link";
import { notFound } from "next/navigation";
import { supabaseServer } from "@/lib/supabase/server";
import { urlFoto } from "@/lib/foto";
import { rupiah, waktuLalu } from "@/lib/format";
import { ambilTertinggiKemarin } from "@/lib/hargaLelang";
import { lelangTerbuka } from "@/lib/lelang";
import { LABEL_JENIS, type ListingLengkap } from "@/lib/types";
import FormPesanan from "./FormPesanan";
import HargaLelang from "./HargaLelang";

export const revalidate = 0;

const BATAS_LELANG_DEMO = "2026-11-20T12:00:00.000Z";
const WAKTU_DEMO = "2026-11-10T00:00:00.000Z";

export default async function DetailListing({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let listing: ListingLengkap | null = null;

  if (id === "demo-mangga-01") {
    listing = {
      id: "demo-mangga-01",
      jenis: "mangga",
      judul: "Mangga Harum Manis 1 Keranjang Super",
      deskripsi: "Dipetik saat matang pohon, getah sudah kering. 1 keranjang isi 12 buah ukuran sedang-besar. Manis legit cocok untuk rujak atau makan langsung.",
      harga: 65000,
      satuan: "/keranjang",
      status: "tersedia",
      mode: "lelang",
      batas_waktu: BATAS_LELANG_DEMO,
      created_at: WAKTU_DEMO,
      listing_foto: [
        { id: "f1", listing_id: "demo-mangga-01", path: "/buah/mangga-keranjang.jpg", urutan: 0 },
        { id: "f2", listing_id: "demo-mangga-01", path: "/buah/mangga-arumanis.jpg", urutan: 1 },
      ],
    };
  } else if (id === "demo-pisang-01") {
    listing = {
      id: "demo-pisang-01",
      jenis: "pisang",
      judul: "Pisang Raja Matang Pohon",
      deskripsi: "Pisang raja manis legit alami, kuning bersih tanpa karbit. Siap makan.",
      harga: 25000,
      satuan: "/sisir",
      status: "tersedia",
      mode: "jual",
      batas_waktu: null,
      created_at: WAKTU_DEMO,
      listing_foto: [
        { id: "f3", listing_id: "demo-pisang-01", path: "/buah/pisang-raja.jpg", urutan: 0 },
      ],
    };
  } else {
    const supabase = await supabaseServer();
    const { data } = await supabase
      .from("listings")
      .select("*, listing_foto(*)")
      .eq("id", id)
      .single();
    listing = data as ListingLengkap | null;
  }

  if (!listing) notFound();
  const foto = [...(listing.listing_foto ?? [])].sort(
    (a, b) => a.urutan - b.urutan,
  );

  const sekarang = new Date();
  const lelang = listing.mode === "lelang";
  const bisaDibeli = lelang
    ? lelangTerbuka(listing, sekarang)
    : listing.status === "tersedia";
  const lelangDitutup = lelang && listing.status === "tersedia" && !bisaDibeli;
  // Lelang yang sudah laku tidak perlu harga lagi; kotak "sudah laku" di
  // bawah sudah cukup.
  const tampilHargaLelang = lelang && listing.status !== "sudah_laku";
  const tertinggi = tampilHargaLelang
    ? (id === "demo-mangga-01" ? 85000 : ((await ambilTertinggiKemarin([listing.id], sekarang))[listing.id] ?? null))
    : null;

  return (
    <main className="mx-auto min-h-dvh w-full max-w-5xl px-4 sm:px-6 lg:px-8 pb-24">
      <nav className="py-5">
        <Link href="/" className="inline-flex items-center gap-1.5 text-base font-semibold text-daun underline transition-transform hover:-translate-x-1">
          ← Kembali ke daftar
        </Link>
      </nav>

      <div className="md:grid md:grid-cols-12 md:gap-10 md:items-start">
        {/* Kolom Kiri: Galeri Foto */}
        <div className="md:col-span-6 lg:col-span-7 md:sticky md:top-6">
          {foto.length > 0 ? (
            <div className="-mx-4 md:mx-0 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 md:px-0 pb-3 md:flex-col md:overflow-visible">
              {foto.map((f) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={f.id}
                  src={urlFoto(f.path)}
                  alt={listing.judul}
                  className="aspect-4/3 w-[88%] md:w-full shrink-0 snap-center rounded-[10px] border-2 border-daun-tua object-cover shadow-sm transition-transform duration-300 hover:scale-[1.01]"
                />
              ))}
            </div>
          ) : (
            <div className="flex aspect-4/3 items-center justify-center rounded-[10px] border-2 border-dashed border-daun-muda bg-putih text-daun-muda shadow-xs">
              Tanpa foto
            </div>
          )}
        </div>

        {/* Kolom Kanan: Rincian Produk & Tindakan */}
        <div className="mt-6 md:mt-0 md:col-span-6 lg:col-span-5">
          <div className="rounded-[14px] border-2 border-daun-tua bg-putih p-5 sm:p-7 shadow-sm">
            <p className="font-semibold text-daun">
              {LABEL_JENIS[listing.jenis]}
              {lelang ? (
                <span className="ml-2 rounded-full bg-emas px-3 py-0.5 text-sm font-extrabold tracking-wide text-daun-tua shadow-xs animasi-pulse-emas">
                  LELANG
                </span>
              ) : null}
            </p>
            <h1 className="mt-2 text-2xl sm:text-3xl font-extrabold text-daun-tua leading-tight">
              {listing.judul}
            </h1>

            {tampilHargaLelang ? (
              <div className="mt-3">
                <HargaLelang
                  hargaMinimum={listing.harga}
                  tertinggi={tertinggi}
                  batas={listing.batas_waktu}
                  satuan={listing.satuan}
                  sekarang={sekarang}
                />
              </div>
            ) : lelang ? null : (
              <p className="angka mt-4 text-3xl sm:text-4xl font-extrabold text-emas-tua">
                {rupiah(listing.harga)}
                <span className="ml-2 text-lg sm:text-xl font-semibold text-daun">
                  {listing.satuan}
                </span>
              </p>
            )}

            {listing.deskripsi ? (
              <p className="mt-5 whitespace-pre-wrap text-base sm:text-lg text-daun-tua/90 border-t border-kertas-tua pt-4 leading-relaxed">
                {listing.deskripsi}
              </p>
            ) : null}

            <p className="mt-4 text-sm text-daun">
              Dipasang {waktuLalu(listing.created_at)}
            </p>

            <div className="mt-6 border-t border-kertas-tua pt-5">
              {bisaDibeli ? (
                <FormPesanan
                  listingId={listing.id}
                  judul={listing.judul}
                  harga={listing.harga}
                  satuan={listing.satuan}
                  jenis={lelang ? "lelang" : "pesan"}
                />
              ) : (
                <div className="rounded-[10px] border-2 border-daun-tua bg-kertas px-4 py-5 text-center">
                  <p className="text-lg font-bold text-daun-tua">
                    {listing.status === "sudah_laku"
                      ? "Barang ini sudah laku."
                      : lelangDitutup
                        ? "Lelang sudah ditutup."
                        : "Belum dibuka."}
                  </p>
                  <p className="mt-2 text-sm text-daun">
                    {listing.status === "sudah_laku"
                      ? "Nanti kalau panen lagi, Ibu kabari di grup keluarga."
                      : lelangDitutup
                        ? "Ibu sedang memilih pemenang. Kalau terpilih, Ibu akan menghubungi lewat WhatsApp."
                        : "Tunggu kabar dari Ibu ya, sebentar lagi dibuka."}
                  </p>
                  <Link
                    href="/"
                    className="mt-4 inline-block min-h-11 rounded-full border-2 border-daun-tua px-5 py-2 text-sm font-bold text-daun-tua transition-colors hover:bg-putih"
                  >
                    Lihat yang lain
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
