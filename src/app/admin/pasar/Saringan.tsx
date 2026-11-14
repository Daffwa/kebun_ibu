import Link from "next/link";
import { NAMA_PASAR, NAMA_RENTANG, type Pasar, type Preset, type Rentang } from "@/lib/pasar";

const PASAR: Pasar[] = ["semua", "tokopedia", "blibli"];
const PRESET: Preset[] = ["30h", "1t", "5t"];

const PIL = "inline-flex min-h-11 items-center rounded-full border-2 px-4 font-semibold";
const pil = (aktif: boolean) =>
  `${PIL} border-daun-tua ${aktif ? "bg-daun-tua text-putih" : "bg-putih text-daun-tua"}`;

function alamat(q: { pasar: Pasar; rentang: Rentang; dari?: string; sampai?: string }): string {
  const p = new URLSearchParams({ pasar: q.pasar, rentang: q.rentang });
  if (q.rentang === "kustom" && q.dari && q.sampai) {
    p.set("dari", q.dari);
    p.set("sampai", q.sampai);
  }
  return `/admin/pasar?${p}`;
}

/**
 * Satu baris saringan di atas semua grafik. Semuanya tautan/form GET biasa, jadi jalan tanpa
 * JavaScript dan bisa dibagikan. Preset terkunci bukan tautan; alasannya ditulis di bawah
 * (HP tidak punya hover untuk tooltip).
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
  const terkunci = status ? PRESET.filter((p) => !status[p].terbuka).map((p) => status[p].pesan) : [];

  return (
    <div className="mb-6 space-y-3">
      <div className="flex flex-wrap gap-2" aria-label="Marketplace">
        {PASAR.map((p) => (
          <Link
            key={p}
            href={alamat({ pasar: p, rentang, dari: mulai, sampai: akhir })}
            aria-current={p === pasar ? "page" : undefined}
            className={pil(p === pasar)}
          >
            {p === "semua" ? "Semua" : NAMA_PASAR[p]}
          </Link>
        ))}
      </div>

      {batas && status && (
        <>
          <div className="flex flex-wrap gap-2" aria-label="Rentang waktu">
            {PRESET.map((p) =>
              status[p].terbuka ? (
                <Link key={p} href={alamat({ pasar, rentang: p })} aria-current={p === rentang ? "page" : undefined} className={pil(p === rentang)}>
                  {NAMA_RENTANG[p]}
                </Link>
              ) : (
                <span key={p} aria-disabled="true" title={status[p].pesan} className={`${PIL} border-kertas-tua bg-kertas-tua text-daun-muda`}>
                  {NAMA_RENTANG[p]}
                </span>
              ),
            )}
            <Link href={alamat({ pasar, rentang: "semua" })} aria-current={rentang === "semua" ? "page" : undefined} className={pil(rentang === "semua")}>
              Semua
            </Link>
          </div>

          {terkunci.length > 0 && <p className="text-sm text-daun">Terkunci · {terkunci.join(" · ")}</p>}

          <form method="get" action="/admin/pasar" className="flex flex-wrap items-end gap-2">
            <input type="hidden" name="pasar" value={pasar} />
            <input type="hidden" name="rentang" value="kustom" />
            <label className="flex flex-col text-sm text-daun">
              Dari
              <input
                type="date"
                name="dari"
                min={batas.awal}
                max={batas.akhir}
                defaultValue={mulai ?? batas.awal}
                className="min-h-11 rounded-[10px] border-2 border-daun-muda bg-putih px-2 text-base text-daun-tua"
              />
            </label>
            <label className="flex flex-col text-sm text-daun">
              Sampai
              <input
                type="date"
                name="sampai"
                min={batas.awal}
                max={batas.akhir}
                defaultValue={akhir ?? batas.akhir}
                className="min-h-11 rounded-[10px] border-2 border-daun-muda bg-putih px-2 text-base text-daun-tua"
              />
            </label>
            <button className={pil(rentang === "kustom")}>{rentang === "kustom" ? "Kustom ✓" : "Terapkan"}</button>
          </form>
        </>
      )}
    </div>
  );
}
