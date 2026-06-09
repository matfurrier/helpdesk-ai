"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { fetchCsrfToken, sendMessage, type TriageResult } from "@/lib/sse";

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

export default function NewChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [lastResult, setLastResult] = useState<TriageResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Create conversation on mount
  useEffect(() => {
    async function init() {
      try {
        await fetchCsrfToken();
        const csrf = document.cookie
          .split("; ")
          .find((c) => c.startsWith("csrf_token="))
          ?.split("=")[1];

        const conv = await api.post<ConversationOut>("/api/v1/chat/conversations", null, {
          headers: csrf ? { "X-CSRF-Token": csrf } : {},
        });
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

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: "user",
      content: userContent,
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const result = await sendMessage(
        conversationId,
        userContent,
        (delta) => setStreamingText((prev) => prev + delta),
      );

      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: result.assistant_text,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setLastResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar mensagem");
    } finally {
      setLoading(false);
      setStreamingText("");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  return (
    <main className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="border-b px-4 py-3 flex items-center gap-3">
        <a href="/dashboard" className="text-sm text-muted-foreground hover:underline">
          ← Dashboard
        </a>
        <h1 className="text-base font-semibold">Suporte de TI</h1>
        {conversationId && (
          <span className="text-xs text-muted-foreground ml-auto">
            #{conversationId.slice(0, 8)}
          </span>
        )}
      </header>

      {/* Messages */}
      <section className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && !loading && (
          <p className="text-center text-sm text-muted-foreground mt-12">
            Descreva seu problema de TI e pressione Enter.
          </p>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* Streaming assistant text */}
        {streamingText && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2 text-sm bg-muted text-foreground whitespace-pre-wrap">
              {streamingText}
              <span className="animate-pulse">▍</span>
            </div>
          </div>
        )}

        {/* Open ticket button */}
        {lastResult?.next_action === "offer_open_ticket" && (
          <div className="flex justify-center pt-2">
            <button
              disabled
              className="text-sm px-4 py-2 rounded-md border border-dashed text-muted-foreground cursor-not-allowed"
              title="Disponível no Sprint 2"
            >
              Abrir chamado (Sprint 2)
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="rounded-md bg-destructive/10 text-destructive text-sm px-4 py-2">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </section>

      {/* Input */}
      <footer className="border-t px-4 py-3">
        <div className="flex gap-2 items-end">
          <textarea
            className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-ring min-h-[2.5rem] max-h-40"
            placeholder={conversationId ? "Digite sua mensagem..." : "Carregando..."}
            value={input}
            disabled={!conversationId || loading}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button
            onClick={() => void handleSend()}
            disabled={!conversationId || loading || !input.trim()}
            className="rounded-md bg-primary text-primary-foreground px-4 py-2 text-sm
                       hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "..." : "Enviar"}
          </button>
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Enter para enviar · Shift+Enter para nova linha
        </p>
      </footer>
    </main>
  );
}
