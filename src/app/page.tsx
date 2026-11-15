import Image from "next/image";
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { ambilTertinggiKemarin } from "@/lib/hargaLelang";
import { lelangTerbuka } from "@/lib/lelang";
import DaftarBarangPublik from "./DaftarBarangPublik";
import type { ListingLengkap, Pengaturan } from "@/lib/types";

export const revalidate = 0;

const BATAS_LELANG_DEMO = "2026-11-20T12:00:00.000Z";
const WAKTU_DEMO_1 = "2026-11-10T00:00:00.000Z";
const WAKTU_DEMO_2 = "2026-11-09T18:00:00.000Z";
const WAKTU_DEMO_3 = "2026-11-08T10:00:00.000Z";

async function denganTimeout<T>(janji: PromiseLike<T>, batasMs = 1500): Promise<T | null> {
  return Promise.race([
    Promise.resolve(janji),
    new Promise<null>((resolve) => setTimeout(() => resolve(null), batasMs)),
  ]).catch(() => null);
}

export default async function Beranda() {
  const supabase = await supabaseServer();

  const [hasilListings, hasilPengaturan] = await Promise.all([
    denganTimeout(
      supabase
        .from("listings")
        .select("*, listing_foto(*)")
        .order("created_at", { ascending: false }),
    ),
    denganTimeout(
      supabase.from("pengaturan").select("*").eq("id", 1).single(),
    ),
  ]);

  const listings = hasilListings?.data;
  const pengaturan = hasilPengaturan?.data;

  let daftar = (listings ?? []) as ListingLengkap[];
  let setelan = pengaturan as Pengaturan | null;

  // Fallback data demo untuk peninjauan UI/UX lokal jika database belum terhubung
  if (daftar.length === 0) {
    setelan = setelan ?? {
      id: 1,
      teks_musim: "🌿 Musim Mangga Harum Manis 2026 dibuka! Panen segar dari kebun sendiri.",
      tampilkan_banner: true,
    };
    daftar = [
      {
        id: "demo-mangga-01",
        jenis: "mangga",
        judul: "Mangga Harum Manis 1 Keranjang Super",
        deskripsi: "Manis legit dipetik saat tua di pohon. 1 keranjang isi 12 buah pilihan.",
        harga: 65000,
        satuan: "/keranjang",
        status: "tersedia",
        mode: "lelang",
        batas_waktu: BATAS_LELANG_DEMO,
        created_at: WAKTU_DEMO_1,
        listing_foto: [
          { id: "f1", listing_id: "demo-mangga-01", path: "/buah/mangga-keranjang.jpg", urutan: 0 },
          { id: "f2", listing_id: "demo-mangga-01", path: "/buah/mangga-arumanis.jpg", urutan: 1 },
        ],
      },
      {
        id: "demo-pisang-01",
        jenis: "pisang",
        judul: "Pisang Raja Matang Pohon",
        deskripsi: "Pisang raja manis legit alami, kuning bersih tanpa karbit.",
        harga: 25000,
        satuan: "/sisir",
        status: "tersedia",
        mode: "jual",
        batas_waktu: null,
        created_at: WAKTU_DEMO_2,
        listing_foto: [
          { id: "f3", listing_id: "demo-pisang-01", path: "/buah/pisang-raja.jpg", urutan: 0 },
        ],
      },
      {
        id: "demo-mangga-02",
        jenis: "mangga",
        judul: "Mangga Manalagi Renyah Gurih",
        deskripsi: "Renyah manis segar, cocok buat rujak keluarga.",
        harga: 40000,
        satuan: "/kantong",
        status: "sudah_laku",
        mode: "jual",
        batas_waktu: null,
        created_at: WAKTU_DEMO_3,
        listing_foto: [
          { id: "f4", listing_id: "demo-mangga-02", path: "/buah/mangga-manalagi.jpg", urutan: 0 },
        ],
      },
    ];
  }

  const sekarang = new Date();
  const idLelangDb = daftar
    .filter((l) => l.mode === "lelang" && !l.id.startsWith("demo-"))
    .map((l) => l.id);
  const rawTertinggi =
    idLelangDb.length > 0
      ? await ambilTertinggiKemarin(idLelangDb, sekarang)
      : {};
  const tertinggi = {
    "demo-mangga-01": 85000,
    ...rawTertinggi,
  };
  const adaYangDijual = daftar.some((l) =>
    l.mode === "lelang" ? lelangTerbuka(l, sekarang) : l.status === "tersedia",
  );

  return (
    <main className="mx-auto min-h-dvh w-full max-w-5xl px-4 sm:px-6 lg:px-8 pb-24">
      <header className="pt-8 pb-6 text-center">
        <h1>
          <Image
            src="/logo.png"
            alt="Kebun Ibu"
            width={240}
            height={288}
            preload
            className="mx-auto h-auto w-48 sm:w-56 md:w-64 transition-transform hover:scale-105 duration-300"
          />
        </h1>
        <p className="mt-3 text-lg md:text-xl font-medium text-daun">
          Mangga dan pisang, dipetik sendiri, dijual ke keluarga.
        </p>
      </header>

      {setelan?.tampilkan_banner && setelan.teks_musim ? (
        <div className="papan mb-8 rounded-[12px] bg-daun-tua px-6 py-4 text-putih shadow-sm">
          <p className="text-lg md:text-xl font-semibold text-center">{setelan.teks_musim}</p>
        </div>
      ) : null}

      {daftar.length === 0 ? (
        <KosongTotal />
      ) : (
        <>
          {!adaYangDijual ? (
            <p className="mb-6 rounded-[10px] border-2 border-kertas-tua bg-putih px-5 py-4">
              Belum ada yang dijual sekarang. Yang di bawah ini sudah laku —
              nanti kalau panen lagi, Ibu kabari di grup.
            </p>
          ) : null}

          <DaftarBarangPublik
            daftar={daftar}
            tertinggi={tertinggi}
            sekarang={sekarang.toISOString()}
          />
        </>
      )}

      <footer className="mt-16 border-t-2 border-kertas-tua pt-5">
        <Link href="/admin" className="text-base text-daun underline">
          Masuk sebagai penjual
        </Link>
      </footer>
    </main>
  );
}

function KosongTotal() {
  return (
    <div className="rounded-[10px] border-2 border-dashed border-daun-muda bg-putih px-6 py-12 text-center">
      <p className="text-xl font-semibold">Belum ada barang yang dipasang.</p>
      <p className="mt-2 text-daun">
        Kalau panen sudah siap, barangnya akan muncul di sini.
      </p>
    </div>
  );
}
