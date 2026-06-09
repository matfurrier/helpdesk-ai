"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { fetchCsrfToken } from "@/lib/sse";

interface TicketMessageOut {
  id: string;
  author_id: string;
  author_role: string;
  visibility: string;
  body: string;
  created_at: string;
}

interface Props {
  ticketId: string;
  currentStatus: string;
  assigneeId: string | null;
  currentUserId: string;
  isAgent: boolean;
  initialMessages: TicketMessageOut[];
}

const NEXT_STATUSES: Record<string, { label: string; value: string; variant: string }[]> = {
  NEW:          [{ label: "Iniciar triagem", value: "TRIAGE", variant: "secondary" },
                 { label: "Assumir → Em andamento", value: "IN_PROGRESS", variant: "primary" },
                 { label: "Cancelar", value: "CANCELLED", variant: "destructive" }],
  TRIAGE:       [{ label: "Em andamento", value: "IN_PROGRESS", variant: "primary" },
                 { label: "Aguardando usuário", value: "WAITING_USER", variant: "secondary" },
                 { label: "Resolver", value: "RESOLVED", variant: "success" }],
  IN_PROGRESS:  [{ label: "Aguardando usuário", value: "WAITING_USER", variant: "secondary" },
                 { label: "Resolver", value: "RESOLVED", variant: "success" },
                 { label: "Cancelar", value: "CANCELLED", variant: "destructive" }],
  WAITING_USER: [{ label: "Retomar", value: "IN_PROGRESS", variant: "primary" },
                 { label: "Resolver", value: "RESOLVED", variant: "success" },
                 { label: "Fechar", value: "CLOSED", variant: "secondary" }],
  RESOLVED:     [{ label: "Fechar", value: "CLOSED", variant: "secondary" },
                 { label: "Reabrir", value: "REOPENED", variant: "destructive" }],
  CLOSED:       [{ label: "Reabrir", value: "REOPENED", variant: "destructive" }],
  REOPENED:     [{ label: "Em andamento", value: "IN_PROGRESS", variant: "primary" },
                 { label: "Resolver", value: "RESOLVED", variant: "success" }],
  CANCELLED:    [{ label: "Reabrir", value: "REOPENED", variant: "destructive" }],
};

const VARIANT_CLASS: Record<string, string> = {
  primary:     "bg-primary text-primary-foreground hover:bg-primary/90",
  secondary:   "bg-secondary text-secondary-foreground hover:bg-secondary/80",
  success:     "bg-green-600 text-white hover:bg-green-700",
  destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
};

const AUTHOR_LABEL: Record<string, string> = {
  agent: "TI", requester: "Usuário", system: "Sistema", ai: "IA",
};

function getCsrf(): string {
  return (
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("csrf_token="))
      ?.split("=")[1] ?? ""
  );
}

