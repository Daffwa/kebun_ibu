-- =====================================================================
-- Kebun Ibu - filter wilayah di dashboard Manalagi
-- Jalankan SETELAH 20261113000000_pasar_manalagi.sql, lewat SQL Editor di dashboard supabase.com.
-- Aman dijalankan ulang berkali-kali.
-- Rancangan: docs/superpowers/specs/2026-11-14-filter-wilayah-design.md
-- =====================================================================

-- Kode Kepmendagri 2025 per baris produk; kosong = kota kosong atau tidak dikenal.
alter table public.pasar_manalagi add column if not exists kabkota_kode  text;
alter table public.pasar_manalagi add column if not exists provinsi_kode text;

-- Deret harian per wilayah: 'semua', kelompok ('jabodetabek'), provinsi ('35'), kab/kota ('35.78').
-- Baris yang sudah ada otomatis 'semua', jadi web yang belum mengenal wilayah tetap benar.
alter table public.pasar_manalagi_harian
  add column if not exists wilayah text not null default 'semua';
alter table public.pasar_manalagi_harian drop constraint if exists pasar_manalagi_harian_pkey;
alter table public.pasar_manalagi_harian
  add constraint pasar_manalagi_harian_pkey primary key (tanggal, pasar, wilayah);

-- Daftar wilayah untuk kotak cari: hanya wilayah yang punya data, jumlah toko sepanjang data.
create table if not exists public.pasar_wilayah (
  wilayah        text    not null,
  pasar          text    not null check (pasar in ('semua', 'blibli', 'tokopedia')),
  nama           text    not null,
  tingkat        text    not null check (tingkat in ('kelompok', 'provinsi', 'kabkota')),
  provinsi_kode  text,                 -- hanya untuk tingkat kabkota
  kata_kunci     text,                 -- kata cari tambahan, mis. 'jatim'
  jumlah_toko    integer not null,
  primary key (wilayah, pasar)
);

revoke all on public.pasar_wilayah from anon, authenticated;
grant select on public.pasar_wilayah to authenticated;
grant select, insert, delete on public.pasar_wilayah to service_role;

alter table public.pasar_wilayah enable row level security;
drop policy if exists pasar_wilayah_baca_pengelola on public.pasar_wilayah;
create policy pasar_wilayah_baca_pengelola on public.pasar_wilayah
  for select to authenticated using (public.is_pengelola());

-- Dibuat ulang: jsonb_populate_recordset mengisi kunci yang tidak ada dengan NULL, bukan nilai
-- bawaan kolom. Basis rekaman berisi wilayah = 'semua' membuat baris harian tanpa kunci
-- `wilayah` (laptop versi lama) tetap tersimpan sebagai 'semua'.
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
    select * from jsonb_populate_recordset(
      jsonb_populate_record(null::public.pasar_manalagi_harian, '{"wilayah": "semua"}'), p_harian);
end;
$gpm$;

revoke all on function public.ganti_pasar_manalagi(jsonb, jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.ganti_pasar_manalagi(jsonb, jsonb, jsonb) to service_role;

-- Mengganti seluruh isi pasar_wilayah dalam satu transaksi (±200 baris).
create or replace function public.ganti_pasar_wilayah(p_baris jsonb)
returns void
language plpgsql
set search_path = public, pg_temp
as $gpw$
begin
  delete from public.pasar_wilayah where true;
  insert into public.pasar_wilayah
    select * from jsonb_populate_recordset(null::public.pasar_wilayah, p_baris);
end;
$gpw$;

revoke all on function public.ganti_pasar_wilayah(jsonb) from public, anon, authenticated;
grant execute on function public.ganti_pasar_wilayah(jsonb) to service_role;

notify pgrst, 'reload schema';
