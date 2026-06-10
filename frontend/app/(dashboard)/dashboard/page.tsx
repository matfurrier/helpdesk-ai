import { Suspense } from "react";
import { cookies } from "next/headers";
import { buildApiUrl } from "@/lib/api";
import { FilterBar } from "@/components/tickets/filter-bar";

interface UserOut { user_id: string; name: string; email: string; role: string; }
interface TicketStatsOut { total_count: number; open_count: number; pending_count: number; resolved_today: number; unassigned_count: number; avg_first_response_minutes: number | null; csat_avg_rating: number | null; csat_total_responses: number; }
interface TicketListItem { id: string; number: number; ticket_number: string; title: string; status: string; priority: string; requester_id: string; requester_name: string | null; assignee_id: string | null; assignee_name: string | null; tags: string[]; created_at: string; updated_at: string; }
interface TicketListOut { items: TicketListItem[]; total: number; }
interface FilterOptionsOut {
  years: number[];
  departments: { id: number; name: string }[];
  users: { id: string; name: string }[];
  categories?: { id: string; slug: string; name: string }[];
}

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);

const TZ = "America/Sao_Paulo";
function fmtDate(s: string) { return new Date(s).toLocaleDateString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit" }); }

async function serverFetch<T>(path: string, session: { name: string; value: string }): Promise<T | null> {
  try {
    const res = await fetch(buildApiUrl(path), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch { return null; }
}

function buildFilterQuery(sp: Record<string, string | string[] | undefined>) {
  const p = new URLSearchParams();
  if (sp.year) p.set("year", String(sp.year));
  if (sp.month) p.set("month", String(sp.month));
  if (sp.dept_id) p.set("dept_id", String(sp.dept_id));
  if (sp.user_id) p.set("user_id", String(sp.user_id));
  const qs = p.toString();
  return qs ? `?${qs}` : "";
}

// Status/priority badge maps
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

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3">
      <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">{label}</p>
      <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
      {sub && <p className="text-[11px] text-zinc-500 mt-0.5">{sub}</p>}
    </div>
  );
}

function StarRating({ value }: { value: number }) {
  return (
    <span className="inline-flex gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <span key={s} className={s <= Math.round(value) ? "text-yellow-400" : "text-zinc-700"}>★</span>
      ))}
    </span>
  );
}

// Employee dashboard (no sidebar duplication — layout handles that)
function EmployeeDashboard({ user }: { user: UserOut }) {
  return (
    <div className="p-6 max-w-3xl">
      <h1 className="text-lg font-semibold text-zinc-100 mb-1">Olá, {user.name}</h1>
      <p className="text-sm text-zinc-400 mb-6">Bem-vindo ao IT Helpdesk</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <a href="/chat/new" className="bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-lg p-5 transition-colors group">
          <div className="text-2xl mb-2">💬</div>
          <h2 className="text-sm font-semibold text-zinc-200 group-hover:text-white">Abrir chamado</h2>
          <p className="text-xs text-zinc-500 mt-1">Descreva seu problema e a IA vai te ajudar</p>
        </a>
        <a href="/tickets" className="bg-zinc-900 border border-zinc-800 hover:border-zinc-600 rounded-lg p-5 transition-colors group">
          <div className="text-2xl mb-2">📋</div>
          <h2 className="text-sm font-semibold text-zinc-200 group-hover:text-white">Meus chamados</h2>
          <p className="text-xs text-zinc-500 mt-1">Acompanhe o status dos seus tickets</p>
        </a>
      </div>
    </div>
  );
}

