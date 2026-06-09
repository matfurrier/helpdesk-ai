# ARCHITECTURE — helpdesk-ai

## 1. Visão de alto nível

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Browser (PWA)                              │
│        Next.js 16 + React 19 + ShadCN + TanStack Query + Zustand        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ HTTPS (Traefik)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Backend (FastAPI :8004)                        │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────────────────┐ │
│  │   API v1      │  │   Workers     │  │   AI Orchestrator            │ │
│  │ (REST + SSE)  │  │ (RQ / arq)    │  │ (OpenAI primary, Claude fb)  │ │
│  └───────┬───────┘  └───────┬───────┘  └───────────────┬──────────────┘ │
│          │                  │                          │                │
│  ┌───────┴──────────────────┴──────────────────────────┴──────────────┐ │
│  │              Services (tickets, rag, auth, attachments)            │ │
│  └───────┬─────────────────┬───────────────────────────┬──────────────┘ │
└──────────┼─────────────────┼───────────────────────────┼────────────────┘
           │                 │                           │
           ▼                 ▼                           ▼
   ┌──────────────┐   ┌────────────┐           ┌──────────────────┐
   │  Postgres    │   │   MinIO    │           │  External APIs   │
   │ schemas:     │   │ bucket:    │           │  - OpenAI        │
   │  security    │   │ helpdesk-  │           │  - Anthropic     │
   │  helpdesk    │   │ attachments│           │  - SMTP / Teams  │
   │  helpdesk_rag│   │            │           │                  │
   │  (pgvector)  │   │            │           │                  │
   └──────────────┘   └────────────┘           └──────────────────┘
```

Tudo roda no Docker Swarm da Hetzner (single-node CPX62, mesmo deploy das outras apps internas). Traefik faz roteamento via subdomínio interno (`helpdesk.<corporate-domain>`). Acesso interno via VPN/AD.

## 2. Componentes

### 2.1 Frontend (`frontend/`)

- **Next.js 16 App Router** (RSC para páginas de listagem, Client Components para chat/forms)
- **ShadCN UI** copiado do BoardAdvisor (mesmos tokens, mesma paleta, mesma fonte)
- **TanStack Query** para todas as chamadas ao backend (cache + revalidação)
- **Zustand** para estado de chat (mensagens, anexos pendentes, draft)
- **SSE** (Server-Sent Events) para streaming das respostas da IA — `EventSource` no client
- **react-hook-form + zod** para forms admin
- **Tabela**: TanStack Table para fila e gestão
- **Markdown**: `react-markdown` + `rehype-sanitize` (sanitização obrigatória, vide SECURITY)

### 2.2 Backend (`backend/`)

- **FastAPI** com routers versionados (`/api/v1`)
- **SQLAlchemy 2.x async** + **asyncpg**
- **Alembic** para migrations (por schema: `helpdesk` e `helpdesk_rag`)
- **Pydantic v2** para schemas
- **structlog** com correlation_id (request_id) propagado para LLM logs
- **OpenTelemetry** (OTLP) com traces para LLM calls (provider, modelo, tokens, latência)
- **arq** (Redis-backed) para workers — usa mesmo Redis dos outros projetos internos
- **Routers**: `auth`, `tickets`, `chat`, `kb`, `attachments`, `admin`, `metrics`, `health`

### 2.3 Workers

- `ingest_rag_source` — varre uma fonte (URL, repo, pasta MinIO), faz chunking, gera embeddings, popula `helpdesk_rag.chunks`
- `compute_sla` — periódico (5 min) recalcula deadlines e dispara notificações
- `scan_attachment` — ClamAV em anexo, atualiza status `clean | infected`
- `notify` — envia email/Teams a partir de outbox
- `anonymize_old_tickets` — job diário, anonimiza tickets fechados >5 anos
- `enrich_kb` — quando `it_lead` marca "transformar em artigo", gera rascunho via LLM

### 2.4 AI Orchestrator

Camada que abstrai providers. Interface:

```python
class LLMClient(Protocol):
    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[Tool] | None = None,
        response_format: ResponseFormat | None = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMChunk]: ...
