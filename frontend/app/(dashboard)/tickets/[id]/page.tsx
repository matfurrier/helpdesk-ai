import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { buildApiUrl } from "@/lib/api";
import { TicketActions } from "@/components/tickets/ticket-actions";

interface TicketOut {
  id: string; number: number; ticket_number: string; title: string; summary: string;
  status: string; priority: string; category_id: string | null;
  category_name: string | null; category_slug: string | null;
  requester_id: string; requester_name: string | null;
  assignee_id: string | null; assignee_name: string | null; conversation_id: string | null;
  tags: string[];
  first_response_due_at: string | null; resolution_due_at: string | null;
  first_response_at: string | null; resolved_at: string | null;
  created_at: string; updated_at: string; transcript: string | null;
}
interface TicketMessageOut {
  id: string; author_id: string; author_role: string; visibility: string; body: string; created_at: string;
}
interface UserOut { user_id: string; name: string; email: string; role: string; }
interface Category { id: string; slug: string; name: string; }

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);
const TZ = "America/Sao_Paulo";
function fmtDt(s: string) { return new Date(s).toLocaleString("pt-BR", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); }

async function serverFetch<T>(path: string, session: { name: string; value: string }): Promise<T | null> {
  try {
    const res = await fetch(buildApiUrl(path), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (res.status === 404 || res.status === 403) return null;
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json() as Promise<T>;
  } catch { return null; }
}

const TERMINAL_STATUSES = new Set(["RESOLVED", "CLOSED", "AUTO_RESOLVED", "CANCELLED"]);

function getSlaInfo(ticket: TicketOut): { label: string; cls: string; detail: string } | null {
  if (!ticket.resolution_due_at) return null;
  const due = new Date(ticket.resolution_due_at);
  if (TERMINAL_STATUSES.has(ticket.status) && ticket.resolved_at) {
    const breached = new Date(ticket.resolved_at) > due;
    return breached
      ? { label: "SLA violado", cls: "bg-red-500/15 text-red-400 ring-1 ring-red-500/30", detail: `Prazo era ${fmtDt(ticket.resolution_due_at)}` }
      : { label: "SLA cumprido", cls: "bg-green-500/15 text-green-400 ring-1 ring-green-500/30", detail: `Resolvido antes de ${fmtDt(ticket.resolution_due_at)}` };
  }
  const now = Date.now();
  const duems = due.getTime();
  if (now > duems) {
    const overMins = Math.floor((now - duems) / 60000);
    const overLabel = overMins < 60 ? `${overMins}min` : `${Math.floor(overMins / 60)}h`;
    return { label: `Vencido há ${overLabel}`, cls: "bg-red-500/15 text-red-400 ring-1 ring-red-500/30", detail: `Prazo: ${fmtDt(ticket.resolution_due_at)}` };
  }
  const remainMins = Math.floor((duems - now) / 60000);
  const remainLabel = remainMins < 60 ? `${remainMins}min restantes` : `${Math.floor(remainMins / 60)}h restantes`;
  const cls = remainMins <= 120
    ? "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/30"
    : "bg-green-500/15 text-green-400 ring-1 ring-green-500/30";
  return { label: remainLabel, cls, detail: `Prazo: ${fmtDt(ticket.resolution_due_at)}` };
}

const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30",
  TRIAGE: "bg-purple-500/15 text-purple-400 ring-1 ring-purple-500/30",
  IN_PROGRESS: "bg-yellow-500/15 text-yellow-400 ring-1 ring-yellow-500/30",
  WAITING_USER: "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/30",
  RESOLVED: "bg-green-500/15 text-green-400 ring-1 ring-green-500/30",
  CLOSED: "bg-zinc-500/15 text-zinc-400 ring-1 ring-zinc-500/30",
  CANCELLED: "bg-zinc-500/15 text-zinc-400 ring-1 ring-zinc-500/30",
  REOPENED: "bg-red-500/15 text-red-400 ring-1 ring-red-500/30",
};
const STATUS_LABEL: Record<string, string> = {
  NEW: "Novo", TRIAGE: "Triagem", IN_PROGRESS: "Em andamento",
  WAITING_USER: "Aguardando usuário", RESOLVED: "Resolvido",
  CLOSED: "Fechado", CANCELLED: "Cancelado", REOPENED: "Reaberto",
};
const PRIORITY_COLOR: Record<string, string> = {
  urgent: "bg-red-500/15 text-red-400 ring-1 ring-red-500/30",
  high:   "bg-orange-500/15 text-orange-400 ring-1 ring-orange-500/30",
  normal: "bg-blue-500/15 text-blue-400 ring-1 ring-blue-500/30",
  low:    "bg-zinc-500/15 text-zinc-400 ring-1 ring-zinc-500/30",
};

