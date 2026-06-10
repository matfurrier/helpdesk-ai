"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { fetchCsrfToken } from "@/lib/sse";

interface TicketMessageOut {
  id: string; author_id: string; author_role: string; visibility: string; body: string; created_at: string;
}
interface AttachmentOut {
  id: string; original_name: string; mime_type: string; size_bytes: number;
  scanned_status: string; created_at: string;
}
interface Category {
  id: string; slug: string; name: string;
}
interface AgentOut { id: string; name: string; }

interface Props {
  ticketId: string; currentStatus: string; assigneeId: string | null;
  categorySlug: string | null; categories: Category[];
  currentUserId: string; isAgent: boolean; initialMessages: TicketMessageOut[];
  csatRating: number | null;
  csatRespondedAt: string | null;
}

const NEXT_STATUSES: Record<string, { label: string; value: string; cls: string }[]> = {
  NEW:          [{ label: "Assumir", value: "IN_PROGRESS", cls: "bg-blue-600 hover:bg-blue-500 text-white" },
                 { label: "Triagem", value: "TRIAGE", cls: "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" },
                 { label: "Cancelar", value: "CANCELLED", cls: "bg-red-900/60 hover:bg-red-800/60 text-red-400" }],
  TRIAGE:       [{ label: "Em andamento", value: "IN_PROGRESS", cls: "bg-blue-600 hover:bg-blue-500 text-white" },
                 { label: "Aguardar usuário", value: "WAITING_USER", cls: "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" },
                 { label: "Resolver", value: "RESOLVED", cls: "bg-green-700 hover:bg-green-600 text-white" }],
  IN_PROGRESS:  [{ label: "Aguardar usuário", value: "WAITING_USER", cls: "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" },
                 { label: "Resolver", value: "RESOLVED", cls: "bg-green-700 hover:bg-green-600 text-white" },
                 { label: "Cancelar", value: "CANCELLED", cls: "bg-red-900/60 hover:bg-red-800/60 text-red-400" }],
  WAITING_USER: [{ label: "Retomar", value: "IN_PROGRESS", cls: "bg-blue-600 hover:bg-blue-500 text-white" },
                 { label: "Resolver", value: "RESOLVED", cls: "bg-green-700 hover:bg-green-600 text-white" },
                 { label: "Fechar", value: "CLOSED", cls: "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" }],
  RESOLVED:     [{ label: "Fechar", value: "CLOSED", cls: "bg-zinc-700 hover:bg-zinc-600 text-zinc-200" },
                 { label: "Reabrir", value: "REOPENED", cls: "bg-orange-900/60 hover:bg-orange-800/60 text-orange-400" }],
  CLOSED:       [{ label: "Reabrir", value: "REOPENED", cls: "bg-orange-900/60 hover:bg-orange-800/60 text-orange-400" }],
  REOPENED:     [{ label: "Em andamento", value: "IN_PROGRESS", cls: "bg-blue-600 hover:bg-blue-500 text-white" },
                 { label: "Resolver", value: "RESOLVED", cls: "bg-green-700 hover:bg-green-600 text-white" }],
  CANCELLED:    [{ label: "Reabrir", value: "REOPENED", cls: "bg-orange-900/60 hover:bg-orange-800/60 text-orange-400" }],
};

