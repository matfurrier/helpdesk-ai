import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { buildApiUrl } from "@/lib/api";
import { TicketActions } from "@/components/tickets/ticket-actions";

interface TicketOut {
  id: string;
  number: number;
  ticket_number: string;
  title: string;
  summary: string;
  status: string;
  priority: string;
  category_id: string | null;
  requester_id: string;
  assignee_id: string | null;
  conversation_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  transcript: string | null;
}

interface TicketMessageOut {
  id: string;
  author_id: string;
  author_role: string;
  visibility: string;
  body: string;
  created_at: string;
}

interface UserOut {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

const IT_ROLES = new Set(["it_agent", "it_lead", "it_admin"]);

async function serverFetch<T>(path: string, session: { name: string; value: string }): Promise<T | null> {
  try {
    const res = await fetch(buildApiUrl(path), {
      headers: { Cookie: `${session.name}=${session.value}` },
      cache: "no-store",
    });
    if (res.status === 404 || res.status === 403) return null;
    if (!res.ok) throw new Error(`${res.status}`);
    return res.json() as Promise<T>;
  } catch {
    return null;
  }
}

const STATUS_LABEL: Record<string, string> = {
  NEW: "Novo", TRIAGE: "Triagem", IN_PROGRESS: "Em andamento",
  WAITING_USER: "Aguardando usuário", RESOLVED: "Resolvido",
  CLOSED: "Fechado", AUTO_RESOLVED: "Resolvido auto",
  CANCELLED: "Cancelado", REOPENED: "Reaberto",
};

const STATUS_COLOR: Record<string, string> = {
  NEW:          "bg-blue-100 text-blue-800",
  TRIAGE:       "bg-purple-100 text-purple-800",
  IN_PROGRESS:  "bg-yellow-100 text-yellow-800",
  WAITING_USER: "bg-orange-100 text-orange-800",
  RESOLVED:     "bg-green-100 text-green-800",
  CLOSED:       "bg-muted text-muted-foreground",
  CANCELLED:    "bg-muted text-muted-foreground",
  REOPENED:     "bg-red-100 text-red-800",
};

const PRIORITY_COLOR: Record<string, string> = {
  low:    "bg-muted text-muted-foreground",
  normal: "bg-blue-100 text-blue-800",
  high:   "bg-orange-100 text-orange-800",
  urgent: "bg-red-100 text-red-800",
};

export default async function TicketPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const cookieStore = await cookies();
  const session =
    cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) notFound();

  const [ticket, user, messages] = await Promise.all([
    serverFetch<TicketOut>(`/api/v1/tickets/${id}`, session),
    serverFetch<UserOut>("/api/v1/auth/me", session),
    serverFetch<TicketMessageOut[]>(`/api/v1/tickets/${id}/messages`, session),
  ]);

  if (!ticket || !user) notFound();

  const isAgent = IT_ROLES.has(user.role);
  const createdAt = new Date(ticket.created_at).toLocaleString("pt-BR");
  const updatedAt = new Date(ticket.updated_at).toLocaleString("pt-BR");

  // Filter out the system transcript message from the thread view
  const threadMessages = (messages ?? []).filter((m) => m.author_role !== "system");

  return (
    <main className="min-h-screen bg-muted/20 p-6 md:p-8">
      <div className="max-w-3xl mx-auto space-y-5">
        <a
          href="/dashboard"
          className="inline-block text-sm text-muted-foreground hover:underline"
        >
          ← Dashboard
        </a>

        {/* Ticket header */}
        <div className="rounded-xl border bg-card p-6 shadow-sm space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground font-mono">
                {ticket.ticket_number}
              </p>
              <h1 className="text-xl font-semibold mt-1 leading-snug">{ticket.title}</h1>
            </div>
            <div className="flex gap-2 flex-shrink-0 flex-wrap justify-end">
              <span
                className={`text-xs px-2 py-1 rounded-full font-medium ${
                  STATUS_COLOR[ticket.status] ?? "bg-muted text-muted-foreground"
                }`}
              >
                {STATUS_LABEL[ticket.status] ?? ticket.status}
              </span>
              <span
                className={`text-xs px-2 py-1 rounded-full font-medium ${
                  PRIORITY_COLOR[ticket.priority] ?? "bg-muted text-muted-foreground"
                }`}
              >
                {ticket.priority}
              </span>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
              Resumo
            </p>
            <p className="text-sm leading-relaxed">{ticket.summary}</p>
          </div>

          {ticket.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {ticket.tags.map((tag) => (
                <span key={tag} className="text-xs bg-muted px-2 py-0.5 rounded-full">
                  {tag}
                </span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-6 text-xs text-muted-foreground border-t pt-4">
            <span>Criado em {createdAt}</span>
            <span>Atualizado em {updatedAt}</span>
            {isAgent && ticket.assignee_id && (
              <span>Responsável: <code className="font-mono">{ticket.assignee_id.slice(0, 8)}…</code></span>
            )}
          </div>
        </div>

        {/* Interactive panel (client component) */}
        <TicketActions
          ticketId={ticket.id}
          currentStatus={ticket.status}
          assigneeId={ticket.assignee_id}
          currentUserId={user.user_id}
          isAgent={isAgent}
          initialMessages={threadMessages}
        />

        {/* Transcript (collapsible, IT only) */}
        {isAgent && ticket.transcript && (
          <details className="rounded-xl border bg-card shadow-sm">
            <summary className="px-5 py-4 text-xs font-medium text-muted-foreground uppercase tracking-wide cursor-pointer select-none">
              Transcrição do chat IA
            </summary>
            <pre className="px-5 pb-5 text-xs whitespace-pre-wrap font-mono leading-relaxed text-muted-foreground">
              {ticket.transcript}
            </pre>
          </details>
        )}

        {/* Show transcript to requester too */}
        {!isAgent && ticket.transcript && (
          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
              Histórico do chat
            </p>
            <pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed text-muted-foreground">
              {ticket.transcript}
            </pre>
          </div>
        )}
      </div>
    </main>
  );
}
