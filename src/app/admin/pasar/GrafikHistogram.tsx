"use client";

import { Bar, BarChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from "recharts";
import { rupiah } from "@/lib/format";
import { rupiahRingkas } from "@/lib/pasar";
import { KotakTooltip, SUMBU, TINGGI, WARNA } from "./gaya";

type Kelompok = { dari: number; sampai: number; jumlah: number };

/**
 * Grafik 2: sebaran harga per kg pada satu hari. Sumbu x berupa angka (bukan kategori) supaya
 * garis median jatuh tepat di harganya, bukan di tengah kelompok. Labelnya ditulis di atas
 * grafik (bukan di dalam) supaya tidak bertabrakan di layar HP.
 * Tanpa garis harga Ibuk (diputuskan 14 Nov): Ibuk bisa menjual lebih dari satu produk
 * Manalagi, jadi satu garis harga akan menyesatkan.
 */
export default function GrafikHistogram({
  kelompok,
  median,
  total,
}: {
  kelompok: Kelompok[];
  median: number;
  total: number;
}) {
  const data = kelompok.map((k) => ({ ...k, tengah: (k.dari + k.sampai) / 2 }));
  const batas = [...kelompok.map((k) => k.dari), kelompok[kelompok.length - 1].sampai];

  return (
    <>
      <p className="mb-3 flex items-center gap-2 text-base">
        <span aria-hidden className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: WARNA.redup }} />
        <span>
          Median <strong className="angka">{rupiah(median)}</strong> dari {total} produk
        </span>
      </p>
      <BarChart responsive data={data} style={{ width: "100%", height: TINGGI }} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={WARNA.grid} />
        <XAxis
          {...SUMBU}
          dataKey="tengah"
          type="number"
          domain={[batas[0], batas[batas.length - 1]]}
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
      </BarChart>
    </>
  );
}
