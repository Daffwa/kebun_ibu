import { rupiah } from "@/lib/format";
import { NAMA_PASAR, tanggalPanjang } from "@/lib/pasar";
import type { Lonjakan } from "@/lib/pasarData";

const persen = (r: number) =>
  `${r > 1 ? "+" : ""}${((r - 1) * 100).toLocaleString("id-ID", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;

/** Tabel toko yang melonjak dalam rentang (20 terbaru). Geser ke samping di HP. */
export default function TabelLonjakan({ daftar, jumlah }: { daftar: Lonjakan[]; jumlah: number }) {
  return (
    <div className="mt-6">
      <h3 className="mb-2 font-bold">
        Lonjakan toko dalam rentang: {jumlah}
        {jumlah > daftar.length ? ` (${daftar.length} terbaru)` : ""}
      </h3>
      {daftar.length === 0 ? (
        <p className="text-daun">Tidak ada toko yang melonjak dalam rentang ini.</p>
      ) : (
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
      )}
    </div>
  );
}
