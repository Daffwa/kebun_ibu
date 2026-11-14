"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import {
  NAMA_PASAR,
  NAMA_RENTANG,
  tanggalPanjang,
  tanggalTerbuka,
  type Pasar,
  type Preset,
  type Rentang,
} from "@/lib/pasar";

const PASAR: Pasar[] = ["semua", "tokopedia", "blibli"];
const PRESET: Preset[] = ["30h", "1t", "5t"];

const KOTAK =
  "min-h-11 w-full appearance-none rounded-full border-2 border-daun-tua bg-putih pr-8 pl-3 text-base font-semibold text-daun-tua";

function alamat(q: { pasar: Pasar; rentang: Rentang; dari?: string; sampai?: string }): string {
  const p = new URLSearchParams({ pasar: q.pasar, rentang: q.rentang });
  if (q.rentang === "kustom" && q.dari && q.sampai) {
    p.set("dari", q.dari);
    p.set("sampai", q.sampai);
  }
  return `/admin/pasar?${p}`;
}

function Pilihan({ label, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  return (
    <div className="relative">
      <select aria-label={label} className={KOTAK} {...props}>
        {children}
      </select>
      <span aria-hidden className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-daun-tua">
        ▾
      </span>
    </div>
  );
}

/**
 * Saringan di atas semua grafik: dua menu pilihan. Preset yang terkunci tampil abu-abu di dalam
 * menu; satu baris pendek di bawahnya menyebut kapan preset berikutnya terbuka. Tanggal Dari–Sampai
 * hanya muncul kalau "Kustom…" dipilih. Halaman memberi `key` dari rentang yang tampil, jadi
 * keadaan di sini (dan isi tanggal) selalu ikut halaman sesudah berpindah.
 */
export default function Saringan({
  pasar,
  rentang,
  mulai,
  akhir,
  batas,
  status,
}: {
  pasar: Pasar;
  rentang: Rentang;
  mulai?: string;
  akhir?: string;
  batas: { awal: string; akhir: string } | null;
  status: Record<Preset, { terbuka: boolean; pesan: string }> | null;
}) {
  const router = useRouter();
  const [memuat, mulaiTransisi] = useTransition();
  const [kustom, setKustom] = useState(rentang === "kustom");
  const pergi = (url: string) => mulaiTransisi(() => router.push(url));
  const terkunciBerikut = status ? PRESET.find((p) => !status[p].terbuka) : undefined;

  return (
    <div className={`mb-5 space-y-2 transition-opacity ${memuat ? "opacity-60" : ""}`}>
      <div className="grid max-w-md grid-cols-2 gap-2">
        <Pilihan
          label="Marketplace"
          value={pasar}
          onChange={(e) => pergi(alamat({ pasar: e.target.value as Pasar, rentang, dari: mulai, sampai: akhir }))}
        >
          {PASAR.map((p) => (
            <option key={p} value={p}>
              {p === "semua" ? "Semua pasar" : NAMA_PASAR[p]}
            </option>
          ))}
        </Pilihan>

        {batas && status && (
          <Pilihan
            label="Rentang waktu"
            value={kustom ? "kustom" : rentang}
            onChange={(e) => {
              const r = e.target.value as Rentang;
              if (r === "kustom") return setKustom(true);
              setKustom(false);
              pergi(alamat({ pasar, rentang: r }));
            }}
          >
            {PRESET.map((p) => (
              <option key={p} value={p} disabled={!status[p].terbuka}>
                {NAMA_RENTANG[p]}
                {status[p].terbuka ? "" : " 🔒"}
              </option>
            ))}
            <option value="semua">Semua waktu</option>
            <option value="kustom">{kustom ? "Kustom" : "Kustom…"}</option>
          </Pilihan>
        )}
      </div>

      {batas && terkunciBerikut && (
        <p className="text-sm text-daun">
          🔒 {NAMA_RENTANG[terkunciBerikut]} terbuka mulai {tanggalPanjang(tanggalTerbuka(batas.awal, terkunciBerikut))}
        </p>
      )}

      {batas && kustom && (
        <form method="get" action="/admin/pasar" className="flex flex-wrap items-end gap-2 pt-1">
          <input type="hidden" name="pasar" value={pasar} />
          <input type="hidden" name="rentang" value="kustom" />
          {(
            [
              ["dari", "Dari", mulai ?? batas.awal],
              ["sampai", "Sampai", akhir ?? batas.akhir],
            ] as const
          ).map(([nama, label, nilai]) => (
            <label key={nama} className="flex flex-col text-sm text-daun">
              {label}
              <input
                type="date"
                name={nama}
                min={batas.awal}
                max={batas.akhir}
                defaultValue={nilai}
                className="min-h-11 rounded-[10px] border-2 border-daun-muda bg-putih px-2 text-base text-daun-tua"
              />
            </label>
          ))}
          <button className="inline-flex min-h-11 items-center rounded-full bg-daun-tua px-5 font-semibold text-putih">
            Terapkan
          </button>
        </form>
      )}
    </div>
  );
}
