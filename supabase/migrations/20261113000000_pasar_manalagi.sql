-- =====================================================================
-- Kebun Ibu - data dashboard harga Mangga Manalagi
-- Jalankan SETELAH 20261012000000_templat_pesan.sql, lewat SQL Editor.
-- Aman dijalankan ulang berkali-kali.
-- Rancangan: docs/superpowers/specs/2026-11-13-dashboard-manalagi-design.md
-- =====================================================================

-- Diisi oleh laptop (data-science/kirim_supabase.py, kunci service role) setiap hari sesudah
-- gudang DuckDB dimuat. Hanya dibaca pengelola di halaman /admin/pasar.
-- Kolomnya hanya yang dibaca grafik dan filter; langkah antara tetap di laptop.

-- Satu baris per produk per hari.
create table if not exists public.pasar_manalagi (
  tanggal         date   not null,
  sumber          text   not null check (sumber in ('blibli', 'tokopedia')),
  produk_key      text   not null,
  nama_toko       text,
  kota            text,
  harga_per_kg    bigint not null,
  terjual_min     bigint,
  median_jendela  double precision,   -- median harga produk ini 7 hari sebelumnya
  rasio_jendela   double precision,   -- harga hari ini / median_jendela (kosong: data < 3 hari)
  lonjak_toko     boolean not null,
  primary key (tanggal, produk_key)
);

-- Satu baris per tanggal per pasar (semua marketplace, Blibli, Tokopedia).
create table if not exists public.pasar_manalagi_harian (
  tanggal          date    not null,
  pasar            text    not null check (pasar in ('semua', 'blibli', 'tokopedia')),
  jumlah_produk    integer not null,
  median           double precision not null,
  indeks_berantai  double precision not null,   -- digeser ke median hari terakhir saat digambar
  median_rasio     double precision,
  lonjak_pasar     boolean not null,
  naik             integer not null,
  turun            integer not null,
  primary key (tanggal, pasar)
);

-- Dicabut dulu, baru diberikan (GRANT hanya menambah). Anon sengaja tidak diberi apa-apa.
-- service_role diberi eksplisit: GRANT otomatis Supabase untuk tabel baru mati sejak 30 Okt 2026.
revoke all on public.pasar_manalagi, public.pasar_manalagi_harian from anon, authenticated;
grant select on public.pasar_manalagi, public.pasar_manalagi_harian to authenticated;
grant select, insert, delete on public.pasar_manalagi, public.pasar_manalagi_harian to service_role;

alter table public.pasar_manalagi        enable row level security;
alter table public.pasar_manalagi_harian enable row level security;

-- Hanya baca, hanya pengelola. Tidak ada policy tulis: yang menulis hanya service_role
-- (menembus RLS) lewat fungsi di bawah.
drop policy if exists pasar_baca_pengelola        on public.pasar_manalagi;
drop policy if exists pasar_harian_baca_pengelola on public.pasar_manalagi_harian;
create policy pasar_baca_pengelola on public.pasar_manalagi
  for select to authenticated using (public.is_pengelola());
create policy pasar_harian_baca_pengelola on public.pasar_manalagi_harian
  for select to authenticated using (public.is_pengelola());

-- Mengganti seluruh isi tanggal-tanggal tertentu di kedua tabel dalam SATU transaksi, jadi
-- halaman dashboard tidak pernah melihat tanggal yang setengah terganti.
--   p_tanggal: ["2026-11-07", ...]       tanggal yang diganti (boleh tanpa baris = dihapus)
--   p_baris:   [{kolom pasar_manalagi}]  baris baru untuk tanggal-tanggal itu
--   p_harian:  [{kolom pasar_manalagi_harian}]
-- Bukan security definer: berjalan dengan hak pemanggil, dan hanya service_role yang boleh memanggil.
create or replace function public.ganti_pasar_manalagi(p_tanggal jsonb, p_baris jsonb, p_harian jsonb)
returns void
language plpgsql
set search_path = public, pg_temp
as $gpm$
declare
  v_tanggal date[] := array(select jsonb_array_elements_text(p_tanggal)::date);
begin
  delete from public.pasar_manalagi        where tanggal = any(v_tanggal);
  delete from public.pasar_manalagi_harian where tanggal = any(v_tanggal);
  insert into public.pasar_manalagi
    select * from jsonb_populate_recordset(null::public.pasar_manalagi, p_baris);
  insert into public.pasar_manalagi_harian
    select * from jsonb_populate_recordset(null::public.pasar_manalagi_harian, p_harian);
end;
$gpm$;

revoke all on function public.ganti_pasar_manalagi(jsonb, jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.ganti_pasar_manalagi(jsonb, jsonb, jsonb) to service_role;

-- PostgREST langsung mengenal tabel dan fungsi baru tanpa menunggu.
notify pgrst, 'reload schema';
