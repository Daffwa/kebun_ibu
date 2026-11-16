import { rupiah } from "@/lib/format";
import { angkaUtama, labelSumbu, tanggalPanjang, type Produk } from "@/lib/pasar";

/** "7 Nov – 14 Nov 2026"; satu hari: "14 Nov 2026"; beda tahun: tanggal lengkap keduanya. */
function judulRentang(mulai: string, akhir: string): string {
  if (mulai === akhir) return tanggalPanjang(akhir);
  if (mulai.slice(0, 4) === akhir.slice(0, 4)) return `${labelSumbu(mulai, "hari")} – ${tanggalPanjang(akhir)}`;
  return `${tanggalPanjang(mulai)} – ${tanggalPanjang(akhir)}`;
}

/** Grafik 1: dua angka utama atas seluruh rentang. `produk` = hasil `ringkasProduk`. */
export default function AngkaUtama({ produk, mulai, akhir }: { produk: Produk[]; mulai: string; akhir: string }) {
  const a = angkaUtama(produk);
  const angka = [
    { judul: "Median per kg", nilai: a.median, catatan: "harga tengah pasar" },
    { judul: "Rata-rata per kg", nilai: a.rataRata, catatan: "terseret harga ekstrem" },
  ];

  return (
    <section className="mb-4 rounded-[10px] bg-putih p-4">
      <p className="mb-3 text-sm text-daun">
        {judulRentang(mulai, akhir)} · {a.jumlahProduk} produk, {a.jumlahToko} toko
      </p>
      <dl className="grid gap-4 sm:grid-cols-2">
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
