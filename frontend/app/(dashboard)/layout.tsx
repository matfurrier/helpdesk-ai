import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { buildApiUrl } from "@/lib/api";
import { Sidebar } from "@/components/layout/sidebar";

interface UserOut {
  user_id: string;
  name: string;
  role: string;
}

async function getMe(session: { name: string; value: string }): Promise<UserOut | null> {
  try {
    const res = await fetch(buildApiUrl("/api/v1/auth/me"), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json() as Promise<UserOut>;
  } catch {
    return null;
  }
}

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) redirect("/login");

  const user = await getMe(session);
  if (!user) redirect("/login");

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-950">
      <Sidebar role={user.role} userName={user.name} />
      <main className="flex-1 overflow-y-auto bg-zinc-900">
        {children}
      </main>
    </div>
  );
}