```

Implementações: `OpenAIClient`, `AnthropicClient`. Roteamento via `AIRouter` com:
- Provider primário configurado em `helpdesk.ai_settings`
- Retry com exponential backoff (3x)
- Fallback automático para provider secundário em caso de erro de provider ou rate limit
- Telemetria por chamada (provider usado, custo estimado, tokens, latência, fallback_used)
- **Guardrails** aplicados antes e depois (vide SECURITY)

## 3. Modelo de dados (resumo)

Detalhe completo em `DATABASE_SCHEMA.sql`. Schemas:

### `helpdesk`
- `tickets`
- `ticket_messages` (thread)
- `ticket_attachments`
- `ticket_status_history`
- `ticket_assignments`
- `categories`
- `sla_matrix`
- `ai_conversations` (chats antes de virar ticket)
- `ai_conversation_messages`
- `ai_suggestions` (cards propostos)
- `ai_call_log` (cada chamada ao LLM, com tokens, custo, latência, guardrail_flags)
- `kb_articles`
- `kb_article_versions`
- `audit_log` (append-only, particionado por mês)
- `notification_outbox`
- `notification_preferences`
- `user_satisfaction` (NPS/CSAT)
- `ai_settings` (provider primário, modelo, temperatura)
- `prompts` (versionados)

### `helpdesk_rag`
- `sources` (origem da KB: URL, repo, pasta, etc.)
- `documents` (1 doc = 1 unidade ingerida)
- `chunks` (texto + `embedding vector(1536)` + metadata)
- `ingestion_runs` (histórico de execuções de ingestão)

### `security` (já existe)
- Reutilizar tabelas existentes; o backend acessa via **vista read-only** + adapter.

## 4. APIs (resumo dos endpoints principais)

```
# auth
POST   /api/v1/auth/login            (delega para schema security)
POST   /api/v1/auth/logout
GET    /api/v1/auth/me

# chat (triagem)
POST   /api/v1/chat                  → cria conversation
POST   /api/v1/chat/{cid}/messages   → envia mensagem (SSE para resposta)
POST   /api/v1/chat/{cid}/feedback   → "funcionou" / "não funcionou" em sugestão
POST   /api/v1/chat/{cid}/convert    → converte em ticket
POST   /api/v1/chat/{cid}/cancel

# tickets
GET    /api/v1/tickets/me            → meus chamados (employee)
GET    /api/v1/tickets               → fila (it_agent+)
GET    /api/v1/tickets/{id}
POST   /api/v1/tickets/{id}/messages
PATCH  /api/v1/tickets/{id}          → mudar status/prioridade/atribuição (it_agent+)
POST   /api/v1/tickets/{id}/assign
POST   /api/v1/tickets/{id}/resolve
POST   /api/v1/tickets/{id}/reopen
POST   /api/v1/tickets/{id}/satisfaction
POST   /api/v1/tickets/{id}/draft-reply   → rascunho gerado por IA (it_agent+)

# attachments
POST   /api/v1/attachments/upload-url     → presigned PUT
POST   /api/v1/attachments/{id}/confirm
GET    /api/v1/attachments/{id}/download  → presigned GET

# kb
GET    /api/v1/kb/articles
GET    /api/v1/kb/articles/{id}
POST   /api/v1/kb/articles                (it_lead+)
GET    /api/v1/kb/search?q=...            → vetorial + textual

# admin
GET/POST/PATCH/DELETE  /api/v1/admin/categories
GET/POST/PATCH         /api/v1/admin/sla
GET/POST/PATCH/DELETE  /api/v1/admin/rag-sources
POST                   /api/v1/admin/rag-sources/{id}/ingest    → dispara worker
GET/POST/PATCH         /api/v1/admin/prompts (versionados)
GET/PATCH              /api/v1/admin/ai-settings

# metrics
GET    /api/v1/metrics/dashboard
GET    /api/v1/metrics/rag-gaps

# health
GET    /api/v1/health
GET    /api/v1/health/ready
```

## 5. Sequência — abertura de chamado via chat

```
User → POST /chat                                  (cria conversation_id)
User → POST /chat/{cid}/messages (SSE)             "Não consigo conectar na VPN"
Backend:
  1. Persiste user_message
  2. Sanitiza + redata PII
  3. RAG: embed query → top-k=8 → rerank → top-3 chunks
  4. Monta prompt com:
     - System prompt (TRIAGE_SYSTEM)
     - Histórico da conversation (últimas N mensagens)
     - Contexto RAG (entre <context></context>)
     - User input (entre <user_input></user_input>)
  5. Chama LLM com guardrails (input + output)
  6. LLM responde com:
     - mensagem em texto natural
     - (opcional) action_cards estruturados (JSON via tool/structured output)
  7. Persiste assistant_message + suggestions
  8. Stream para o client
Client recebe stream → renderiza mensagem + action cards

User → POST /chat/{cid}/feedback { suggestion_id, outcome: "worked" }
Backend:
  - Se worked: convida a fechar conversa (AUTO_RESOLVED)
  - Se not_worked: marca, IA tenta outra abordagem ou pergunta detalhe
  - Se cant_execute: agenda follow-up humano automaticamente

