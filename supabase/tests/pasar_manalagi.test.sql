-- Tes aturan akses dan fungsi ganti data dashboard Manalagi. Jalankan: npx supabase test db
begin;
create extension if not exists pgtap with schema extensions;
select plan(14);

insert into auth.users (id, email) values
  ('00000000-0000-0000-0000-0000000000a1', 'ibu@contoh.test'),
  ('00000000-0000-0000-0000-0000000000b2', 'orang@asing.test');
insert into public.pengelola (user_id, nama)
values ('00000000-0000-0000-0000-0000000000a1', 'Ibu');

-- ---------- Laptop (service_role) mengisi dua tanggal ----------
set local role service_role;
select lives_ok($$
  select public.ganti_pasar_manalagi(
    '["2026-11-07", "2026-11-08"]'::jsonb,
    '[{"tanggal":"2026-11-07","sumber":"blibli","produk_key":"p1","nama_toko":"A","kota":"Bogor","harga_per_kg":30000,"terjual_min":null,"median_jendela":null,"rasio_jendela":null,"lonjak_toko":false},
      {"tanggal":"2026-11-07","sumber":"tokopedia","produk_key":"p2","nama_toko":"B","kota":null,"harga_per_kg":25000,"terjual_min":10,"median_jendela":null,"rasio_jendela":null,"lonjak_toko":false},
      {"tanggal":"2026-11-08","sumber":"blibli","produk_key":"p1","nama_toko":"A","kota":"Bogor","harga_per_kg":33000,"terjual_min":null,"median_jendela":30000,"rasio_jendela":1.1,"lonjak_toko":true},
      {"tanggal":"2026-11-08","sumber":"tokopedia","produk_key":"p2","nama_toko":"B","kota":null,"harga_per_kg":25000,"terjual_min":10,"median_jendela":25000,"rasio_jendela":1.0,"lonjak_toko":false}]'::jsonb,
    '[{"tanggal":"2026-11-07","pasar":"semua","jumlah_produk":2,"median":27500,"indeks_berantai":27500,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0},
      {"tanggal":"2026-11-07","pasar":"blibli","jumlah_produk":1,"median":30000,"indeks_berantai":30000,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0},
      {"tanggal":"2026-11-07","pasar":"tokopedia","jumlah_produk":1,"median":25000,"indeks_berantai":25000,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0},
      {"tanggal":"2026-11-08","pasar":"semua","jumlah_produk":2,"median":29000,"indeks_berantai":28875,"median_rasio":1.05,"lonjak_pasar":true,"naik":1,"turun":0},
      {"tanggal":"2026-11-08","pasar":"blibli","jumlah_produk":1,"median":33000,"indeks_berantai":33000,"median_rasio":1.1,"lonjak_pasar":true,"naik":1,"turun":0},
      {"tanggal":"2026-11-08","pasar":"tokopedia","jumlah_produk":1,"median":25000,"indeks_berantai":25000,"median_rasio":1.0,"lonjak_pasar":false,"naik":0,"turun":0}]'::jsonb)
$$, 'service_role bisa mengisi lewat ganti_pasar_manalagi');
reset role;

-- ---------- Publik (anon) ----------
set local role anon;
select throws_ok($$ select * from public.pasar_manalagi $$, '42501', null, 'anon tidak bisa membaca pasar_manalagi');
select throws_ok($$ select * from public.pasar_manalagi_harian $$, '42501', null, 'anon tidak bisa membaca pasar_manalagi_harian');
select throws_ok($$ select public.ganti_pasar_manalagi('[]', '[]', '[]') $$, '42501', null, 'anon tidak bisa memanggil fungsi ganti');
reset role;

-- ---------- Akun biasa, bukan pengelola ----------
set local request.jwt.claims = '{"sub":"00000000-0000-0000-0000-0000000000b2","role":"authenticated"}';
set local role authenticated;
select is_empty($$ select * from public.pasar_manalagi $$, 'akun biasa tidak melihat pasar_manalagi');
select is_empty($$ select * from public.pasar_manalagi_harian $$, 'akun biasa tidak melihat pasar_manalagi_harian');
select throws_ok($$ select public.ganti_pasar_manalagi('[]', '[]', '[]') $$, '42501', null, 'akun biasa tidak bisa memanggil fungsi ganti');
reset role;

-- ---------- Pengelola ----------
set local request.jwt.claims = '{"sub":"00000000-0000-0000-0000-0000000000a1","role":"authenticated"}';
set local role authenticated;
select results_eq($$ select count(*)::int from public.pasar_manalagi $$, $$ values (4) $$, 'pengelola melihat 4 baris produk');
select results_eq($$ select count(*)::int from public.pasar_manalagi_harian $$, $$ values (6) $$, 'pengelola melihat 6 baris harian');
select throws_ok($$
  insert into public.pasar_manalagi (tanggal, sumber, produk_key, harga_per_kg, lonjak_toko)
  values ('2026-11-09', 'blibli', 'p9', 1, false) $$,
  '42501', null, 'pengelola tidak bisa menulis langsung');
reset role;

-- ---------- Ganti, bukan tambah ----------
set local role service_role;
select public.ganti_pasar_manalagi(
  '["2026-11-07"]'::jsonb,
  '[{"tanggal":"2026-11-07","sumber":"blibli","produk_key":"p1","nama_toko":"A","kota":"Bogor","harga_per_kg":31000,"terjual_min":null,"median_jendela":null,"rasio_jendela":null,"lonjak_toko":false}]'::jsonb,
  '[]'::jsonb);
select results_eq(
  $$ select tanggal::text, count(*)::int from public.pasar_manalagi group by 1 order by 1 $$,
  $$ values ('2026-11-07', 1), ('2026-11-08', 2) $$,
  'ganti hanya menyentuh tanggal yang dikirim');
select results_eq(
  $$ select count(*)::int from public.pasar_manalagi_harian where tanggal = '2026-11-07' $$,
  $$ values (0) $$,
  'baris harian tanggal yang dikirim ikut diganti');

-- ---------- Kirim kosong menghapus tanggal ----------
select public.ganti_pasar_manalagi('["2026-11-08"]'::jsonb, '[]'::jsonb, '[]'::jsonb);
select results_eq(
  $$ select count(*)::int from public.pasar_manalagi where tanggal = '2026-11-08' $$,
  $$ values (0) $$,
  'kirim kosong menghapus tanggal');

select throws_ok($$
  select public.ganti_pasar_manalagi('["2026-11-09"]'::jsonb, '[]'::jsonb,
    '[{"tanggal":"2026-11-09","pasar":"shopee","jumlah_produk":1,"median":1,"indeks_berantai":1,"median_rasio":null,"lonjak_pasar":false,"naik":0,"turun":0}]'::jsonb) $$,
  '23514', null, 'pasar selain semua/blibli/tokopedia ditolak');
reset role;

select * from finish();
rollback;
