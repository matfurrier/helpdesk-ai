import { Suspense } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { buildApiUrl } from "@/lib/api";
import { FilterBar } from "@/components/tickets/filter-bar";

interface TicketListItem {
  id: string;
  number: number;
  ticket_number: string;
  title: string;
  status: string;
  priority: string;
  requester_id: string;
  requester_name: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface TicketListOut {
  items: TicketListItem[];
  total: number;
}

interface FilterOptionsOut {
  years: number[];
  departments: { id: number; name: string }[];
  users: { id: string; name: string }[];
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

function buildFilterQuery(sp: Record<string, string | string[] | undefined>) {
  const p = new URLSearchParams();
  if (sp.year) p.set("year", String(sp.year));
  if (sp.month) p.set("month", String(sp.month));
  if (sp.dept_id) p.set("dept_id", String(sp.dept_id));
  if (sp.user_id) p.set("user_id", String(sp.user_id));
  const qs = p.toString();
  return qs ? `?${qs}` : "";
}

export default async function TicketsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) redirect("/login");

  const fq = buildFilterQuery(sp);
  const ticketsUrl = fq
    ? `${fq}&limit=100`
    : "?limit=100";

  let data: TicketListOut | null = null;
  let filterOptions: FilterOptionsOut | null = null;
  try {
    const [ticketsRes, filterRes] = await Promise.all([
      fetch(buildApiUrl(`/api/v1/tickets/${ticketsUrl}`), {
        headers: { Cookie: `${session.name}=${session.value}` },
        cache: "no-store",
      }),
      fetch(buildApiUrl("/api/v1/tickets/filter-options"), {
        headers: { Cookie: `${session.name}=${session.value}` },
        cache: "no-store",
      }),
    ]);
    if (ticketsRes.ok) data = await ticketsRes.json() as TicketListOut;
    if (filterRes.ok) filterOptions = await filterRes.json() as FilterOptionsOut;
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

      {/* Filter bar */}
      {filterOptions && (
        <Suspense fallback={null}>
          <FilterBar options={filterOptions} />
        </Suspense>
      )}

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
                      {t.requester_name && (
                        <p className="text-[11px] text-zinc-600 mt-0.5 truncate max-w-[240px]">{t.requester_name}</p>
                      )}
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
                        {t.assignee_name ?? (t.assignee_id ? t.assignee_id.slice(0, 8) + "…" : <span className="text-zinc-700">—</span>)}
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
