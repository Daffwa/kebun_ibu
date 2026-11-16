"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { BARIS, NAMA_URUT, alamatPasar, paramTabel, type Urut } from "@/lib/tabelLonjakan";
import { Pilihan } from "./Saringan";

/** Urutan dan baris per halaman tabel lonjakan. Mengganti salah satunya kembali ke halaman 1. */
export default function PengaturanTabel({ query, urut, baris }: { query: string; urut: Urut; baris: number }) {
  const router = useRouter();
  const [memuat, mulaiTransisi] = useTransition();
  const ganti = (kunci: "t_urut" | "t_baris", nilai: string) =>
    mulaiTransisi(() => router.push(alamatPasar(query, "t_", { ...paramTabel(query), [kunci]: nilai }), { scroll: false }));

  return (
    <div className={`mb-3 grid max-w-2xl grid-cols-1 gap-2 transition-opacity sm:grid-cols-2 ${memuat ? "opacity-60" : ""}`}>
      <Pilihan label="Urutkan" value={urut} onChange={(e) => ganti("t_urut", e.target.value)}>
        {(Object.keys(NAMA_URUT) as Urut[]).map((u) => (
          <option key={u} value={u}>
            {NAMA_URUT[u]}
          </option>
        ))}
      </Pilihan>
      <Pilihan label="Baris per halaman" value={String(baris)} onChange={(e) => ganti("t_baris", e.target.value)}>
        {BARIS.map((b) => (
          <option key={b} value={b}>
            {b} baris per halaman
          </option>
        ))}
      </Pilihan>
    </div>
  );
}