const TZ = "America/Sao_Paulo";
function fmtTime(s: string) {
  return new Date(s).toLocaleString("pt-BR", { timeZone: TZ, hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
}
function fmtSize(bytes: number) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
function mimeIcon(mime: string) {
  if (mime.startsWith("image/")) return "🖼";
  if (mime === "application/pdf") return "📄";
  if (mime.includes("spreadsheet") || mime.includes("excel")) return "📊";
  if (mime.includes("word") || mime.includes("document")) return "📝";
  return "📎";
}

function getCsrf() {
  return document.cookie.split("; ").find((c) => c.startsWith("csrf_token="))?.split("=")[1] ?? "";
}

export function TicketActions({
  ticketId, currentStatus, assigneeId, categorySlug, categories,
  currentUserId, isAgent, initialMessages,
  csatRating, csatRespondedAt,
}: Props) {
  const [status, setStatus] = useState(currentStatus);
  const [assignee, setAssignee] = useState(assigneeId);
  const [catSlug, setCatSlug] = useState(categorySlug);
  const [messages, setMessages] = useState<TicketMessageOut[]>(initialMessages);
  const [attachments, setAttachments] = useState<AttachmentOut[]>([]);
  const [agents, setAgents] = useState<AgentOut[]>([]);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"public" | "internal">("public");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void loadAttachments(); }, []);

  useEffect(() => { if (isAgent) void loadAgents(); }, [isAgent]);

  async function loadAgents() {
    try {
      const res = await fetch("/api/v1/tickets/agents");
      if (res.ok) setAgents(await res.json() as AgentOut[]);
    } catch { /* silent */ }
  }

  async function loadAttachments() {
    try {
      const res = await fetch(`/api/v1/tickets/${ticketId}/attachments`);
      if (res.ok) setAttachments(await res.json() as AttachmentOut[]);
    } catch { /* silent */ }
  }

  const csatLocked = status === "CLOSED" && csatRespondedAt !== null;
  const nextStatuses = csatLocked ? [] : (NEXT_STATUSES[status] ?? []);
  const terminal = ["CLOSED", "CANCELLED"].includes(status);
  const canSend = !terminal && (body.trim().length > 0 || pendingFiles.length > 0);

  async function withCsrf(fn: (csrf: string) => Promise<void>) {
    setLoading(true); setError(null);
    try { await fetchCsrfToken(); await fn(getCsrf()); }
    catch (e) { setError(e instanceof Error ? e.message : "Erro"); }
    finally { setLoading(false); }
  }

  function handleStatusChange(newStatus: string) {
    void withCsrf(async (csrf) => {
      await api.patch(`/api/v1/tickets/${ticketId}/status`, { status: newStatus }, { headers: { "X-CSRF-Token": csrf } });
      setStatus(newStatus);
    });
  }

  function handleAssignTo(userId: string | null) {
    void withCsrf(async (csrf) => {
      await api.patch(`/api/v1/tickets/${ticketId}/assign`, { assignee_id: userId }, { headers: { "X-CSRF-Token": csrf } });
      setAssignee(userId);
    });
  }

  function handleCategoryChange(slug: string) {
    void withCsrf(async (csrf) => {
      await api.patch(
        `/api/v1/tickets/${ticketId}/category`,
        { category_slug: slug || null },
        { headers: { "X-CSRF-Token": csrf } },
      );
      setCatSlug(slug || null);
    });
  }

  async function handleSend() {
    if (!canSend) return;
    await fetchCsrfToken();
    const csrf = getCsrf();
    setLoading(true); setError(null);
    try {
      // Send text message if body exists
      if (body.trim()) {
        const msg = await api.post<TicketMessageOut>(
          `/api/v1/tickets/${ticketId}/messages`,
          { body: body.trim(), visibility },
          { headers: { "X-CSRF-Token": csrf } },
        );
        setMessages((prev) => [...prev, msg]);
        setBody("");
      }
      // Upload pending files
      if (pendingFiles.length > 0) {
        setUploading(true);
        const uploaded: AttachmentOut[] = [];
        for (const file of pendingFiles) {
          const fd = new FormData();
          fd.append("file", file);
          const res = await fetch(`/api/v1/tickets/${ticketId}/attachments`, {
            method: "POST",
            headers: { "X-CSRF-Token": csrf },
            body: fd,
          });
          if (res.ok) {
            uploaded.push(await res.json() as AttachmentOut);
          } else {
            const err = await res.json() as { detail?: string };
            setError(err.detail ?? `Erro ao enviar ${file.name}`);
          }
        }
        if (uploaded.length > 0) setAttachments((prev) => [...prev, ...uploaded]);
        setPendingFiles([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao enviar");
    } finally {
      setLoading(false); setUploading(false);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files) return;
    setPendingFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
    e.target.value = "";
  }

  function removeFile(idx: number) {
    setPendingFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  return (
    <div className="space-y-3">
      {/* IT controls */}
      {isAgent && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 space-y-3">
          {csatLocked ? (
            <div className="flex items-center gap-2 text-[11px] text-amber-400 bg-amber-900/20 border border-amber-800/30 rounded-md px-3 py-2">
              <span>{"★".repeat(Math.round(csatRating ?? 0))}{"☆".repeat(5 - Math.round(csatRating ?? 0))}</span>
              <span>
                Avaliação: <strong>{(csatRating ?? 0).toFixed(1)}/5</strong> — chamado encerrado definitivamente
              </span>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 flex-wrap">
                  {nextStatuses.map((s) => (
                    <button key={s.value} onClick={() => handleStatusChange(s.value)} disabled={loading}
                      className={`text-xs px-3 py-1.5 rounded-md font-medium transition-colors disabled:opacity-40 ${s.cls}`}>
                      {s.label}
                    </button>
                  ))}
                </div>
                {!terminal && (
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-zinc-500">Responsável:</span>
                    <select
                      value={assignee ?? ""}
                      onChange={(e) => handleAssignTo(e.target.value || null)}
                      disabled={loading}
                      className="bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500/50 disabled:opacity-40"
                    >
                      <option value="">Sem responsável</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.id === currentUserId ? `${a.name} (eu)` : a.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              {categories.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-zinc-500">Categoria:</span>
                  <select
                    value={catSlug ?? ""}
                    onChange={(e) => handleCategoryChange(e.target.value)}
                    disabled={loading}
                    className="bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500/50 disabled:opacity-40"
                  >
                    <option value="">Sem categoria</option>
                    {categories.map((c) => (
                      <option key={c.slug} value={c.slug}>{c.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Message thread */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
        {messages.length === 0 ? (
          <div className="px-4 py-8 text-center text-xs text-zinc-600">Sem mensagens ainda.</div>
        ) : (
          <div className="px-4 py-4 space-y-3 max-h-[500px] overflow-y-auto">
            {messages.map((msg) => {
              const isRequester = msg.author_role === "requester";
              const isInternal = msg.visibility === "internal";
              return (
                <div key={msg.id} className={`flex flex-col ${isRequester ? "items-end" : "items-start"}`}>
                  <div className={`max-w-[85%] ${
                    isInternal
                      ? "bg-yellow-900/20 border border-yellow-800/30 rounded-lg"
                      : isRequester
                        ? "bg-blue-600/20 rounded-lg rounded-tr-sm"
                        : "bg-zinc-800 rounded-lg rounded-tl-sm"
                  } px-3 py-2`}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[11px] font-medium text-zinc-400">
                        {msg.author_role === "agent" ? "TI" : msg.author_role === "requester" ? "Usuário" : msg.author_role === "ai" ? "IA" : "Sistema"}
                      </span>
                      {isInternal && (
                        <span className="text-[10px] bg-yellow-800/40 text-yellow-400 px-1.5 py-0.5 rounded">interno</span>
                      )}
                      <span className="text-[11px] text-zinc-600 ml-auto">{fmtTime(msg.created_at)}</span>
                    </div>
                    <p className="text-xs text-zinc-200 whitespace-pre-wrap leading-relaxed">{msg.body}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Attachments list */}
        {attachments.length > 0 && (
          <div className="border-t border-zinc-800 px-4 py-3">
            <p className="text-[11px] font-medium text-zinc-500 uppercase tracking-wide mb-2">
              Anexos ({attachments.length})
            </p>
            <div className="flex flex-wrap gap-2">
              {attachments.map((att) => (
                <a
                  key={att.id}
                  href={`/api/v1/tickets/${ticketId}/attachments/${att.id}/download`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-[11px] bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-zinc-100 px-2.5 py-1.5 rounded-md transition-colors border border-zinc-700/50"
                >
                  <span>{mimeIcon(att.mime_type)}</span>
                  <span className="max-w-[180px] truncate">{att.original_name}</span>
                  <span className="text-zinc-600 shrink-0">{fmtSize(att.size_bytes)}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Reply form */}
        {!terminal && (
          <div className="border-t border-zinc-800 p-3 space-y-2">
            {isAgent && (
              <div className="flex gap-4 text-[11px]">
                {(["public", "internal"] as const).map((v) => (
                  <label key={v} className="flex items-center gap-1.5 cursor-pointer">
                    <input type="radio" name="vis" value={v} checked={visibility === v}
                      onChange={() => setVisibility(v)} className="accent-blue-500 w-3 h-3" />
                    <span className={visibility === v ? "text-zinc-200" : "text-zinc-500"}>
                      {v === "public" ? "Resposta pública" : "Nota interna"}
                    </span>
                  </label>
                ))}
              </div>
            )}

            {/* Pending files chips */}
            {pendingFiles.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {pendingFiles.map((f, i) => (
                  <span key={i} className="flex items-center gap-1 text-[11px] bg-zinc-800 border border-zinc-700 text-zinc-300 px-2 py-0.5 rounded-md">
                    <span>{mimeIcon(f.type)}</span>
                    <span className="max-w-[140px] truncate">{f.name}</span>
                    <span className="text-zinc-600">{fmtSize(f.size)}</span>
                    <button
                      onClick={() => removeFile(i)}
                      className="ml-0.5 text-zinc-500 hover:text-red-400 transition-colors leading-none"
                      aria-label="Remover arquivo"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div className="flex gap-2 items-end">
              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                multiple
                accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.jpg,.jpeg,.png,.gif,.webp"
                onChange={handleFileSelect}
              />

              {/* Paperclip button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={loading}
                title="Anexar arquivo (máx. 10 MB)"
                className="flex-shrink-0 p-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded-md transition-colors disabled:opacity-40"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                  <path fillRule="evenodd" d="M15.621 4.379a3 3 0 00-4.242 0l-7 7a1.5 1.5 0 002.122 2.121l7-7a.75.75 0 011.06 1.061l-7 7a3 3 0 11-4.242-4.243l7-7a4.5 4.5 0 016.364 6.364l-7 7a6 6 0 11-8.486-8.486l7-7a.75.75 0 011.06 1.061z" clipRule="evenodd" />
                </svg>
              </button>

              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void handleSend(); } }}
                placeholder={isAgent && visibility === "internal" ? "Nota interna (não visível ao usuário)…" : "Escreva uma mensagem…"}
                rows={2}
                className="flex-1 resize-none bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
              />
              <button
                onClick={() => void handleSend()}
                disabled={loading || !canSend}
                className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed h-[calc(2*1.25rem+1rem)] whitespace-nowrap"
              >
                {uploading ? "Enviando…" : loading ? "…" : "Enviar"}
              </button>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-400 bg-red-900/20 border border-red-800/30 rounded-md px-3 py-2">{error}</div>
      )}
    </div>
  );
}
