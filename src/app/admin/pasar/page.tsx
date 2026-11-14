import { supabaseServer } from "@/lib/supabase/server";
import {
  JENDELA_HARI,
  NAMA_PASAR,
  bacaFilter,
  deret,
  geserIndeks,
  histogram,
  pilihRentang,
  rentangTeks,
  ringkasProduk,
  ringkasTren,
  rupiahRingkas,
  selisihHari,
  statusPreset,
  tanggalPanjang,
} from "@/lib/pasar";
import { ambilBatas, ambilHarian, ambilLonjakan, ambilProdukRentang } from "@/lib/pasarData";
import { rupiah } from "@/lib/format";
import AngkaUtama from "./AngkaUtama";
import GrafikHistogram from "./GrafikHistogram";
import GrafikLonjakan from "./GrafikLonjakan";
import GrafikTren from "./GrafikTren";
import Saringan from "./Saringan";
import TabelLonjakan from "./TabelLonjakan";

export const revalidate = 0;

function Kosong({ judul, isi }: { judul: string; isi?: string }) {
  return (
    <div className="rounded-[10px] border-2 border-dashed border-daun-muda bg-putih px-6 py-12 text-center">
      <p className="text-xl font-semibold">{judul}</p>
      {isi && <p className="mt-2 text-daun">{isi}</p>}
    </div>
  );
}

function Kartu({ judul, children }: { judul: string; children: React.ReactNode }) {
  return (
    <section className="mb-4 rounded-[10px] bg-putih p-4">
      <h2 className="mb-3 text-lg font-bold text-daun-tua">{judul}</h2>
      {children}
    </section>
  );
}

const persen = (v: number) =>
  `${v > 0 ? "+" : ""}${(v * 100).toLocaleString("id-ID", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}%`;

export default async function Pasar({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const filter = bacaFilter(await searchParams);
  const sb = await supabaseServer();
  const batas = await ambilBatas(sb, filter.pasar);

  const kepala = (
    <div className="mb-5">
      <h1 className="text-3xl font-extrabold text-daun-tua">Pasar</h1>
      <p className="mt-1 text-daun">Harga Mangga Manalagi di Blibli dan Tokopedia, per kg.</p>
    </div>
  );

  if (!batas) {
    return (
      <>
        {kepala}
        <Saringan pasar={filter.pasar} rentang={filter.rentang} batas={null} status={null} />
        <Kosong judul={`Belum ada data harga Manalagi untuk ${NAMA_PASAR[filter.pasar]}.`} isi="Data dikirim laptop setiap hari sesudah penarikan harga." />
      </>
    );
  }

  const status = statusPreset(batas.awal, batas.akhir);
  const pilih = pilihRentang(filter, batas.awal, batas.akhir);

  if ("kosong" in pilih) {
    return (
      <>
        {kepala}
        <Saringan pasar={filter.pasar} rentang="kustom" batas={batas} status={status} />
        {pilih.kosong === "terbalik" ? (
          <Kosong judul="Rentang kosong." isi="Tanggal Dari sesudah tanggal Sampai. Pilih ulang tanggalnya." />
        ) : (
          <Kosong
            judul={`Tidak ada data ${NAMA_PASAR[filter.pasar]} di rentang ini.`}
            isi={`Data ${NAMA_PASAR[filter.pasar]} ada dari ${tanggalPanjang(batas.awal)} sampai ${tanggalPanjang(batas.akhir)}.`}
          />
        )}
      </>
    );
  }

  const { mulai, akhir } = pilih;
  const harian = await ambilHarian(sb, filter.pasar, mulai, akhir);
  const { titik, satuan } = deret(harian, mulai, akhir);
  // Grafik 1 dan 2: seluruh rentang, setiap produk sekali (median harganya di rentang).
  const [barisProduk, lonjakan] = await Promise.all([
    ambilProdukRentang(sb, filter.pasar, mulai, akhir),
    ambilLonjakan(sb, filter.pasar, mulai, akhir),
  ]);
  const produk = ringkasProduk(barisProduk);

  const indeks = geserIndeks(titik);
  const tren = ringkasTren(indeks, titik.map((t) => t.tanggal));
  const nLonjak = titik.filter((t) => t.lonjak_pasar === 1).length;
  const hist = produk.length ? histogram(produk.map((p) => p.harga_per_kg)) : null;

  return (
    <>
      {kepala}
      <Saringan
        key={`${filter.pasar}-${pilih.rentang}-${mulai}-${akhir}`}
        pasar={filter.pasar}
        rentang={pilih.rentang}
        mulai={mulai}
        akhir={akhir}
        batas={batas}
        status={status}
      />

      <p className="mb-4 text-sm text-daun">
        {rentangTeks(mulai, akhir)} · {selisihHari(mulai, akhir) + 1} hari, {harian.length} berdata · titik per {satuan}
      </p>

      {hist ? (
        <>
          <AngkaUtama produk={produk} mulai={mulai} akhir={akhir} />
          <Kartu judul="Sebaran harga per kg (satu produk dihitung sekali)">
            <GrafikHistogram {...hist} />
          </Kartu>
        </>
      ) : (
        <div className="mb-4">
          <Kosong judul="Tidak ada data harga di rentang ini." />
        </div>
      )}

      <Kartu
        judul={
          "Harga per kg produk yang sama" +
          (tren ? `: ${rupiah(tren.akhir)}, ${persen(tren.ubah)} sejak ${tanggalPanjang(tren.sejak)}` : "")
        }
      >
        <GrafikTren
          titik={titik.map((t, i) => ({ tanggal: t.tanggal, indeks: indeks[i], median: t.median }))}
          satuan={satuan}
        />
        <p className="mt-2 text-sm text-daun">
          Garis biru hanya bergerak kalau produk yang sama berubah harga, jadi tidak terpengaruh produk yang muncul
          berganti. Ujung kanannya = median hari terakhir ({tren ? rupiahRingkas(tren.akhir) : "–"}).
        </p>
      </Kartu>

      <Kartu
        judul={`Harga pasar vs ${JENDELA_HARI} hari sebelumnya (per ${satuan}): ${
          nLonjak === 0 ? "tidak ada lonjakan pasar" : `${nLonjak} ${satuan} lonjakan pasar`
        }`}
      >
        <GrafikLonjakan titik={titik} satuan={satuan} />
        <TabelLonjakan {...lonjakan} />
      </Kartu>
    </>
  );
}
