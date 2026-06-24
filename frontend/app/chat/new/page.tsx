"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { sendMessage, type TriageResult } from "@/lib/sse";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ConversationOut {
  id: string;
  status: string;
  started_at: string;
  message_count: number;
}

interface ConvertOut {
  ticket_id: string;
  ticket_number: string;
  status: string;
}

export default function NewChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [converting, setConverting] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [lastResult, setLastResult] = useState<TriageResult | null>(null);
  const [ticket, setTicket] = useState<ConvertOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function init() {
      try {
        const conv = await api.post<ConversationOut>("/api/v1/chat/conversations", null);
        setConversationId(conv.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro ao iniciar conversa");
      }
    }
    void init();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  async function handleSend() {
    if (!input.trim() || !conversationId || loading) return;

    const userContent = input.trim();
    setInput("");
    setError(null);
    setLoading(true);
    setStreamingText("");

    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, role: "user", content: userContent },
    ]);

    try {
      const result = await sendMessage(
        conversationId,
        userContent,
        (delta) => setStreamingText((prev) => prev + delta),
      );
      setMessages((prev) => [
        ...prev,
        { id: `a-${Date.now()}`, role: "assistant", content: result.assistant_text },
      ]);
      setLastResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar mensagem");
    } finally {
      setLoading(false);
      setStreamingText("");
    }
  }

  async function handleConvert() {
    if (!conversationId || converting) return;
    setConverting(true);
    setError(null);
    try {
      const result = await api.post<ConvertOut>(
        `/api/v1/chat/conversations/${conversationId}/convert`,
        null,
      );
      setTicket(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro ao abrir chamado";
      setError(msg.includes("409") || msg.toLowerCase().includes("convertida")
        ? "Este chat já foi convertido em chamado."
        : msg);
    } finally {
      setConverting(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  const showConvertButton =
    !ticket &&
    (lastResult?.next_action === "offer_open_ticket" ||
      lastResult?.next_action === "escalate_human");

  return (
    <main className="flex flex-col h-screen bg-zinc-950">
      <header className="border-b border-zinc-800 px-4 py-3 flex items-center gap-3 bg-zinc-950">
        <a href="/dashboard" className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors">
          ← Dashboard
        </a>
        <h1 className="text-base font-semibold text-zinc-100">Suporte de TI</h1>
        {conversationId && (
          <span className="text-xs text-zinc-600 ml-auto font-mono">
            #{conversationId.slice(0, 8)}
          </span>
        )}
      </header>

      <section className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-zinc-900">
        {messages.length === 0 && !loading && (
          <p className="text-center text-sm text-zinc-400 mt-12">
            Descreva seu problema de TI e pressione Enter.
          </p>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-zinc-800 text-zinc-200 border border-zinc-700/50"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2.5 text-sm bg-zinc-800 text-zinc-200 border border-zinc-700/50 whitespace-pre-wrap leading-relaxed">
              {streamingText}
              <span className="animate-pulse text-zinc-400">▍</span>
            </div>
          </div>
        )}

        {showConvertButton && (
          <div className="flex justify-center pt-2">
            <button
              onClick={() => void handleConvert()}
              disabled={converting}
              className="text-sm px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-500 text-white
                         transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {converting ? "Abrindo chamado…" : "Abrir chamado"}
            </button>
          </div>
        )}

        {ticket && (
          <div className="flex justify-center pt-2">
            <div className="rounded-lg border border-green-500/30 bg-green-500/10 px-5 py-3 text-sm text-center">
              <p className="font-medium text-green-400">
                Chamado criado: <strong>{ticket.ticket_number}</strong>
              </p>
              <a
                href={`/tickets/${ticket.ticket_id}`}
                className="text-xs text-zinc-400 hover:text-zinc-200 mt-1 block transition-colors"
              >
                Ver chamado →
              </a>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-md bg-red-900/20 border border-red-800/30 text-red-400 text-sm px-4 py-2">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </section>

      <footer className="border-t border-zinc-800 px-4 py-3 bg-zinc-950">
        <div className="flex gap-2 items-end">
          <textarea
            className="flex-1 resize-none rounded-md border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm
                       text-zinc-100 placeholder:text-zinc-500
                       focus:outline-none focus:ring-1 focus:ring-blue-500/50 min-h-[2.5rem] max-h-40"
            placeholder={conversationId ? "Digite sua mensagem..." : "Carregando..."}
            value={input}
            disabled={!conversationId || loading || !!ticket}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            onClick={() => void handleSend()}
            disabled={!conversationId || loading || !input.trim() || !!ticket}
            className="rounded-md bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 text-sm
                       transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "..." : "Enviar"}
          </button>
        </div>
        <p className="text-xs text-zinc-600 mt-1">
          Enter para enviar · Shift+Enter para nova linha
        </p>
      </footer>
    </main>
  );
}
