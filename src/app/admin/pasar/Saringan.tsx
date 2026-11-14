"use client";

import Form from "next/form";
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
import { alamatPasar, isianTersembunyi, type Awalan } from "@/lib/tabelLonjakan";
import type { Wilayah } from "@/lib/wilayah";
import KotakWilayah from "./KotakWilayah";

const PASAR: Pasar[] = ["semua", "tokopedia", "blibli"];
const PRESET: Preset[] = ["30h", "1t", "5t"];

export const KOTAK =
  "min-h-11 w-full appearance-none rounded-full border-2 border-daun-tua bg-putih pr-8 pl-3 text-base font-semibold text-daun-tua";

export function Pilihan({ label, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
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
 * Satu baris saringan: di atas grafik (`awalan` "") atau di kartu tabel lonjakan (`awalan` "t_").
 * Alamat baru hanya mengganti parameter kelompoknya sendiri; kelompok lain di `query` tetap.
 * `tambahan` = parameter kelompok ini yang bukan saringan (urutan dan baris tabel), ikut dibawa.
 *
 * Saringan: dua menu pilihan dan kotak cari wilayah. Preset yang terkunci tampil abu-abu di dalam
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
  wilayah,
  daftarWilayah,
  awalan,
  query,
  tambahan = {},
}: {
  awalan: Awalan;
  query: string;
  tambahan?: Record<string, string>;
  pasar: Pasar;
  rentang: Rentang;
  wilayah: Wilayah | null;
  daftarWilayah: Wilayah[];
  mulai?: string;
  akhir?: string;
  batas: { awal: string; akhir: string } | null;
  status: Record<Preset, { terbuka: boolean; pesan: string }> | null;
}) {
  const router = useRouter();
  const [memuat, mulaiTransisi] = useTransition();
  const [kustom, setKustom] = useState(rentang === "kustom");
  // Tabel ada di bawah grafik: pindah halaman tanpa melompat ke atas.
  const pergi = (url: string) => mulaiTransisi(() => router.push(url, { scroll: awalan === "" }));
  const kodeWilayah = wilayah?.wilayah ?? "semua";
  const terkunciBerikut = status ? PRESET.find((p) => !status[p].terbuka) : undefined;
  const alamat = (q: { pasar: Pasar; rentang: Rentang; wilayah: string; dari?: string; sampai?: string }) => {
    const kustom = q.rentang === "kustom" && q.dari && q.sampai;
    return alamatPasar(query, awalan, {
      [`${awalan}pasar`]: q.pasar,
      [`${awalan}rentang`]: q.rentang,
      [`${awalan}wilayah`]: q.wilayah !== "semua" ? q.wilayah : undefined,
      [`${awalan}dari`]: kustom ? q.dari : undefined,
      [`${awalan}sampai`]: kustom ? q.sampai : undefined,
      ...tambahan,
    });
  };

  return (
    <div className={`mb-5 space-y-2 transition-opacity ${memuat ? "opacity-60" : ""}`}>
      <div className="grid max-w-2xl grid-cols-2 gap-2 sm:grid-cols-3">
        <Pilihan
          label="Marketplace"
          value={pasar}
          onChange={(e) => pergi(alamat({ pasar: e.target.value as Pasar, rentang, wilayah: kodeWilayah, dari: mulai, sampai: akhir }))}
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
              pergi(alamat({ pasar, rentang: r, wilayah: kodeWilayah }));
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

        {daftarWilayah.length > 0 && (
          <div className="col-span-2 sm:col-span-1">
            <KotakWilayah
              daftar={daftarWilayah}
              terpilih={wilayah}
              kelas={KOTAK.replace("pr-8", "pr-11")}
              onPilih={(w) => pergi(alamat({ pasar, rentang, wilayah: w, dari: mulai, sampai: akhir }))}
            />
          </div>
        )}
      </div>

      {batas && terkunciBerikut && (
        <p className="text-sm text-daun">
          🔒 {NAMA_RENTANG[terkunciBerikut]} terbuka mulai {tanggalPanjang(tanggalTerbuka(batas.awal, terkunciBerikut))}
        </p>
      )}

      {batas && kustom && (
        // next/form: navigasi di sisi klien (bukan muat ulang dokumen); form tabel tidak melompat ke atas.
        <Form action="/admin/pasar" scroll={awalan === ""} prefetch={false} className="flex flex-wrap items-end gap-2 pt-1">
          <input type="hidden" name={`${awalan}pasar`} value={pasar} />
          <input type="hidden" name={`${awalan}rentang`} value="kustom" />
          {wilayah && <input type="hidden" name={`${awalan}wilayah`} value={wilayah.wilayah} />}
          {isianTersembunyi(query, awalan, tambahan).map(([k, v]) => (
            <input key={k} type="hidden" name={k} value={v} />
          ))}
          {(
            [
              [`${awalan}dari`, "Dari", mulai ?? batas.awal],
              [`${awalan}sampai`, "Sampai", akhir ?? batas.akhir],
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
        </Form>
      )}
    </div>
  );
}
