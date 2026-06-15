"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";

interface Props {
  role: string;
  userName: string;
}

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "⬛" },
  { href: "/tickets", label: "Chamados", icon: "🎫" },
  { href: "/kb", label: "Base de Conhecimento", icon: "📚" },
];

const ADMIN_NAV = { href: "/admin", label: "Admin", icon: "🔧" };
const ASSETS_NAV = { href: "/admin/assets", label: "Patrimônio", icon: "🖥" };

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);

export function Sidebar({ role, userName }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const items = IT_ROLES.has(role) ? [...NAV, ASSETS_NAV, ADMIN_NAV] : NAV;

  async function handleLogout() {
    try {
      const csrfRes = await fetch("/api/v1/auth/csrf");
      await csrfRes.json();
      const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrf_token="))?.split("=")[1] ?? "";
      await fetch("/api/v1/auth/logout", { method: "POST", headers: { "X-CSRF-Token": csrf } });
    } finally {
      router.push("/login");
    }
  }

  return (
    <aside className="flex flex-col w-[220px] min-w-[220px] h-screen bg-zinc-950 border-r border-zinc-800/60 overflow-hidden">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-zinc-800/60">
        <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
          IT
        </div>
        <span className="text-sm font-semibold text-zinc-100 truncate">IT Helpdesk</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-zinc-800 text-white font-medium"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              }`}
            >
              <span className="text-base leading-none">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="px-3 py-3 border-t border-zinc-800/60">
        <div className="px-2 py-2">
          <p className="text-xs font-medium text-zinc-200 truncate">{userName}</p>
          <p className="text-[11px] text-zinc-500 truncate">{role}</p>
        </div>
        <button
          onClick={() => void handleLogout()}
          className="flex items-center gap-2 px-2 py-1.5 mt-1 w-full text-xs text-zinc-500 hover:text-zinc-300 rounded transition-colors"
        >
          <span>↩</span> Sair
        </button>
      </div>
    </aside>
  );
}
