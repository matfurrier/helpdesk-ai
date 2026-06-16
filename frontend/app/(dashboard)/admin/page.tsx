import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { buildApiUrl } from "@/lib/api";

interface UserOut { user_id: string; role: string; }

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);

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

const CARDS = [
  {
    href: "/admin/kb",
    icon: "📚",
    label: "Base de Conhecimento",
    desc: "Criar, editar, arquivar e re-ingerir artigos na RAG",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/categories",
    icon: "🗂",
    label: "Categorias",
    desc: "Gerenciar categorias de chamados — ativar, criar, editar",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/departments",
    icon: "🏢",
    label: "Departamentos",
    desc: "Cadastrar e gerenciar departamentos da empresa",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/applications",
    icon: "🔗",
    label: "Aplicações",
    desc: "Catálogo de sistemas internos e controle de acesso por usuário",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/users",
    icon: "👥",
    label: "Usuários & Papéis",
    desc: "Conceder e revogar papéis de TI para usuários",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/sla",
    icon: "⏱",
    label: "SLA",
    desc: "Configurar prazos de primeira resposta e resolução por prioridade",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/reports",
    icon: "📊",
    label: "Relatórios",
    desc: "Exportar chamados em CSV e ver detalhes de CSAT",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/ai-monitor",
    icon: "🤖",
    label: "Monitor IA",
    desc: "Logs de chamadas ao LLM — tokens, latência, guardrails",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
  {
    href: "/admin/assets",
    icon: "🖥",
    label: "Patrimônio de TI",
    desc: "Controle de notebooks, smartphones e outros equipamentos com histórico de titular",
    roles: ["it_admin", "it_lead", "it_agent"],
  },
];

export default async function AdminHubPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) redirect("/login");

  const user = await getMe(session);
  if (!user || !IT_ROLES.has(user.role)) redirect("/dashboard");

  return (
    <div className="p-6 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-lg font-semibold text-zinc-100">Administração</h1>
        <p className="text-xs text-zinc-500 mt-0.5">Gerenciamento do IT Helpdesk</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {CARDS.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 hover:bg-zinc-800/50 transition-colors group"
          >
            <div className="flex items-center gap-2.5 mb-2">
              <span className="text-xl">{card.icon}</span>
              <span className="text-sm font-medium text-zinc-200 group-hover:text-white transition-colors">
                {card.label}
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 leading-relaxed">{card.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