User → POST /chat/{cid}/convert
Backend:
  - Gera ticket: title, summary, category sugerida, priority sugerida (LLM)
  - Persiste em tickets, copia transcript para ticket_messages (uma única "message" de tipo "transcript")
  - Status = NEW
  - Enfileira notificação para fila do TI
  - Retorna ticket_id
```

## 6. Autenticação e autorização

- **Login** via `public.users` no banco `security` (diretório compartilhado de colaboradores).
  Cada app emite seu próprio JWT — não há SSO entre apps.
- **Adapter** em `services/auth/` lê `public.users` (read-only) e deriva o papel:
  - `BOOTSTRAP_ADMIN_UUIDS` (env var provisória, Sprint 0) → `it_admin`
  - `departmentid == 1` (TI) → `it_agent`
  - demais → `employee`
  - Sprint 2: `helpdesk.role_overrides` permitirá distinguir `it_lead`/`it_admin` sem
    depender de alterações em tabelas externas. Ver ADR-0003.
- **RBAC** via `fastapi.Depends(require_role("it_agent"))`.
- **Auditoria**: cada request autenticada loga `user_id`, `role`, `endpoint`, `params`, `result` em `helpdesk.audit_log` (assíncrono via outbox).

## 7. Anexos — fluxo seguro

```
1. Client → POST /attachments/upload-url { filename, mime, size, ticket_id|conversation_id }
   - Backend valida extensão, mime, tamanho, autorização
   - Gera key UUID, retorna presigned PUT (expiração 5 min)
   - Cria registro em ticket_attachments com status=PENDING
2. Client → PUT MinIO (direto, sem passar pelo backend)
3. Client → POST /attachments/{id}/confirm
   - Backend verifica que o objeto existe no MinIO
   - Atualiza status=QUARANTINE
   - Enfileira worker scan_attachment
4. Worker scan_attachment:
   - Stream do MinIO → ClamAV
   - Se clean: status=CLEAN; remove EXIF se imagem; gera thumbnail (imagens)
   - Se infected: status=INFECTED; envia para bucket quarantine; notifica it_admin
5. Download:
   - Backend valida autorização (solicitante ou agente do ticket)
   - Só libera presigned GET se status=CLEAN
```

## 8. RAG — pipeline

Detalhado em `RAG_KNOWLEDGE_BASE.md`. Pontos arquiteturais:

- **Ingestão** roda em worker, idempotente, com hash de conteúdo (não re-embedda chunk inalterado)
- **Retrieval** é síncrono no path do chat (latência crítica)
- **pgvector HNSW** index em `helpdesk_rag.chunks.embedding`
- **Filtragem** por `source_type` e por permissões (alguns docs são só para TI)
- **Reranking** com cross-encoder leve (BAAI/bge-reranker-v2-m3 via API local) ou via LLM (cheap reranker prompt)
- **Citação obrigatória** — resposta precisa carregar `chunk_ids` usados; renderizados como notas no chat

## 9. Decisões iniciais (ADRs a documentar)

- **ADR-0001** — Stack base (FastAPI + Next.js 16 + Postgres + pgvector)
- **ADR-0002** — LLM provider primário OpenAI, fallback Anthropic
- **ADR-0003** — pgvector em vez de Qdrant/Pinecone (reuso do Postgres existente)
- **ADR-0004** — Schemas separados (`helpdesk`, `helpdesk_rag`) no mesmo cluster
- **ADR-0005** — Chat com SSE em vez de WebSocket (simplicidade, suficiente para o caso)
- **ADR-0006** — Anexos com presigned URL direto ao MinIO (não passa pelo backend)
- **ADR-0007** — Auth reusando schema `security` (sem duplicar identidade)
- **ADR-0008** — Defesa em profundidade contra prompt injection (vide SECURITY)

## 10. Performance / capacidade (estimativa)

- ~150 colaboradores ativos, ~20 tickets/dia, picos de 80
- Latência alvo:
  - REST (não-LLM): p95 < 300 ms
  - Chat (1º token): p95 < 1.5 s
  - Chat (resposta completa): p95 < 6 s
- RAG: < 200 ms para retrieval (top-k=8 + rerank de 3)
- Workers: paralelismo 4, retry 3x com backoff

## 11. Roadmap pós-MVP

- Auto-criação de artigos da KB a partir de tickets resolvidos (com revisão humana)
- Detecção de tickets duplicados (similaridade vetorial entre tickets recentes)
- Sugestão de categoria/prioridade refinada com fine-tune leve nos dados históricos
- Integração com SAP B1 (consulta de status de equipamento, OS de manutenção)
- Detecção de surtos (>N chamados sobre mesmo tema em janela curta) → alerta + criação automática de KB
