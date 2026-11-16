"use client";

/**
 * Warna dan potongan bersama grafik /admin/pasar. Palet sama dengan notebook
 * (lolos validator dataviz di mode terang). Teks memakai tinta situs, bukan warna seri.
 */
export const WARNA = {
  biru: "#2a78d6",
  oranye: "#eb6834",
  merah: "#e34948",
  grid: "#e1e0d9",
  sumbu: "#c3c2b7",
  redup: "#898781",
  tinta: "#17392a", // --color-daun-tua
  tinta2: "#2d6a4f", // --color-daun
  permukaan: "#ffffff",
};

export const TINGGI = 260;

export const SUMBU = {
  stroke: WARNA.sumbu,
  tick: { fill: WARNA.redup, fontSize: 13 },
  tickLine: false,
} as const;

export type BarisTooltip = { warna: string; nama: string; nilai: string; garis?: boolean };

/** Isi tooltip: nilai tebal di depan, nama seri sesudahnya, kunci berupa garis pendek. */
export function KotakTooltip({ judul, baris }: { judul: string; baris: BarisTooltip[] }) {
  return (
    <div className="rounded-[10px] border border-kertas-tua bg-putih px-3 py-2 text-sm shadow-md">
      <p className="mb-1 text-daun">{judul}</p>
      {baris.map((b) => (
        <p key={b.nama} className="flex items-center gap-2">
          <span
            aria-hidden
            className="inline-block w-3"
            style={b.garis === false ? { height: 10, background: b.warna, borderRadius: 2 } : { height: 2, background: b.warna }}
          />
          <strong className="angka text-daun-tua">{b.nilai}</strong>
          <span className="text-daun">{b.nama}</span>
        </p>
      ))}
    </div>
  );
}

/** Titik bulat r=4 dengan cincin 2px warna permukaan, hanya kalau titiknya sedikit. */
export function titikGaris(warna: string, banyak: number) {
  return banyak <= 31 ? { r: 4, fill: warna, stroke: WARNA.permukaan, strokeWidth: 2 } : false;
}
