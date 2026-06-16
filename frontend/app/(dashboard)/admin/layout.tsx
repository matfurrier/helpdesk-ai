import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { buildApiUrl } from "@/lib/api";
import Link from "next/link";

interface UserOut { user_id: string; role: string; name: string; }

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);

const SUB_NAV = [
  { href: "/admin/kb", label: "Base de Conhecimento" },
  { href: "/admin/categories", label: "Categorias" },
  { href: "/admin/departments", label: "Departamentos" },
  { href: "/admin/applications", label: "Aplicações" },
  { href: "/admin/users-mgmt", label: "Cadastro de Usuários" },
  { href: "/admin/users", label: "Papéis TI" },
  { href: "/admin/sla", label: "SLA" },
  { href: "/admin/reports", label: "Relatórios" },
  { href: "/admin/ai-monitor", label: "Monitor IA" },
];

async function getMe(session: { name: string; value: string }): Promise<UserOut | null> {
  try {
    const res = await fetch(buildApiUrl("/api/v1/auth/me"), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json() as Promise<UserOut>;
  } catch { return null; }
}

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) redirect("/login");

  const user = await getMe(session);
  if (!user || !IT_ROLES.has(user.role)) redirect("/dashboard");

  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-zinc-800 bg-zinc-950/50 px-5 py-0 flex items-center gap-1 flex-shrink-0">
        {SUB_NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="px-3 py-3 text-xs text-zinc-400 hover:text-zinc-200 border-b-2 border-transparent hover:border-zinc-600 transition-colors whitespace-nowrap"
          >
            {item.label}
          </Link>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
