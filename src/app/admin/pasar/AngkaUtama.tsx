import { rupiah } from "@/lib/format";
import { angkaUtama, tanggalPanjang, type Produk } from "@/lib/pasar";

/** Grafik 1: tiga angka utama hari potret. */
export default function AngkaUtama({ snap, tanggal }: { snap: Produk[]; tanggal: string }) {
  const a = angkaUtama(snap);
  const angka = [
    { judul: "Median per kg", nilai: a.median, catatan: "harga tengah pasar" },
    { judul: "Rata-rata per kg", nilai: a.rataRata, catatan: "terseret harga ekstrem" },
    { judul: "Tertimbang terjual", nilai: a.tertimbang, catatan: "perkiraan harga yang dibayar pembeli" },
  ];

  return (
    <section className="mb-4 rounded-[10px] bg-putih p-4">
      <p className="mb-3 text-sm text-daun">
        {tanggalPanjang(tanggal)} · {a.jumlahProduk} produk, {a.jumlahToko} toko
      </p>
      <dl className="grid gap-4 sm:grid-cols-3">
        {angka.map((x) => (
          <div key={x.judul}>
            <dt className="text-daun">{x.judul}</dt>
            <dd className="angka text-3xl font-extrabold text-daun-tua">{x.nilai === null ? "–" : rupiah(x.nilai)}</dd>
            <dd className="text-sm text-daun">{x.catatan}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
