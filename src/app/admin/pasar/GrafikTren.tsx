"use client";

import { CartesianGrid, Legend, Line, LineChart, Tooltip, XAxis, YAxis } from "recharts";
import { rupiah } from "@/lib/format";
import { labelSumbu, rupiahRingkas, tanggalPanjang, type Satuan } from "@/lib/pasar";
import { KotakTooltip, SUMBU, TINGGI, WARNA, titikGaris } from "./gaya";

type TitikTren = { tanggal: string; indeks: number | null; median: number | null };

const SERI = [
  { kunci: "indeks", nama: "Produk yang sama (ujung = median terakhir)", warna: WARNA.biru },
  { kunci: "median", nama: "Median semua produk", warna: WARNA.oranye },
] as const;

/** Grafik 3. Hari/periode tanpa data tetap kosong: garisnya putus, tidak disambung. */
export default function GrafikTren({ titik, satuan }: { titik: TitikTren[]; satuan: Satuan }) {
  const tertinggi = Math.max(0, ...titik.flatMap((t) => [t.indeks ?? 0, t.median ?? 0]));

  return (
    <LineChart responsive data={titik} style={{ width: "100%", height: TINGGI }} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
      <CartesianGrid vertical={false} stroke={WARNA.grid} />
      <XAxis {...SUMBU} dataKey="tanggal" tickFormatter={(t: string) => labelSumbu(t, satuan)} minTickGap={24} />
      <YAxis
        {...SUMBU}
        axisLine={false}
        domain={[0, Math.ceil((tertinggi * 1.25) / 5_000) * 5_000 || 5_000]}
        tickFormatter={rupiahRingkas}
        width={48}
      />
      <Tooltip
        cursor={{ stroke: WARNA.sumbu, strokeWidth: 1 }}
        content={({ active, payload, label }) => {
          if (!active || !payload?.length) return null;
          const t = payload[0].payload as TitikTren;
          return (
            <KotakTooltip
              judul={satuan === "hari" ? tanggalPanjang(String(label)) : `${satuan} ${labelSumbu(String(label), satuan)}`}
              baris={SERI.map((s) => ({ warna: s.warna, nama: s.nama, nilai: t[s.kunci] === null ? "–" : rupiah(t[s.kunci]!) }))}
            />
          );
        }}
      />
      <Legend
        iconType="plainline"
        verticalAlign="bottom"
        wrapperStyle={{ fontSize: 14 }}
        formatter={(nama) => <span style={{ color: WARNA.tinta2 }}>{nama}</span>}
      />
      {SERI.map((s) => (
        <Line
          key={s.kunci}
          dataKey={s.kunci}
          name={s.nama}
          stroke={s.warna}
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          dot={titikGaris(s.warna, titik.length)}
          activeDot={{ r: 5, stroke: WARNA.permukaan, strokeWidth: 2 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      ))}
    </LineChart>
  );
}
