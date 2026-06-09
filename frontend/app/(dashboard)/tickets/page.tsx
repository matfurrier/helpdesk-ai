import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { buildApiUrl } from "@/lib/api";

interface TicketListItem {
  id: string;
  number: number;
  ticket_number: string;
  title: string;
  status: string;
  priority: string;
  requester_id: string;
  assignee_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface TicketListOut {
  items: TicketListItem[];
  total: number;
}

const TZ = "America/Sao_Paulo";
function fmtDate(s: string) {
  return new Date(s).toLocaleDateString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "2-digit" });
}

const STATUS_DOT: Record<string, string> = {
  NEW: "bg-blue-500", TRIAGE: "bg-purple-500", IN_PROGRESS: "bg-yellow-400",
  WAITING_USER: "bg-orange-500", RESOLVED: "bg-green-500",
  CLOSED: "bg-zinc-500", REOPENED: "bg-red-500", CANCELLED: "bg-zinc-600",
};
const STATUS_LABEL: Record<string, string> = {
  NEW: "Novo", TRIAGE: "Triagem", IN_PROGRESS: "Em andamento",
  WAITING_USER: "Aguardando", RESOLVED: "Resolvido",
  CLOSED: "Fechado", REOPENED: "Reaberto", CANCELLED: "Cancelado",
};
const PRIORITY_CHIP: Record<string, string> = {
  urgent: "bg-red-500/15 text-red-400 ring-1 ring-red-500/30",
  high:   "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/30",
  normal: "bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30",
  low:    "bg-zinc-500/15 text-zinc-400 ring-1 ring-zinc-500/30",
};

export default async function TicketsPage() {
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) redirect("/login");

  let data: TicketListOut | null = null;
  try {
    const res = await fetch(buildApiUrl("/api/v1/tickets/?limit=100"), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (res.ok) data = await res.json() as TicketListOut;
  } catch { /* ignore */ }

  const items = data?.items ?? [];

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold text-zinc-100">Chamados</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-500">{data?.total ?? 0} no total</span>
          <a
            href="/chat/new"
            className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
          >
            + Novo
          </a>
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        {items.length === 0 ? (
          <p className="text-sm text-zinc-500 text-center py-12">Nenhum chamado encontrado.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-zinc-500 uppercase tracking-wide border-b border-zinc-800">
                  <th className="text-left px-4 py-2.5 font-medium">Chamado</th>
                  <th className="text-left px-3 py-2.5 font-medium hidden sm:table-cell">Status</th>
                  <th className="text-left px-3 py-2.5 font-medium">Prioridade</th>
                  <th className="text-left px-3 py-2.5 font-medium hidden lg:table-cell">Responsável</th>
                  <th className="text-left px-3 py-2.5 font-medium hidden md:table-cell">Criado</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {items.map((t) => (
                  <tr key={t.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-4 py-2.5">
                      <p className="font-mono text-[11px] text-zinc-500">{t.ticket_number}</p>
                      <p className="text-xs font-medium text-zinc-200 truncate max-w-[240px] mt-0.5">{t.title}</p>
                    </td>
                    <td className="px-3 py-2.5 hidden sm:table-cell">
                      <span className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATUS_DOT[t.status] ?? "bg-zinc-500"}`} />
                        <span className="text-xs text-zinc-400">{STATUS_LABEL[t.status] ?? t.status}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`text-[11px] px-1.5 py-0.5 rounded font-medium ${PRIORITY_CHIP[t.priority] ?? ""}`}>
                        {t.priority}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 hidden lg:table-cell">
                      <span className="text-xs text-zinc-500">
                        {t.assignee_id ? t.assignee_id.slice(0, 8) + "…" : <span className="text-zinc-700">—</span>}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 hidden md:table-cell">
                      <span className="text-xs text-zinc-500">{fmtDate(t.created_at)}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <a href={`/tickets/${t.id}`} className="text-xs text-blue-400 hover:text-blue-300">→</a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
