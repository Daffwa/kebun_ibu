"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AMBANG_PASAR, AMBANG_TOKO, labelSumbu, tanggalPanjang, type Satuan, type Titik } from "@/lib/pasar";
import { KotakTooltip, SUMBU, WARNA, titikGaris } from "./gaya";

const persen = (v: number) => `${v > 0 ? "+" : ""}${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;

/**
 * Grafik 6: atas = median rasio harga vs 7 hari sebelumnya (pita abu = batas ±5%);
 * bawah = jumlah toko yang naik (merah, ke atas) dan turun (biru, ke bawah).
 * Kedua grafik berbagi sumbu x dan tooltip (`syncId`).
 */
export default function GrafikLonjakan({ titik, satuan }: { titik: Titik[]; satuan: Satuan }) {
  const data = titik.map((t) => ({
    tanggal: t.tanggal,
    ubah: t.median_rasio === null ? null : (t.median_rasio - 1) * 100,
    lonjak: t.lonjak_pasar === 1,
    naik: t.naik,
    turun: t.turun === null ? null : -t.turun,
  }));
  type Baris = (typeof data)[number];

  const ambang = AMBANG_PASAR * 100;
  const batasAtas = Math.ceil(Math.max(ambang * 2, ...data.map((d) => Math.abs(d.ubah ?? 0) * 1.3)));
  const batasBawah = Math.ceil(Math.max(2, ...data.map((d) => Math.max(d.naik ?? 0, -(d.turun ?? 0)) * 1.4)));
  const sedikit = data.length <= 31;
  const judulTooltip = (t: string) => (satuan === "hari" ? tanggalPanjang(t) : `${satuan} ${labelSumbu(t, satuan)}`);
  const xAxis = (tampil: boolean) => (
    <XAxis
      {...SUMBU}
      dataKey="tanggal"
      tickFormatter={(t: string) => labelSumbu(t, satuan)}
      minTickGap={24}
      hide={!tampil}
    />
  );

  return (
    <>
      <LineChart
        responsive
        syncId="lonjakan"
        data={data}
        style={{ width: "100%", height: 220 }}
        margin={{ top: 24, right: 12, left: 0, bottom: 0 }}
      >
        <CartesianGrid vertical={false} stroke={WARNA.grid} />
        {xAxis(false)}
        <YAxis
          {...SUMBU}
          axisLine={false}
          domain={[-batasAtas, batasAtas]}
          tickFormatter={(v: number) => (v ? persen(v) : "0%")}
          width={48}
        />
        <ReferenceArea y1={-ambang} y2={ambang} fill={WARNA.grid} fillOpacity={0.6} stroke="none" />
        <ReferenceLine y={0} stroke={WARNA.sumbu} />
        <Tooltip
          cursor={{ stroke: WARNA.sumbu, strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as Baris;
            return (
              <KotakTooltip
                judul={judulTooltip(String(label))}
                baris={[
                  { warna: WARNA.biru, nama: d.lonjak ? "harga pasar · lonjakan" : "harga pasar", nilai: d.ubah === null ? "–" : persen(d.ubah) },
                  { warna: WARNA.merah, nama: "toko naik", nilai: d.naik === null ? "–" : String(d.naik), garis: false },
                  { warna: WARNA.biru, nama: "toko turun", nilai: d.turun === null ? "–" : String(-d.turun), garis: false },
                ]}
              />
            );
          }}
        />
        <Line
          dataKey="ubah"
          stroke={WARNA.biru}
          strokeWidth={2}
          dot={titikGaris(WARNA.biru, data.length)}
          connectNulls={false}
          isAnimationActive={false}
        >
          <LabelList
            dataKey="ubah"
            content={({ x, y, index, value }) =>
              index !== undefined && data[index].lonjak && typeof value === "number" ? (
                <text x={Number(x)} y={Number(y) - 10} textAnchor="middle" fontSize={13} fontWeight={700} fill={WARNA.tinta}>
                  Lonjakan {persen(value)}
                </text>
              ) : null
            }
          />
        </Line>
      </LineChart>

      <p className="mt-4 mb-1 text-sm text-daun">
        Toko yang berubah ≥{AMBANG_TOKO * 100}% dari harganya sendiri:{" "}
        <span className="inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: WARNA.merah }} /> naik,{" "}
        <span className="inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: WARNA.biru }} /> turun
      </p>
      <BarChart
        responsive
        syncId="lonjakan"
        data={data}
        stackOffset="sign"
        style={{ width: "100%", height: 160 }}
        margin={{ top: 12, right: 12, left: 0, bottom: 0 }}
      >
        <CartesianGrid vertical={false} stroke={WARNA.grid} />
        {xAxis(true)}
        <YAxis
          {...SUMBU}
          axisLine={false}
          allowDecimals={false}
          domain={[-batasBawah, batasBawah]}
          tickFormatter={(v: number) => String(Math.abs(v))}
          width={48}
        />
        <ReferenceLine y={0} stroke={WARNA.sumbu} />
        <Tooltip cursor={{ fill: WARNA.grid, opacity: 0.5 }} content={() => null} />
        <Bar dataKey="naik" stackId="toko" fill={WARNA.merah} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {sedikit && <LabelList dataKey="naik" position="top" fontSize={12} fill={WARNA.tinta2} formatter={(v) => (Number(v) > 0 ? v : "")} />}
        </Bar>
        <Bar dataKey="turun" stackId="toko" fill={WARNA.biru} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
          {sedikit && (
            <LabelList dataKey="turun" position="bottom" fontSize={12} fill={WARNA.tinta2} formatter={(v) => (Number(v) < 0 ? -Number(v) : "")} />
          )}
        </Bar>
      </BarChart>
    </>
  );
}
