"use client";

import { useId, useState } from "react";
import { cariWilayah, labelWilayah, type Wilayah } from "@/lib/wilayah";

/**
 * Kotak cari wilayah (pola combobox ARIA). Diklik tanpa teks: 5 provinsi dengan toko terbanyak.
 * Mengetik: cari di semua tingkat dan kata kunci (`cariWilayah`). Panah atas/bawah, Enter, Esc;
 * di HP cukup disentuh. Tombol × kembali ke Semua wilayah.
 */
export default function KotakWilayah({
  daftar,
  terpilih,
  onPilih,
  kelas,
}: {
  daftar: Wilayah[];
  terpilih: Wilayah | null;
  onPilih: (kode: string) => void;
  kelas: string;
}) {
  const id = useId();
  const [buka, setBuka] = useState(false);
  const [teks, setTeks] = useState("");
  const [aktif, setAktif] = useState(0);
  const hasil = buka ? cariWilayah(daftar, teks) : [];

  const tutup = () => {
    setBuka(false);
    setTeks("");
  };
  const pilih = (w: Wilayah, input: HTMLInputElement | null) => {
    tutup();
    input?.blur();
    onPilih(w.wilayah);
  };

  return (
    <div className="relative">
      <input
        role="combobox"
        aria-label="Wilayah"
        aria-expanded={buka}
        aria-controls={`${id}-daftar`}
        aria-autocomplete="list"
        aria-activedescendant={buka && hasil[aktif] ? `${id}-${aktif}` : undefined}
        autoComplete="off"
        value={buka ? teks : (terpilih?.nama ?? "")}
        placeholder={buka ? "Cari wilayah…" : "Semua wilayah"}
        onFocus={() => {
          setBuka(true);
          setTeks("");
          setAktif(0);
        }}
        onBlur={tutup}
        onChange={(e) => {
          setTeks(e.target.value);
          setAktif(0);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setAktif((a) => Math.min(a + 1, hasil.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setAktif((a) => Math.max(a - 1, 0));
          } else if (e.key === "Enter" && hasil[aktif]) {
            e.preventDefault();
            pilih(hasil[aktif], e.currentTarget);
          } else if (e.key === "Escape") {
            e.currentTarget.blur();
          }
        }}
        className={`${kelas} placeholder:font-semibold placeholder:text-daun-tua focus:placeholder:font-normal focus:placeholder:text-daun`}
      />

      {terpilih && !buka ? (
        <button
          type="button"
          aria-label="Hapus pilihan wilayah"
          onClick={() => onPilih("semua")}
          className="absolute top-1/2 right-1 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center text-xl text-daun-tua"
        >
          ×
        </button>
      ) : (
        <span aria-hidden className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-daun-tua">
          ⌕
        </span>
      )}

      {buka && (
        <ul
          id={`${id}-daftar`}
          role="listbox"
          aria-label="Pilihan wilayah"
          className="absolute z-20 mt-1 max-h-80 w-full min-w-64 overflow-auto rounded-[10px] border-2 border-daun-muda bg-putih py-1 shadow-lg"
        >
          {teks.trim() === "" && (
            <li role="presentation" className="px-3 pt-1 pb-1 text-sm text-daun">
              Provinsi dengan toko terbanyak
            </li>
          )}
          {hasil.map((w, i) => (
            <li
              key={w.wilayah}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === aktif}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setAktif(i)}
              onClick={() => pilih(w, document.activeElement as HTMLInputElement | null)}
              className={`flex min-h-11 cursor-pointer items-center px-3 py-2 ${i === aktif ? "bg-kertas-tua" : ""}`}
            >
              <span>
                <span className="font-semibold text-daun-tua">{w.nama}</span>
                <span className="text-sm text-daun">{labelWilayah(w).slice(w.nama.length)}</span>
              </span>
            </li>
          ))}
          {hasil.length === 0 && <li className="px-3 py-2 text-daun">Tidak ada wilayah yang cocok.</li>}
        </ul>
      )}
    </div>
  );
}
