# ADR-0005 — LLM Orchestrator Design

**Data:** 2026-06-09
**Status:** Aceito
**Contexto:** Sprint 1 — primeira conversa de helpdesk funcional end-to-end

---

## Contexto

O sistema precisa chamar modelos de linguagem para triagem de chamados.
Decisões de design afetam segurança, auditoria, LGPD e custo operacional.

## Alternativas consideradas

| Alternativa | Avaliação |
|-------------|-----------|
| SDK direto (openai.chat.completions) em cada endpoint | ❌ Sem auditoria centralizada; prompt não versionado; PII pode vazar |
| LangChain / LlamaIndex | ❌ Abstração excessiva para o escopo; dificulta auditoria; dependências pesadas |
| **Orquestrador próprio (escolhido)** | ✅ Pipeline explícito e auditável; prompts versionados no DB |

## Decisão

Toda chamada LLM passa por `LLMOrchestrator.complete()`. Nenhum endpoint
chama OpenAI/Anthropic diretamente.

### Pipeline

```
user_input
    │
    ▼
guardrails.check()          ← 12 padrões regex (NFKC normalized)
    │ flags: list[str]
    ▼
redactor.redact()           ← CPF/CNPJ (DV), email, phone BR, CEP, IPv4/v6, Luhn
    │ (clean_input, pii_map)
    ▼
token_map.store()           ← Redis Fernet-encrypted, TTL 24 h
    │
    ▼
fetch_prompt()              ← DB helpdesk.prompts WHERE published=true, cache 60 s
    │
    ▼
OpenAI beta.parse()         ← structured output → TriageOutput (Pydantic validated)
    │ on 5xx + fallback=true → Anthropic tool_use
    ▼
token_map.restore()         ← restaura tokens na resposta do assistente
    │
    ▼
ai_call_log INSERT          ← auditoria: tokens, latência, flags, provider, sha256
    │
    ▼
TriageOutput
```

### Prompts versionados no DB

- Tabela `helpdesk.prompts` com `(prompt_key, version)` unique e índice parcial
  `WHERE published=true` (exatamente 1 versão publicada por key).
- Mudar um prompt = nova versão. A versão anterior permanece (imutável).
- Toda chamada grava `prompt_sha256` em `ai_call_log` — rastreabilidade completa.

### Fernet key derivation

`SECRET_KEY` (urlsafe_b64 de ≥32 bytes) → `base64.urlsafe_b64decode(secret_key)[:32]`
→ `base64.urlsafe_b64encode(raw_32)` → `Fernet(key)`.

Rotação de `SECRET_KEY` invalida todos os `pii_map` em Redis (TTL 24 h).
Consequência aceita: mensagens em andamento perdem a capacidade de restaurar
tokens no display (Sprint 2 poderá usar HKDF + key-id se rotação frequente for necessária).

### SSE — Sprint 1 simplification

Sprint 1 usa chamada OpenAI síncrona (structured output) + chunking por palavra
(25 ms delay) como resposta SSE. Efeito visual: texto aparece progressivamente.
Sprint 2 pode migrar para streaming real com `stream=True` + parsing incremental de JSON.

### Fallback Anthropic

Ativado por `AI_FALLBACK_ENABLED=true` (default false). Acionado apenas em HTTP 5xx
da OpenAI. Erros 4xx (bad request) não fazem fallback — o payload é inválido.
Modelo fallback: `claude-haiku-4-5-20251001` (via tool_use forçado — Anthropic
não tem structured_output nativo no mesmo formato do OpenAI).

## Consequências

- Toda chamada LLM é auditável via `ai_call_log`.
- PII nunca chega ao LLM em claro (redactor + token_map).
- Prompts podem ser atualizados em runtime sem redeploy (DB-driven).
- Rotação de chave Fernet invalida pii_maps ativos (TTL 24 h mitiga).
- CSRF e rate limit (Redis sliding window Lua) protegem os endpoints de chat.
