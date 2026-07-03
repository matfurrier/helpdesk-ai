# helpdesk-ai

Sistema interno de atendimento de TI com triagem por IA, base de conhecimento RAG e fluxo completo de chamados. Substitui o GLPI no ambiente de uma multinacional do agronegócio.

O colaborador **conversa com um assistente de IA** ao invés de preencher formulário. A IA tenta resolver via base de conhecimento; se não resolver, converte automaticamente em ticket categorizado e priorizado.

---

## Personas e papéis

| Papel | Acesso |
|---|---|
| `employee` | Chat com IA, acompanhar próprios tickets, anexar arquivos |
| `it_agent` | Fila completa, responder, reatribuir, fechar chamados |
| `it_lead` | Tudo do agente + gestão da base de conhecimento |
| `it_admin` | Configurações globais: categorias, SLA, modelos de IA, prompts, RAG sources |

Papéis derivados do banco `security` (diretório compartilhado), com `helpdesk.role_overrides` (banco `helpdesk`) para grants explícitos de `it_lead`/`it_admin`. O papel é reresolvido a cada request (não fica em cache no JWT), então um grant novo vale imediatamente, sem precisar de novo login.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 · FastAPI ≥ 0.115 · SQLAlchemy 2.x async · Alembic · Pydantic v2 |
| Frontend | Next.js 15 App Router · React 19 · TypeScript strict · ShadCN UI · Tailwind 4 |
| Estado client | TanStack Query · Zustand · react-hook-form + zod |
| Banco | PostgreSQL 16 + pgvector ≥ 0.7 (schemas `helpdesk`, `helpdesk_rag`) |
| Cache / filas | Redis 7 (arq workers) |
| Storage | MinIO — bucket `helpdesk-attachments` |
| Antivírus | ClamAV (sidecar, scan de todos os uploads; volume persistente no Swarm para as assinaturas; `CLAMAV_FAIL_OPEN` libera upload se o scanner ficar indisponível — manter `false` em produção normalmente) |
| LLM primário | OpenAI GPT-4o-mini (configurável via env) |
| LLM fallback | Anthropic Claude Haiku 4.5 |
| Embeddings | text-embedding-3-small (OpenAI) — 1536 dims |
| Observabilidade | structlog · OpenTelemetry (OTLP) · Sentry |
| Deploy | Docker Swarm (Hetzner CPX62, single-node) · Traefik |

---

## Arquitetura (visão de alto nível)

```
Browser (PWA)
  │ HTTPS via Traefik
  ▼
Frontend — Next.js :3004
  │ REST + SSE
  ▼
Backend — FastAPI :8004
  ├── API v1 (auth · tickets · chat · kb · attachments · admin · metrics)
  ├── AI Orchestrator (OpenAI primário → Anthropic fallback, guardrails, telemetria)
  ├── RAG Service (retrieval síncrono: embed → pgvector HNSW → rerank → top-3)
  └── Workers arq (ingest_rag · compute_sla · scan_attachment · notify · anonymize)
        │
  ┌─────┼─────────────────────────┐
  ▼     ▼                         ▼
Postgres 16     MinIO              Redis 7
helpdesk        helpdesk-          (arq queue)
helpdesk_rag    attachments
security (RO)
```

> Em produção (Swarm), `helpdesk`/`helpdesk_rag` rodam no cluster **`infra_postgres`** compartilhado (cutover em 2026-07-01), não mais num container `helpdesk-postgres` dedicado — credenciais via `INFRA_POSTGRES_*`. O banco `security` continua uma base física separada, só leitura. Em dev local o `docker-compose.yml` ainda sobe um Postgres próprio (porta 5436).

Detalhes completos: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Portas (dev local)

| Serviço | Porta host | Porta interna |
|---|---|---|
| Backend (FastAPI) | 8004 | 8004 |
| Frontend (Next.js) | 8081 | 3004 |
| Postgres (helpdesk) | 5436 | 5432 |
| Redis | 6380 | 6379 |
| MinIO API | 9100 | 9000 |
| MinIO Console | 9101 | 9101 |
| ClamAV | 3310 | 3310 |

