import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { buildApiUrl } from "@/lib/api";

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
  conversation_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  transcript: string | null;
}

async function getTicket(id: string): Promise<TicketOut | null> {
  const cookieStore = await cookies();
  const session =
    cookieStore.get("sds_session") ?? cookieStore.get("__Host-sds_session");
  if (!session) return null;

  const res = await fetch(buildApiUrl(`/api/v1/tickets/${id}`), {
    headers: { Cookie: `${session.name}=${session.value}` },
    cache: "no-store",
  });

  if (res.status === 404 || res.status === 403) return null;
  if (!res.ok) throw new Error(`Erro ao carregar chamado: ${res.status}`);
  return res.json() as Promise<TicketOut>;
}

const STATUS_LABEL: Record<string, string> = {
  NEW: "Novo",
  OPEN: "Aberto",
  PENDING: "Pendente",
  RESOLVED: "Resolvido",
  CLOSED: "Fechado",
};

const STATUS_COLOR: Record<string, string> = {
  NEW: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  OPEN: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  PENDING: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  RESOLVED: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  CLOSED: "bg-muted text-muted-foreground",
};

const PRIORITY_LABEL: Record<string, string> = {
  low: "Baixa",
  normal: "Normal",
  high: "Alta",
  urgent: "Urgente",
};

const PRIORITY_COLOR: Record<string, string> = {
  low: "bg-muted text-muted-foreground",
  normal: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  urgent: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
};

export default async function TicketPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const ticket = await getTicket(id);

  if (!ticket) notFound();

  const createdAt = new Date(ticket.created_at).toLocaleString("pt-BR");
  const updatedAt = new Date(ticket.updated_at).toLocaleString("pt-BR");

  return (
    <main className="min-h-screen bg-muted/20 p-6 md:p-8">
      <div className="max-w-3xl mx-auto space-y-5">
        <a
          href="/dashboard"
          className="inline-block text-sm text-muted-foreground hover:underline"
        >
          ← Dashboard
        </a>

        <div className="rounded-xl border bg-card p-6 shadow-sm space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground font-mono">
                {ticket.ticket_number}
              </p>
              <h1 className="text-xl font-semibold mt-1 leading-snug">
                {ticket.title}
              </h1>
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
                  PRIORITY_COLOR[ticket.priority] ??
                  "bg-muted text-muted-foreground"
                }`}
              >
                {PRIORITY_LABEL[ticket.priority] ?? ticket.priority}
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
                <span
                  key={tag}
                  className="text-xs bg-muted px-2 py-0.5 rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-6 text-xs text-muted-foreground border-t pt-4">
            <span>Criado em {createdAt}</span>
            <span>Atualizado em {updatedAt}</span>
          </div>
        </div>

        {ticket.transcript && (
          <div className="rounded-xl border bg-card p-6 shadow-sm">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
              Transcrição do chat
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
