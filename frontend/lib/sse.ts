/**
 * SSE streaming client for the chat triage endpoint.
 *
 * Uses fetch + ReadableStream (not EventSource) because:
 * - EventSource doesn't support POST or cookies on all browsers/proxies.
 * - We need to send the message body in the request.
 */

import { buildApiUrl } from "./api";

export interface SseDelta {
  delta?: string;
  done: false;
}

export interface SseFinal {
  done: true;
  result: TriageResult;
}

export type SseEvent = SseDelta | SseFinal;

export interface TriageResult {
  assistant_text: string;
  next_action:
    | "ask_more"
    | "suggest_kb"
    | "offer_open_ticket"
    | "auto_resolve"
    | "escalate_human";
  suggestions: SuggestionItem[];
  ticket_draft: TicketDraft | null;
  guardrails_triggered: string[];
}

export interface SuggestionItem {
  title: string;
  steps: string[];
  citations: string[];
}

export interface TicketDraft {
  title: string;
  summary: string;
  category_suggestion: string;
  priority_suggestion: "low" | "normal" | "high" | "urgent";
  tags: string[];
}

/**
 * Stream a triage message from the server.
 *
 * Yields SseDelta events as the assistant types, then one SseFinal event.
 * Caller should consume the generator and update UI state incrementally.
 */
export async function* streamChat(
  conversationId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<SseEvent, void, unknown> {
  const res = await fetch(
    buildApiUrl(`/api/v1/chat/conversations/${conversationId}/messages`),
    {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ content }),
      signal,
    },
  );

  if (res.status === 401) {
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new Error("Não autenticado");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Erro desconhecido");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("ReadableStream not supported");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (!raw) continue;
      yield JSON.parse(raw) as SseEvent;
    }
  }
}

/** One-shot helper: returns the final TriageResult (skips deltas). */
export async function sendMessage(
  conversationId: string,
  content: string,
  onDelta?: (delta: string) => void,
  signal?: AbortSignal,
): Promise<TriageResult> {
  for await (const event of streamChat(conversationId, content, signal)) {
    if (!event.done && onDelta && event.delta) {
      onDelta(event.delta);
    }
    if (event.done) {
      return event.result;
    }
  }
  throw new Error("SSE stream ended without final event");
}
