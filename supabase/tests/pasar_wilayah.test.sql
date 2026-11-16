-- Tes filter wilayah: pasar_wilayah, ganti_pasar_wilayah, harian per wilayah.
-- Jalankan: npx supabase test db
begin;
create extension if not exists pgtap with schema extensions;
select plan(11);

-- Mulai dari tabel kosong: Supabase lokal bisa berisi data uji kirim_supabase.py.
-- Dihapus di dalam transaksi ini saja (rollback di akhir).
delete from public.pasar_manalagi;
delete from public.pasar_manalagi_harian;
delete from public.pasar_wilayah;

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-0000000000a1', 'ibu@contoh.test'),
  ('00000000-0000-0000-0000-0000000000b2', 'orang@asing.test');
insert into public.pengelola (user_id, nama)
values ('00000000-0000-0000-0000-0000000000a1', 'Ibu');

-- ---------- Laptop (service_role) mengisi daftar wilayah ----------
set local role service_role;
select lives_ok($$
  select public.ganti_pasar_wilayah('[
    {"wilayah":"35","pasar":"semua","nama":"Jawa Timur","tingkat":"provinsi","provinsi_kode":null,"kata_kunci":"jatim","jumlah_toko":7},
    {"wilayah":"35.78","pasar":"semua","nama":"Kota Surabaya","tingkat":"kabkota","provinsi_kode":"35","kata_kunci":null,"jumlah_toko":4}
  ]'::jsonb)
$$, 'service_role bisa mengisi lewat ganti_pasar_wilayah');
select public.ganti_pasar_wilayah('[
  {"wilayah":"jabodetabek","pasar":"semua","nama":"Jabodetabek","tingkat":"kelompok","provinsi_kode":null,"kata_kunci":null,"jumlah_toko":23}
]'::jsonb);
select results_eq($$ select wilayah from public.pasar_wilayah $$, $$ values ('jabodetabek') $$,
  'isi ulang mengganti seluruh daftar, bukan menambah');
select throws_ok($$
  select public.ganti_pasar_wilayah('[{"wilayah":"id","pasar":"semua","nama":"Indonesia","tingkat":"negara","provinsi_kode":null,"kata_kunci":null,"jumlah_toko":1}]'::jsonb) $$,
  '23514', null, 'tingkat selain kelompok/provinsi/kabkota ditolak');

-- ---------- Harian per wilayah lewat ganti_pasar_manalagi ----------
select public.ganti_pasar_manalagi('["2026-11-07"]'::jsonb, '[]'::jsonb, '[
  {"tanggal":"2026-11-07","pasar":"semua","wilayah":"semua","jumlah_produk":2,"median":27500,"indeks_berantai":27500,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0},
  {"tanggal":"2026-11-07","pasar":"semua","wilayah":"35","jumlah_produk":1,"median":25000,"indeks_berantai":25000,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0}
]'::jsonb);
select results_eq(
  $$ select wilayah from public.pasar_manalagi_harian where tanggal = '2026-11-07' order by 1 $$,
  $$ values ('35'), ('semua') $$,
  'tanggal dan pasar sama, wilayah berbeda: keduanya tersimpan');
select public.ganti_pasar_manalagi('["2026-11-08"]'::jsonb, '[]'::jsonb, '[
  {"tanggal":"2026-11-08","pasar":"semua","jumlah_produk":1,"median":1,"indeks_berantai":1,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0}
]'::jsonb);
select results_eq(
  $$ select wilayah from public.pasar_manalagi_harian where tanggal = '2026-11-08' $$,
  $$ values ('semua') $$,
  'baris harian tanpa kunci wilayah (laptop versi lama) tersimpan sebagai semua');
reset role;

-- ---------- Publik (anon) ----------
set local role anon;
select throws_ok($$ select * from public.pasar_wilayah $$, '42501', null, 'anon tidak bisa membaca pasar_wilayah');
select throws_ok($$ select public.ganti_pasar_wilayah('[]') $$, '42501', null, 'anon tidak bisa memanggil ganti_pasar_wilayah');
reset role;

-- ---------- Akun biasa, bukan pengelola ----------
set local request.jwt.claims = '{"sub":"00000000-0000-0000-0000-0000000000b2","role":"authenticated"}';
set local role authenticated;
select is_empty($$ select * from public.pasar_wilayah $$, 'akun biasa tidak melihat pasar_wilayah');
select throws_ok($$ select public.ganti_pasar_wilayah('[]') $$, '42501', null, 'akun biasa tidak bisa memanggil ganti_pasar_wilayah');
reset role;

-- ---------- Pengelola ----------
set local request.jwt.claims = '{"sub":"00000000-0000-0000-0000-0000000000a1","role":"authenticated"}';
set local role authenticated;
select results_eq($$ select count(*)::int from public.pasar_wilayah $$, $$ values (1) $$,
  'pengelola melihat daftar wilayah');
select throws_ok($$
  insert into public.pasar_wilayah (wilayah, pasar, nama, tingkat, jumlah_toko)
  values ('51', 'semua', 'Bali', 'provinsi', 1) $$,
  '42501', null, 'pengelola tidak bisa menulis langsung');
reset role;

select * from finish();
rollback;
