import { cookies } from "next/headers";
import { buildApiUrl } from "@/lib/api";

interface UserOut {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

interface TicketStatsOut {
  open_count: number;
  pending_count: number;
  resolved_today: number;
  unassigned_count: number;
  avg_first_response_minutes: number | null;
}

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

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);

async function serverFetch<T>(path: string, sessionCookie: { name: string; value: string }): Promise<T | null> {
  try {
    const res = await fetch(buildApiUrl(path), {
      headers: { Cookie: `${sessionCookie.name}=${sessionCookie.value}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

async function getSession() {
  const cookieStore = await cookies();
  return cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
}

// ---------------------------------------------------------------------------
// Employee dashboard (current behaviour)
// ---------------------------------------------------------------------------

function EmployeeDashboard({ user }: { user: UserOut }) {
  return (
    <main className="min-h-screen bg-muted/20 p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-8">
          <h1 className="text-2xl font-semibold">Olá, {user.name}</h1>
          <p className="text-sm text-muted-foreground mt-1">Bem-vindo ao IT Helpdesk</p>
        </header>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <a
            href="/chat/new"
            className="rounded-xl border bg-card p-6 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
          >
            <div className="text-4xl mb-3">💬</div>
            <h2 className="font-semibold text-lg">Abrir chamado</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Descreva seu problema e a IA vai te ajudar
            </p>
          </a>

          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <div className="text-4xl mb-3">📋</div>
            <h2 className="font-semibold text-lg">Meus chamados</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Acompanhe o status dos seus tickets
            </p>
          </div>

          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <div className="text-4xl mb-3">📚</div>
            <h2 className="font-semibold text-lg">Base de conhecimento</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Artigos e resoluções documentadas
            </p>
          </div>
        </div>

        <p className="mt-8 text-xs text-muted-foreground">
          Papel: <code className="font-mono">{user.role}</code> · ID: {user.user_id}
        </p>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// IT dashboard
// ---------------------------------------------------------------------------

const STATUS_LABEL: Record<string, string> = {
  NEW: "Novo", TRIAGE: "Triagem", IN_PROGRESS: "Em andamento",
  WAITING_USER: "Aguardando usuário", RESOLVED: "Resolvido",
  CLOSED: "Fechado", AUTO_RESOLVED: "Resolvido auto", CANCELLED: "Cancelado",
  REOPENED: "Reaberto",
};

const STATUS_DOT: Record<string, string> = {
  NEW: "bg-blue-500", TRIAGE: "bg-purple-500", IN_PROGRESS: "bg-yellow-500",
  WAITING_USER: "bg-orange-500", RESOLVED: "bg-green-500",
  CLOSED: "bg-gray-400", REOPENED: "bg-red-500",
};

const PRIORITY_BADGE: Record<string, string> = {
  urgent: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  normal: "bg-blue-100 text-blue-800",
  low: "bg-muted text-muted-foreground",
};

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
}

function ItDashboard({
  user,
  stats,
  queue,
}: {
  user: UserOut;
  stats: TicketStatsOut | null;
  queue: TicketListOut | null;
}) {
  const avgFRT = stats?.avg_first_response_minutes
    ? stats.avg_first_response_minutes < 60
      ? `${Math.round(stats.avg_first_response_minutes)} min`
      : `${(stats.avg_first_response_minutes / 60).toFixed(1)} h`
    : "—";

  return (
    <main className="min-h-screen bg-muted/20">
      {/* Header */}
      <header className="border-b bg-card px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Painel de TI</h1>
          <p className="text-xs text-muted-foreground">{user.name} · {user.role}</p>
        </div>
        <a
          href="/chat/new"
          className="text-xs px-3 py-1.5 rounded-md border hover:bg-muted transition-colors"
        >
          + Abrir chat
        </a>
      </header>

      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Abertos" value={stats?.open_count ?? "—"} />
          <KpiCard label="Aguardando usuário" value={stats?.pending_count ?? "—"} />
          <KpiCard label="Resolvidos hoje" value={stats?.resolved_today ?? "—"} />
          <KpiCard
            label="Tempo 1ª resposta"
            value={avgFRT}
            sub={stats?.unassigned_count ? `${stats.unassigned_count} sem responsável` : undefined}
          />
        </div>

        {/* Ticket queue */}
        <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b">
            <h2 className="text-sm font-semibold">Fila de chamados</h2>
            <span className="text-xs text-muted-foreground">{queue?.total ?? 0} no total</span>
          </div>

          {!queue || queue.items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-10">
              Nenhum chamado ativo.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-muted-foreground border-b">
                  <th className="text-left px-5 py-2 font-medium">Chamado</th>
                  <th className="text-left px-3 py-2 font-medium hidden md:table-cell">Status</th>
                  <th className="text-left px-3 py-2 font-medium">Prioridade</th>
                  <th className="text-left px-3 py-2 font-medium hidden lg:table-cell">Responsável</th>
                  <th className="text-left px-3 py-2 font-medium hidden lg:table-cell">Criado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {queue.items.map((t) => (
                  <tr key={t.id} className="border-b last:border-0 hover:bg-muted/40 transition-colors">
                    <td className="px-5 py-3">
                      <p className="font-mono text-xs text-muted-foreground">{t.ticket_number}</p>
                      <p className="font-medium truncate max-w-xs">{t.title}</p>
                    </td>
                    <td className="px-3 py-3 hidden md:table-cell">
                      <span className="flex items-center gap-1.5">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[t.status] ?? "bg-gray-400"}`} />
                        <span className="text-xs">{STATUS_LABEL[t.status] ?? t.status}</span>
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_BADGE[t.priority] ?? ""}`}>
                        {t.priority}
                      </span>
                    </td>
                    <td className="px-3 py-3 hidden lg:table-cell">
                      <span className="text-xs text-muted-foreground">
                        {t.assignee_id ? t.assignee_id.slice(0, 8) + "…" : "—"}
                      </span>
                    </td>
                    <td className="px-3 py-3 hidden lg:table-cell">
                      <span className="text-xs text-muted-foreground">
                        {new Date(t.created_at).toLocaleDateString("pt-BR")}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <a
                        href={`/tickets/${t.id}`}
                        className="text-xs text-primary hover:underline"
                      >
                        Abrir →
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default async function DashboardPage() {
  const session = await getSession();
  if (!session) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground text-sm">
          <a href="/login" className="hover:underline">Faça login</a> para continuar.
        </p>
      </main>
    );
  }

  const user = await serverFetch<UserOut>("/api/v1/auth/me", session);
  if (!user) return null;

  if (!IT_ROLES.has(user.role)) {
    return <EmployeeDashboard user={user} />;
  }

  // Fetch IT data in parallel
  const [stats, queue] = await Promise.all([
    serverFetch<TicketStatsOut>("/api/v1/tickets/stats", session),
    serverFetch<TicketListOut>(
      "/api/v1/tickets/?limit=20",
      session,
    ),
  ]);

  return <ItDashboard user={user} stats={stats} queue={queue} />;
}
