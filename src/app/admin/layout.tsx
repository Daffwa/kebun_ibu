import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { keluar } from "./actions";
import NavAdmin from "./NavAdmin";

export default async function LayoutAdmin({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Halaman login ikut lewat sini. Tanpa sesi, tampilkan polos saja -
  // menu dan tombol keluar tidak ada gunanya sebelum masuk.
  if (!user) return <>{children}</>;

  return (
    <div className="min-h-dvh">
      <header className="border-b-2 border-daun-tua bg-daun-tua text-putih">
        <div className="mx-auto flex w-full max-w-5xl lg:max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8 py-3.5">
          <Link href="/admin" className="text-xl font-extrabold tracking-tight transition-transform hover:scale-105">
            Kebun Ibu <span className="text-xs font-normal text-emas ml-1 bg-white/10 px-2 py-0.5 rounded-full">Admin</span>
          </Link>
          <form action={keluar}>
            <button className="min-h-10 rounded-full border-2 border-putih/40 px-4 text-sm font-semibold transition-all hover:bg-putih/10 active:scale-95">
              Keluar
            </button>
          </form>
        </div>
        <div className="mx-auto max-w-5xl lg:max-w-6xl px-4 sm:px-6 lg:px-8">
          <NavAdmin />
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl lg:max-w-6xl px-4 sm:px-6 lg:px-8 pt-8 pb-24">{children}</main>
    </div>
  );
}
