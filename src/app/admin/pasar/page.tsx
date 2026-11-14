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
import { ambilBatas, ambilDaftarWilayah, ambilHarian, ambilLonjakanHalaman, ambilProdukRentang } from "@/lib/pasarData";
import { bacaTabel } from "@/lib/tabelLonjakan";
import { pilihWilayah, saringanProduk } from "@/lib/wilayah";
import { rupiah } from "@/lib/format";
import AngkaUtama from "./AngkaUtama";
import GrafikHistogram from "./GrafikHistogram";
import GrafikLonjakan from "./GrafikLonjakan";
import GrafikTren from "./GrafikTren";
import Saringan from "./Saringan";
import TabelLonjakan, { type PropsTabel } from "./TabelLonjakan";

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

type Sp = Record<string, string | string[] | undefined>;
type SupabaseServer = Awaited<ReturnType<typeof supabaseServer>>;

function teksQuery(sp: Sp): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(sp)) for (const isi of [v ?? []].flat()) p.append(k, isi);
  return p.toString();
}

/** Data kartu tabel lonjakan: hanya dari parameter `t_*`, tidak bergantung pada saringan grafik. */
async function siapkanTabel(sb: SupabaseServer, sp: Sp, query: string): Promise<PropsTabel> {
  const t = bacaTabel(sp);
  const daftarWilayah = await ambilDaftarWilayah(sb, t.filter.pasar);
  const wilayah = pilihWilayah(t.wilayah, daftarWilayah);
  const nama = `${NAMA_PASAR[t.filter.pasar]}${wilayah ? ` di ${wilayah.nama}` : ""}`;
  const batas = await ambilBatas(sb, t.filter.pasar, wilayah?.wilayah ?? "semua");
  const dasar = {
    query, pasar: t.filter.pasar, wilayah, daftarWilayah, batas, urut: t.urut, baris: t.baris,
    daftar: [], jumlah: 0, hal: 1,
  };
  if (!batas) return { ...dasar, rentang: t.filter.rentang, status: null, pesan: `Belum ada data harga untuk ${nama}.` };
  const status = statusPreset(batas.awal, batas.akhir);
  const pilih = pilihRentang(t.filter, batas.awal, batas.akhir);
  if ("kosong" in pilih) {
    const pesan = pilih.kosong === "terbalik"
      ? "Rentang kosong: tanggal Dari sesudah tanggal Sampai."
      : `Tidak ada data ${nama} di rentang ini.`;
    return { ...dasar, rentang: "kustom", status, pesan };
  }
  const halaman = await ambilLonjakanHalaman(sb, {
    pasar: t.filter.pasar, mulai: pilih.mulai, akhir: pilih.akhir, wilayah: saringanProduk(wilayah) ?? undefined,
    urut: t.urut, baris: t.baris, hal: t.hal,
  });
  return {
    ...dasar, ...halaman, rentang: pilih.rentang, mulai: pilih.mulai, akhir: pilih.akhir, status,
    pesan: halaman.jumlah === 0 ? "Tidak ada toko yang melonjak untuk saringan ini." : null,
  };
}

export default async function Pasar({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const filter = bacaFilter(sp);
  const query = teksQuery(sp);
  const sb = await supabaseServer();
  // Wilayah dari URL hanya sah kalau ada di daftar pasar ini; lainnya = semua wilayah.
  const [tabel, daftarWilayah] = await Promise.all([siapkanTabel(sb, sp, query), ambilDaftarWilayah(sb, filter.pasar)]);
  const kartuTabel = <TabelLonjakan {...tabel} />;
  const wilayah = pilihWilayah(sp.wilayah, daftarWilayah);
  const kodeWilayah = wilayah?.wilayah ?? "semua";
  const saringWilayah = saringanProduk(wilayah);
  const namaData = `${NAMA_PASAR[filter.pasar]}${wilayah ? ` di ${wilayah.nama}` : ""}`;
  const batas = await ambilBatas(sb, filter.pasar, kodeWilayah);
  const saringan = { pasar: filter.pasar, wilayah, daftarWilayah, awalan: "" as const, query };

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
        <Saringan {...saringan} rentang={filter.rentang} batas={null} status={null} />
        <Kosong judul={`Belum ada data harga Manalagi untuk ${namaData}.`} isi="Data dikirim laptop setiap hari sesudah penarikan harga." />
        <div className="mt-4">{kartuTabel}</div>
      </>
    );
  }

  const status = statusPreset(batas.awal, batas.akhir);
  const pilih = pilihRentang(filter, batas.awal, batas.akhir);

  if ("kosong" in pilih) {
    return (
      <>
        {kepala}
        <Saringan {...saringan} rentang="kustom" batas={batas} status={status} />
        {pilih.kosong === "terbalik" ? (
          <Kosong judul="Rentang kosong." isi="Tanggal Dari sesudah tanggal Sampai. Pilih ulang tanggalnya." />
        ) : (
          <Kosong
            judul={`Tidak ada data ${namaData} di rentang ini.`}
            isi={`Data ${namaData} ada dari ${tanggalPanjang(batas.awal)} sampai ${tanggalPanjang(batas.akhir)}.`}
          />
        )}
        <div className="mt-4">{kartuTabel}</div>
      </>
    );
  }

  const { mulai, akhir } = pilih;
  const harian = await ambilHarian(sb, filter.pasar, mulai, akhir, kodeWilayah);
  const { titik, satuan } = deret(harian, mulai, akhir);
  // Grafik 1 dan 2: seluruh rentang, setiap produk sekali (median harganya di rentang).
  const barisProduk = await ambilProdukRentang(sb, filter.pasar, mulai, akhir, saringWilayah);
  const produk = ringkasProduk(barisProduk);

  const indeks = geserIndeks(titik);
  const tren = ringkasTren(indeks, titik.map((t) => t.tanggal));
  const nLonjak = titik.filter((t) => t.lonjak_pasar === 1).length;
  const hist = produk.length ? histogram(produk.map((p) => p.harga_per_kg)) : null;

  return (
    <>
      {kepala}
      <Saringan
        key={`${filter.pasar}-${kodeWilayah}-${pilih.rentang}-${mulai}-${akhir}`}
        {...saringan}
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
      </Kartu>

      {kartuTabel}
    </>
  );
}