export default async function TicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cookieStore = await cookies();
  const session = cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) notFound();

  const [ticket, user, messages, categories] = await Promise.all([
    serverFetch<TicketOut>(`/api/v1/tickets/${id}`, session),
    serverFetch<UserOut>("/api/v1/auth/me", session),
    serverFetch<TicketMessageOut[]>(`/api/v1/tickets/${id}/messages`, session),
    serverFetch<Category[]>("/api/v1/tickets/categories", session),
  ]);
  if (!ticket || !user) notFound();

  const isAgent = IT_ROLES.has(user.role);
  const threadMessages = (messages ?? []).filter((m) => m.author_role !== "system");
  const requesterDisplay = ticket.requester_name ?? ticket.requester_id.slice(0, 8) + "…";
  const slaInfo = getSlaInfo(ticket);

  return (
    <div className="p-5 max-w-3xl space-y-4">
      {/* Header */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
        <div className="flex items-start gap-3 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              <span className="font-mono text-xs text-zinc-500">{ticket.ticket_number}</span>
              <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[ticket.status] ?? "bg-zinc-500/15 text-zinc-400"}`}>
                {STATUS_LABEL[ticket.status] ?? ticket.status}
              </span>
              <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLOR[ticket.priority] ?? ""}`}>
                {ticket.priority}
              </span>
              {ticket.category_name && (
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-zinc-700/60 text-zinc-300">
                  {ticket.category_name}
                </span>
              )}
              {slaInfo && (
                <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${slaInfo.cls}`} title={slaInfo.detail}>
                  SLA: {slaInfo.label}
                </span>
              )}
            </div>
            <h1 className="text-base font-semibold text-zinc-100 leading-snug">{ticket.title}</h1>
            <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1.5 text-[11px] text-zinc-500">
              <span>Solicitante: <span className="text-zinc-300">{requesterDisplay}</span></span>
              <span>Criado: <span className="text-zinc-300">{fmtDt(ticket.created_at)}</span></span>
              {isAgent && ticket.assignee_id && (
                <span>Responsável: <span className="text-zinc-300">{ticket.assignee_name ?? "—"}</span></span>
              )}
              {isAgent && !ticket.assignee_id && (
                <span className="text-zinc-600">Sem responsável</span>
              )}
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="mt-3 pt-3 border-t border-zinc-800">
          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wide mb-1">Resumo</p>
          <p className="text-xs text-zinc-300 leading-relaxed">{ticket.summary}</p>
        </div>

        {/* Tags */}
        {ticket.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {ticket.tags.map((tag) => (
              <span key={tag} className="text-[11px] bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-full">{tag}</span>
            ))}
          </div>
        )}
      </div>

      {/* Interactive panel */}
      <TicketActions
        ticketId={ticket.id}
        currentStatus={ticket.status}
        assigneeId={ticket.assignee_id}
        categorySlug={ticket.category_slug}
        categories={categories ?? []}
        currentUserId={user.user_id}
        isAgent={isAgent}
        initialMessages={threadMessages}
      />

      {/* Transcript (agents only, collapsible) */}
      {isAgent && ticket.transcript && (
        <details className="bg-zinc-900 border border-zinc-800 rounded-lg group">
          <summary className="px-4 py-3 text-[11px] font-medium text-zinc-500 uppercase tracking-wide cursor-pointer select-none hover:text-zinc-400 list-none flex items-center gap-2">
            <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
            Transcrição do chat IA
          </summary>
          <pre className="px-4 pb-4 text-[11px] whitespace-pre-wrap font-mono leading-relaxed text-zinc-500 border-t border-zinc-800 pt-3">
            {ticket.transcript}
          </pre>
        </details>
      )}

      {/* Transcript for requester */}
      {!isAgent && ticket.transcript && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
          <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wide mb-3">Histórico do chat</p>
          <pre className="text-[11px] whitespace-pre-wrap font-mono leading-relaxed text-zinc-500">{ticket.transcript}</pre>
        </div>
      )}
    </div>
  );
}