// IT dashboard
function ItDashboard({
  stats,
  queue,
  filterOptions,
}: {
  stats: TicketStatsOut | null;
  queue: TicketListOut | null;
  filterOptions: FilterOptionsOut | null;
}) {
  const avgFRT = stats?.avg_first_response_minutes
    ? stats.avg_first_response_minutes < 60
      ? `${Math.round(stats.avg_first_response_minutes)} min`
      : `${(stats.avg_first_response_minutes / 60).toFixed(1)} h`
    : "—";

  return (
    <div className="p-5 space-y-5">
      {/* Filter bar */}
      {filterOptions && (
        <Suspense fallback={null}>
          <FilterBar options={filterOptions} />
        </Suspense>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard label="Abertos" value={stats?.open_count ?? "—"} />
        <KpiCard label="Aguardando usuário" value={stats?.pending_count ?? "—"} />
        <KpiCard label="Resolvidos hoje" value={stats?.resolved_today ?? "—"} />
        <KpiCard
          label="1ª resposta (média)"
          value={avgFRT}
          sub={stats?.unassigned_count ? `${stats.unassigned_count} sem dono` : undefined}
        />
        {/* CSAT KPI */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3">
          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider">Satisfação (CSAT)</p>
          {stats?.csat_avg_rating != null ? (
            <>
              <p className="text-2xl font-bold text-white mt-0.5">{stats.csat_avg_rating.toFixed(1)}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <StarRating value={stats.csat_avg_rating} />
                <span className="text-[11px] text-zinc-500">{stats.csat_total_responses} resp.</span>
              </div>
            </>
          ) : (
            <>
              <p className="text-2xl font-bold text-white mt-0.5">—</p>
              <p className="text-[11px] text-zinc-500 mt-0.5">Sem avaliações</p>
            </>
          )}
        </div>
      </div>

      {/* Quick action */}
      <div className="flex gap-2">
        <a href="/chat/new" className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors">
          + Abrir chat
        </a>
      </div>

      {/* Ticket queue */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-200">Fila de chamados</h2>
          <span className="text-xs text-zinc-500">{queue?.total ?? 0} total</span>
        </div>

        {!queue || queue.items.length === 0 ? (
          <p className="text-sm text-zinc-500 text-center py-10">Nenhum chamado ativo.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[11px] text-zinc-500 uppercase tracking-wide border-b border-zinc-800/60">
                  <th className="text-left px-4 py-2 font-medium">Chamado</th>
                  <th className="text-left px-3 py-2 font-medium hidden sm:table-cell">Status</th>
                  <th className="text-left px-3 py-2 font-medium">Prioridade</th>
                  <th className="text-left px-3 py-2 font-medium hidden md:table-cell">Solicitante</th>
                  <th className="text-left px-3 py-2 font-medium hidden lg:table-cell">Responsável</th>
                  <th className="text-left px-3 py-2 font-medium hidden xl:table-cell">Data</th>
                  <th className="w-8"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {queue.items.map((t) => (
                  <tr key={t.id} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-4 py-2.5">
                      <p className="font-mono text-[11px] text-zinc-500">{t.ticket_number}</p>
                      <p className="text-zinc-200 truncate max-w-[200px] text-xs font-medium mt-0.5">{t.title}</p>
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
                    <td className="px-3 py-2.5 hidden md:table-cell">
                      <span className="text-xs text-zinc-400 truncate max-w-[120px] block">
                        {t.requester_name ?? <span className="text-zinc-600">—</span>}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 hidden lg:table-cell">
                      <span className="text-xs text-zinc-500 truncate max-w-[120px] block">
                        {t.assignee_name ?? (t.assignee_id ? <span className="text-zinc-600">—</span> : <span className="text-zinc-700">Sem dono</span>)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 hidden xl:table-cell">
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

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) return null;

  const user = await serverFetch<UserOut>("/api/v1/auth/me", session);
  if (!user) return null;

  if (!IT_ROLES.has(user.role)) {
    return <EmployeeDashboard user={user} />;
  }

  const fq = buildFilterQuery(sp);
  const ticketsUrl = fq ? `/api/v1/tickets/${fq}&limit=30` : "/api/v1/tickets/?limit=30";

  const [stats, queue, filterOptions] = await Promise.all([
    serverFetch<TicketStatsOut>(`/api/v1/tickets/stats${fq}`, session),
    serverFetch<TicketListOut>(ticketsUrl, session),
    serverFetch<FilterOptionsOut>("/api/v1/tickets/filter-options", session),
  ]);

  return <ItDashboard stats={stats} queue={queue} filterOptions={filterOptions} />;
}