---

## Quick start — desenvolvimento local

**Pré-requisitos:** Docker, pnpm, acesso de leitura ao banco `security` via rede overlay `data`.

```bash
# 1. Configurar variáveis
cp .env.example .env
# editar .env — preencher senhas, OPENAI_API_KEY, SECURITY_DB_*

# 2. Subir todos os containers
make dev

# 3. Aplicar migrations
make migrate

# 4. (primeira vez) instalar deps e componentes ShadCN do frontend
make frontend-bootstrap

# Abrir
open http://localhost:8081
```

Para ter papel `it_admin` durante o desenvolvimento (antes do Sprint 2):
```bash
# em .env
BOOTSTRAP_ADMIN_UUIDS=<seu-uuid-da-coluna-public.users.uuid>
```

---

## Comandos Makefile

```bash
make dev            # sobe tudo com hot-reload
make down           # para containers
make down-v         # para e remove volumes (destrutivo)

make migrate        # alembic upgrade head (via container dev)
make migrate-swarm  # alembic upgrade head (via container swarm em produção)

make test           # pytest tests/unit/
make test-int       # testes de integração (requer postgres rodando)
make test-pi        # suite de prompt injection (bloqueia merge se falhar)

make lint           # ruff check + ruff format --check
make ci-local       # reproduz o pipeline CI completo localmente

make deploy-swarm   # build + deploy no Docker Swarm (ver seção abaixo)
make psql           # abre shell psql no banco de dev
```

---

## Deploy — Docker Swarm

```bash
# Build das imagens prod e deploy no Swarm
make deploy-swarm
```

O Makefile já faz `set -a && source .env && set +a` antes do `docker stack deploy` — obrigatório porque o Swarm não carrega `.env` automaticamente.

Após qualquer rebuild de imagem local, o `--force` é aplicado automaticamente pelo `make deploy-swarm` para forçar o restart (Swarm não detecta mudanças em imagens sem registry digest).

**Verificar se o frontend está sendo servido pelo Swarm:**
```bash
curl -sI http://localhost:8081 | head -3
# Esperado: HTTP/1.1 307 → /login
```

**Importante:** os containers dev `helpdesk-frontend` e `helpdesk-backend` devem estar parados em produção (concorrem na porta 8081):
```bash
docker stop helpdesk-frontend helpdesk-backend
```

---

## Migrations

```bash
# Dev (via container docker compose)
make migrate

# Produção (via réplica Swarm em execução)
make migrate-swarm

# Produção (container efêmero, útil em CI/CD)
IMAGE=helpdesk-backend:prod DATABASE_URL=postgresql+asyncpg://... make migrate-prod
```

Migrations ficam em `backend/alembic/versions/`. Dois schemas: `helpdesk` e `helpdesk_rag` — ambos gerenciados pelo mesmo `env.py`.

---

## Testes e CI

| Suite | Cobertura mínima | Comando |
|---|---|---|
| Unit (backend) | 70% global, 90% em `services/ai/` e `core/security` | `make test` |
| Integration | — | `make test-int` |
| Prompt injection | ≥ 10 casos, falha bloqueia merge | `make test-pi` |
| Frontend (vitest) | 50% em utils e hooks críticos | `cd frontend && pnpm test` |

O workflow de CI (GitHub Actions) foi **removido** (`.github/workflows/ci.yml`, 2026-06-30) — hoje não há verificação automática em PR/push. Rodar `make ci-local` manualmente antes de mergear para reproduzir lint → typecheck → migration → unit → prompt injection.

---

## Fluxo principal — triagem via chat

```
1. Colaborador abre chat → cria ai_conversation
2. Envia mensagem → backend sanitiza PII, faz RAG (embed → top-8 → rerank → top-3)
3. LLM recebe: system prompt + contexto RAG + histórico + input do usuário
4. Responde com texto + action_cards (JSON validado por Pydantic)
5. Usuário avalia sugestão:
   - "resolveu" → AUTO_RESOLVED, conversa encerrada
   - "não resolveu" → IA tenta nova abordagem
6. POST /chat/{cid}/convert → gera ticket com título, resumo, categoria e prioridade
   sugeridos por IA; status = NEW; notificação para fila do TI
```

