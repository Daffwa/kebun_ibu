"use client";

import { Bar, BarChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { rupiah } from "@/lib/format";
import { rupiahRingkas } from "@/lib/pasar";
import { KotakTooltip, SUMBU, TINGGI, WARNA } from "./gaya";

type Kelompok = { dari: number; sampai: number; jumlah: number };

/**
 * Grafik 2: sebaran harga per kg pada satu hari. Sumbu x berupa angka (bukan kategori) supaya
 * garis median dan harga Ibuk jatuh tepat di harganya, bukan di tengah kelompok.
 * Label garis ditulis di atas grafik (bukan di dalam) supaya tidak bertabrakan di layar HP.
 */
export default function GrafikHistogram({
  kelompok,
  median,
  hargaIbuk,
  lebihMurah,
  total,
}: {
  kelompok: Kelompok[];
  median: number;
  hargaIbuk: number;
  lebihMurah: number;
  total: number;
}) {
  const data = kelompok.map((k) => ({ ...k, tengah: (k.dari + k.sampai) / 2 }));
  const batas = [...kelompok.map((k) => k.dari), kelompok[kelompok.length - 1].sampai];
  const kiri = Math.min(batas[0], hargaIbuk - 2_500);
  const kanan = Math.max(batas[batas.length - 1], hargaIbuk + 2_500);

  return (
    <>
      <ul className="mb-3 space-y-1 text-base">
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block h-0.5 w-5 bg-daun-tua" />
          <span>
            Harga Ibuk <strong className="angka">{rupiah(hargaIbuk)}</strong>:{" "}
            <strong className="angka">{lebihMurah}</strong> dari {total} produk lebih murah
          </span>
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: WARNA.redup }} />
          <span>
            Median <strong className="angka">{rupiah(median)}</strong>
          </span>
        </li>
      </ul>
      <BarChart responsive data={data} style={{ width: "100%", height: TINGGI }} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={WARNA.grid} />
        <XAxis
          {...SUMBU}
          dataKey="tengah"
          type="number"
          domain={[kiri, kanan]}
          ticks={batas}
          tickFormatter={rupiahRingkas}
          interval="preserveStartEnd"
        />
        <YAxis {...SUMBU} axisLine={false} allowDecimals={false} width={32} />
        <Tooltip
          cursor={{ fill: WARNA.grid, opacity: 0.5 }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const k = payload[0].payload as Kelompok;
            return (
              <KotakTooltip
                judul={`${rupiah(k.dari)} – ${rupiah(k.sampai)}`}
                baris={[{ warna: WARNA.biru, nama: "produk", nilai: String(k.jumlah), garis: false }]}
              />
            );
          }}
        />
        <Bar dataKey="jumlah" fill={WARNA.biru} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        <ReferenceLine x={median} stroke={WARNA.redup} strokeWidth={2} strokeDasharray="4 3" ifOverflow="extendDomain" />
        <ReferenceLine x={hargaIbuk} stroke={WARNA.tinta} strokeWidth={2} ifOverflow="extendDomain" />
      </BarChart>
    </>
  );
}
