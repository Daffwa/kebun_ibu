import Link from "next/link";
import { rupiah } from "@/lib/format";
import { NAMA_PASAR, tanggalPanjang, type Pasar, type Preset, type Rentang } from "@/lib/pasar";
import type { Lonjakan } from "@/lib/pasarData";
import { alamatPasar, nomorHalaman, paramTabel, type Urut } from "@/lib/tabelLonjakan";
import type { Wilayah } from "@/lib/wilayah";
import PengaturanTabel from "./PengaturanTabel";
import Saringan from "./Saringan";

const persen = (r: number) =>
  `${r > 1 ? "+" : ""}${((r - 1) * 100).toLocaleString("id-ID", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;

export type PropsTabel = {
  query: string;
  pasar: Pasar;
  rentang: Rentang;
  mulai?: string;
  akhir?: string;
  wilayah: Wilayah | null;
  daftarWilayah: Wilayah[];
  batas: { awal: string; akhir: string } | null;
  status: Record<Preset, { terbuka: boolean; pesan: string }> | null;
  /** Diisi kalau tabel tidak bisa ditampilkan (belum ada data, rentang kosong, 0 lonjakan). */
  pesan: string | null;
  daftar: Lonjakan[];
  jumlah: number;
  hal: number;
  baris: number;
  urut: Urut;
};

const TOMBOL = "inline-flex min-h-11 min-w-11 items-center justify-center rounded-full px-3 font-semibold";

/**
 * Kartu "Lonjakan toko", berdiri sendiri dari grafik: saringan, urutan, baris per halaman, dan
 * halamannya sendiri (parameter `t_*`). Geser ke samping di HP untuk tabelnya saja.
 */
export default function TabelLonjakan(p: PropsTabel) {
  const { query, daftar, jumlah, hal, baris, urut } = p;
  const total = Math.max(1, Math.ceil(jumlah / baris));
  const keHalaman = (n: number) => alamatPasar(query, "t_", { ...paramTabel(query), t_hal: n > 1 ? String(n) : undefined });
  const tambahan = Object.fromEntries(
    Object.entries({ t_urut: urut !== "baru" ? urut : undefined, t_baris: baris !== 10 ? String(baris) : undefined }).filter(
      (e): e is [string, string] => e[1] !== undefined,
    ),
  );

  return (
    <section className="mb-4 rounded-[10px] bg-putih p-4">
      <h2 className="mb-3 text-lg font-bold text-daun-tua">Lonjakan toko: {jumlah}</h2>
      <Saringan
        key={`t-${p.pasar}-${p.wilayah?.wilayah ?? "semua"}-${p.rentang}-${p.mulai}-${p.akhir}`}
        awalan="t_"
        query={query}
        tambahan={tambahan}
        pasar={p.pasar}
        rentang={p.rentang}
        mulai={p.mulai}
        akhir={p.akhir}
        wilayah={p.wilayah}
        daftarWilayah={p.daftarWilayah}
        batas={p.batas}
        status={p.status}
      />
      <PengaturanTabel query={query} urut={urut} baris={baris} />

      {p.pesan ? (
        <p className="text-daun">{p.pesan}</p>
      ) : (
        <>
          <div className="-mx-4 overflow-x-auto px-4">
            <table className="w-full min-w-[640px] text-left text-base">
              <thead className="text-sm text-daun">
                <tr>
                  {["Tanggal", "Toko", "Pasar", "Kota", "Sebelumnya", "Sekarang", "Perubahan"].map((k) => (
                    <th key={k} className="border-b-2 border-kertas-tua py-2 pr-3 font-semibold">
                      {k}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {daftar.map((l, i) => (
                  <tr key={`${l.tanggal}-${i}`} className="border-b border-kertas-tua">
                    <td className="py-2 pr-3 whitespace-nowrap">{tanggalPanjang(l.tanggal)}</td>
                    <td className="py-2 pr-3">{l.nama_toko ?? "–"}</td>
                    <td className="py-2 pr-3">{NAMA_PASAR[l.sumber]}</td>
                    <td className="py-2 pr-3">{l.kota ?? "–"}</td>
                    <td className="angka py-2 pr-3 whitespace-nowrap">{l.median_jendela === null ? "–" : rupiah(l.median_jendela)}</td>
                    <td className="angka py-2 pr-3 whitespace-nowrap">{rupiah(l.harga_per_kg)}</td>
                    <td className="angka py-2 pr-3 font-semibold whitespace-nowrap">{l.rasio_jendela === null ? "–" : persen(l.rasio_jendela)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > 1 && (
            <nav aria-label="Halaman tabel lonjakan" className="mt-3 flex flex-wrap items-center gap-1">
              {hal > 1 && (
                <Link href={keHalaman(hal - 1)} prefetch={false} scroll={false} aria-label="Halaman sebelumnya" className={`${TOMBOL} text-daun-tua`}>
                  ‹
                </Link>
              )}
              {nomorHalaman(hal, total).map((n, i) =>
                n === "…" ? (
                  <span key={`celah-${i}`} className="px-1 text-daun">
                    …
                  </span>
                ) : n === hal ? (
                  <span key={n} aria-current="page" className={`${TOMBOL} bg-daun-tua text-putih`}>
                    {n}
                  </span>
                ) : (
                  <Link key={n} href={keHalaman(n)} prefetch={false} scroll={false} className={`${TOMBOL} text-daun-tua`}>
                    {n}
                  </Link>
                ),
              )}
              {hal < total && (
                <Link href={keHalaman(hal + 1)} prefetch={false} scroll={false} aria-label="Halaman berikutnya" className={`${TOMBOL} text-daun-tua`}>
                  ›
                </Link>
              )}
            </nav>
          )}
        </>
      )}
    </section>
  );
}