---

## Funcionalidades

### Gestão de usuários (`/admin/users-mgmt`)

- CRUD completo com papel **nativo** (`user`/`responsavel`, valores derivados do diretório `security`) exibido junto do papel efetivo do helpdesk.
- Seletor **`override_role`** no próprio diálogo — concede/revoga `it_lead`/`it_admin` direto no modal (chama a API existente `POST`/`DELETE /admin/roles/{uuid}`), sem precisar da página de papéis separada.
- Flags `supplier_docs_manager` e `auditor` expostas no CRUD.
- **Atribuições dinâmicas de app** — lista de `app_ids` por usuário, carregada de `/admin/applications` e sincronizada no create/patch (sem N+1 no list).
- Seção "Documentos e Contato": CPF, RG, matrícula e telefone/celular, persistidos em `helpdesk.user_profiles` (tabela de extensão que não toca o `security.users` compartilhado). *CRUD suporta esses campos — nenhum dado real deve aparecer em prints ou exemplos deste repositório.*

### Fila de tickets de TI

- Toggle **"Ocultar fechados"** (`exclude_closed`) na barra de filtros do dashboard, para tirar tickets `CLOSED`/`CANCELLED` da visão padrão da fila.

### Anexos

- **Auto-upload ao selecionar arquivo** — o upload dispara imediatamente na seleção (com spinner), sem fila de "pendentes" à parte; simplifica o estado do formulário de ticket.

### Notificações

- Outbox de e-mail corrigido: endereços vazios são filtrados antes do envio SMTP (evitava falha silenciosa quando `IT_TEAM_EMAIL` não estava configurado) e linhas `failed` com menos de 3 tentativas voltam a ser reprocessadas em vez de ficar travadas para sempre.

---

## Segurança (destaques)

- **Structured output obrigatório** — LLM nunca retorna texto livre, sempre JSON validado
- **Separação instrução/dado** — input do usuário e chunks RAG ficam entre tags XML dedicadas, nunca em posição de instrução
- **Sanitização de input** — normalização NFKC, remoção de control chars, escape de delimitadores, detecção heurística de injection (marca `guardrail_flags` sem bloquear)
- **Anexos** — presigned PUT direto ao MinIO (não passa pelo backend), ClamAV obrigatório, download só liberado após scan `CLEAN`
- **PII** — redactor antes de qualquer chamada ao LLM; logs sem dados pessoais em claro
- **Auditoria** — toda chamada LLM, todo acesso a anexo e toda mudança de status registrados em `helpdesk.audit_log` (append-only, particionado por mês)

Detalhes: [`docs/SECURITY.md`](docs/SECURITY.md)

---

## Documentação

| Documento | Conteúdo |
|---|---|
| [`docs/SPEC.md`](docs/SPEC.md) | Especificação funcional completa |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitetura, componentes, sequências, ADRs |
| [`docs/DATABASE_SCHEMA.sql`](docs/DATABASE_SCHEMA.sql) | DDL completo dos schemas |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Modelo de ameaças e defesas em profundidade |
| [`docs/RAG_KNOWLEDGE_BASE.md`](docs/RAG_KNOWLEDGE_BASE.md) | Pipeline de ingestão e retrieval |
| [`docs/PROMPTS.md`](docs/PROMPTS.md) | Prompts versionados e regras invioláveis |
| [`docs/adr/`](docs/adr/) | Architecture Decision Records |
| [`CLAUDE.md`](CLAUDE.md) | Convenções de código, OPSEC, testes |

---

## Variáveis de ambiente

Ver [`.env.example`](.env.example) para a lista completa com descrições. Variáveis obrigatórias:

```
DATABASE_URL, SECURITY_DB_*, REDIS_URL, MINIO_*, OPENAI_API_KEY, SECRET_KEY, SMTP_*
```

Nunca commitar `.env`. O arquivo `.env.example` não deve conter valores reais.