export function TicketActions({
  ticketId,
  currentStatus,
  assigneeId,
  currentUserId,
  isAgent,
  initialMessages,
}: Props) {
  const [status, setStatus] = useState(currentStatus);
  const [assignee, setAssignee] = useState(assigneeId);
  const [messages, setMessages] = useState<TicketMessageOut[]>(initialMessages);
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"public" | "internal">("public");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMine = assignee === currentUserId;
  const nextStatuses = NEXT_STATUSES[status] ?? [];
  const terminal = ["CLOSED", "CANCELLED"].includes(status);

  async function ensureCsrf() {
    await fetchCsrfToken();
  }

  async function handleStatusChange(newStatus: string) {
    setLoading(true);
    setError(null);
    try {
      await ensureCsrf();
      const csrf = getCsrf();
      await api.patch(`/api/v1/tickets/${ticketId}/status`, { status: newStatus }, {
        headers: { "X-CSRF-Token": csrf },
      });
      setStatus(newStatus);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao alterar status");
    } finally {
      setLoading(false);
    }
  }

  async function handleAssign() {
    setLoading(true);
    setError(null);
    try {
      await ensureCsrf();
      const csrf = getCsrf();
      const newAssignee = isMine ? null : currentUserId;
      await api.patch(`/api/v1/tickets/${ticketId}/assign`, { assignee_id: newAssignee }, {
        headers: { "X-CSRF-Token": csrf },
      });
      setAssignee(newAssignee);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao atribuir chamado");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendMessage() {
    if (!body.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await ensureCsrf();
      const csrf = getCsrf();
      const msg = await api.post<TicketMessageOut>(
        `/api/v1/tickets/${ticketId}/messages`,
        { body: body.trim(), visibility },
        { headers: { "X-CSRF-Token": csrf } },
      );
      setMessages((prev) => [...prev, msg]);
      setBody("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao enviar mensagem");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {/* IT controls */}
      {isAgent && (
        <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Ações do chamado
          </p>

          {/* Assign */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">
              {assignee
                ? isMine
                  ? "Atribuído a mim"
                  : `Atribuído: ${assignee.slice(0, 8)}…`
                : "Sem responsável"}
            </span>
            {!terminal && (
              <button
                onClick={() => void handleAssign()}
                disabled={loading}
                className="text-xs px-3 py-1.5 rounded-md border hover:bg-muted transition-colors disabled:opacity-50"
              >
                {isMine ? "Liberar" : "Assumir"}
              </button>
            )}
          </div>

          {/* Status transitions */}
          {nextStatuses.length > 0 && !terminal && (
            <div className="flex flex-wrap gap-2">
              {nextStatuses.map((s) => (
                <button
                  key={s.value}
                  onClick={() => void handleStatusChange(s.value)}
                  disabled={loading}
                  className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors disabled:opacity-50 ${VARIANT_CLASS[s.variant] ?? ""}`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          )}

          {terminal && (
            <p className="text-xs text-muted-foreground">
              Chamado encerrado. {nextStatuses.length > 0 && (
                <button
                  onClick={() => void handleStatusChange(nextStatuses[0].value)}
                  disabled={loading}
                  className="underline hover:no-underline"
                >
                  {nextStatuses[0].label}
                </button>
              )}
            </p>
          )}
        </div>
      )}

      {/* Messages thread */}
      <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-5 py-4 border-b">
          Mensagens
        </p>

        <div className="divide-y">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">Sem mensagens ainda.</p>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`px-5 py-4 ${msg.visibility === "internal" ? "bg-yellow-50 dark:bg-yellow-900/10" : ""}`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-medium">
                  {AUTHOR_LABEL[msg.author_role] ?? msg.author_role}
                </span>
                {msg.visibility === "internal" && (
                  <span className="text-xs bg-yellow-200 text-yellow-800 px-1.5 py-0.5 rounded dark:bg-yellow-800/40 dark:text-yellow-300">
                    interno
                  </span>
                )}
                <span className="text-xs text-muted-foreground ml-auto">
                  {new Date(msg.created_at).toLocaleString("pt-BR")}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{msg.body}</p>
            </div>
          ))}
        </div>

        {/* Reply form */}
        {!terminal && (
          <div className="border-t p-4 space-y-2">
            {isAgent && (
              <div className="flex gap-3 text-xs">
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="vis"
                    value="public"
                    checked={visibility === "public"}
                    onChange={() => setVisibility("public")}
                    className="accent-primary"
                  />
                  Resposta pública
                </label>
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="vis"
                    value="internal"
                    checked={visibility === "internal"}
                    onChange={() => setVisibility("internal")}
                    className="accent-primary"
                  />
                  Nota interna
                </label>
              </div>
            )}
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey) {
                  e.preventDefault();
                  void handleSendMessage();
                }
              }}
              placeholder={
                isAgent
                  ? visibility === "internal"
                    ? "Nota interna (não visível ao usuário)…"
                    : "Resposta ao usuário…"
                  : "Adicione uma atualização ao chamado…"
              }
              rows={3}
              className="w-full resize-none rounded-md border bg-background px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <div className="flex justify-end">
              <button
                onClick={() => void handleSendMessage()}
                disabled={loading || !body.trim()}
                className="text-sm px-4 py-2 rounded-md bg-primary text-primary-foreground
                           hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Enviando…" : "Enviar"}
              </button>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 text-destructive text-sm px-4 py-2">
          {error}
        </div>
      )}
    </div>
  );
}
