# === FABLE MODE BOOTSTRAP (paste at the TOP of every project CLAUDE.md) ===

## Session bootstrap — do this before anything else, in order

1. **Invoke the `fable-mode` skill now** and keep its discipline active for
   the whole session (autonomy, verified claims, TL;DR-first, stop
   conditions, delegation). Do not wait for it to trigger on its own.
2. Read `LEARNINGS.md` in this repo root (create it if absent).
3. Read `docs/adr/` index if present — decisions there are settled.
4. Only then start the task.

## Tools active in this repo

- **RTK**: compress context before long sessions and after large file reads.
  Prefer RTK-compressed summaries over re-reading big files.
- **Ponytail** (plugin, always-on): its decision ladder IS the enforcement of
  fable-mode §2 (Simplicity) — do not restate minimalism rules, follow the
  ladder. Never trade away validation, error handling, security, or
  accessibility to satisfy it. Run `/ponytail-review` on the diff before the
  final report, and treat any `ponytail:` deferred shortcuts as open items
  in the report (check `/ponytail-debt` at session end).

## Memory — two systems, different scope

- **`LEARNINGS.md`** (this file, project root): project-local lessons —
  environment quirks, failed approaches, config gotchas specific to this repo.
- **Auto-memory (`MEMORY.md`, global)**: cross-project facts, feedback, and
  preferences. Don't duplicate the same fact in both — put it where its
  scope matches.

## Precedence

This file > global ~/.claude/CLAUDE.md > fable-mode skill defaults.
On conflict, the most specific wins — except **hard rules** (secrets,
destructive ops, SAP access pattern, OPSEC), which always win.

# === END BOOTSTRAP — project-specific context below ===

# CLAUDE.md — convenções de desenvolvimento

> Este arquivo é lido automaticamente pelo Claude Code em toda sessão. Mantém estilo, OPSEC e padrões consistentes com as demais aplicações internas.

## 0. OPSEC — leia antes de qualquer commit ou doc público

- **NUNCA** mencionar o nome da empresa real em arquivos do repositório, comentários, mensagens de commit, READMEs públicos, screenshots ou material exposto externamente.
- Em material público use: `French agribusiness multinational` ou `internal IT helpdesk`.
- **NÃO** referenciar nomes de projetos internos irmãos (FlowSDS, NPD Flow, RNC Flow, BoardAdvisor, CargoLoad, sso-manager, AppDS) em material que possa vazar.
- Capturas de tela em portfólio: borrar nomes próprios, e-mails, RA de funcionário, CNPJ.
- Logs nunca devem conter PII em claro (ver `docs/SECURITY.md` — redactor).

## 1. Stack & versões alvo

| Camada       | Tecnologia                              |
|--------------|-----------------------------------------|
| Python       | 3.12                                    |
| FastAPI      | ≥ 0.115                                 |
| SQLAlchemy   | 2.x (estilo `select()`)                 |
| Pydantic     | v2                                      |
| Alembic      | última                                  |
| Node         | 22 LTS                                  |
| Next.js      | 15.x (App Router, Server Components)    |
| React        | 19                                      |
| TypeScript   | 5.x (strict)                            |
| Tailwind     | 4.x                                     |
| ShadCN UI    | última                                  |
| Postgres     | 16 + pgvector ≥ 0.7                     |
| Redis        | 7 (cache + filas RQ/arq)                |
| MinIO        | última (S3 API)                         |
| ClamAV       | scanner sidecar para anexos             |

## 2. Estilo de código

### Python
- `ruff` (lint + format) + `mypy --strict` em `app/services` e `app/core`.
- Imports absolutos a partir de `app.`.
- Funções com tipos explícitos. Modelos Pydantic v2 com `model_config = ConfigDict(strict=True)`.
- Erros de domínio: classes em `app/core/errors.py`. Nunca propagar `Exception` genérica para a API.
- Logs estruturados via `structlog` (JSON em produção).

### TypeScript / React
- `eslint` + `prettier`. Hooks com `react-hook-form` + `zod`.
- Componentes server-first; `"use client"` apenas onde necessário.
- Não usar `localStorage`/`sessionStorage` para dados sensíveis — sessão é cookie HttpOnly.
- ShadCN: copiar componentes via CLI, não wrappers desnecessários.

### Commits
- Conventional Commits: `feat(scope): ...`, `fix(scope): ...`, `chore: ...`.
- Mensagens em **inglês** (código também). Documentação Markdown em **pt-BR**.

## 3. Estrutura de pastas alvo

```
helpdesk-ai/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # routers FastAPI
│   │   ├── core/               # config, errors, security helpers
│   │   ├── db/                 # session, base, migrations bootstrap
│   │   ├── models/             # SQLAlchemy
│   │   ├── schemas/            # Pydantic
│   │   ├── services/           # regras de negócio
│   │   │   ├── ai/             # orchestrator, prompts, redactor
│   │   │   ├── rag/            # ingestion, retrieval
│   │   │   ├── tickets/
│   │   │   ├── attachments/
│   │   │   └── auth/
│   │   ├── workers/            # tarefas assíncronas
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── prompt_injection/   # suite obrigatória
│   │   └── conftest.py
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/                    # Next.js App Router
│   ├── components/
│   ├── lib/
│   ├── tests/                  # vitest + playwright
│   ├── package.json
│   └── Dockerfile
├── docs/                       # ESTE pacote
├── scripts/                    # one-off (seeds, migrations manuais)
├── docker-compose.yml          # dev local
├── docker-compose.swarm.yml    # deploy Hetzner
└── .github/workflows/
```

## 4. Testes & cobertura mínima

- **Backend**: pytest, cobertura global **≥ 70%**, e **≥ 90%** em `services/ai/`, `services/auth/`, `core/security.py`.
- **Frontend**: vitest **≥ 50%** em utils e hooks críticos.
- **E2E**: playwright com pelo menos 1 cenário golden (abrir chat, ser sugerido KB, recusar, virar ticket, analista responder).
- **Prompt injection**: suite separada em `tests/prompt_injection/` com **mínimo 10 casos** (ver `docs/PROMPTS.md`). Roda em CI a cada PR. Falha = bloqueia merge.

## 5. Padrão de chamada ao LLM

Toda chamada ao LLM passa pelo orquestrador único:

```python
from app.services.ai.orchestrator import LLMOrchestrator

result = await orchestrator.complete(
    prompt_key="TRIAGE_SYSTEM",          # versionado no banco
    user_input=sanitized_text,           # já passado pelo redactor
    context_blocks=rag_chunks,           # com trust_level
    schema=TriageOutput,                 # Pydantic, structured output
    user_id=current_user.id,
    conversation_id=conv.id,
)
```

Nunca chamar SDK do OpenAI/Anthropic direto fora de `services/ai/`. Toda chamada gera linha em `ai_call_log`.

## 6. Variáveis de ambiente

Ver `.env.example` (a ser criado no Sprint 0). Mínimo:

```
DATABASE_URL=postgresql+psycopg://...
REDIS_URL=redis://...
MINIO_ENDPOINT=...
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
MINIO_BUCKET=helpdesk-attachments
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini-2024-07-18
OPENAI_EMBED_MODEL=text-embedding-3-small
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
AI_FALLBACK_ENABLED=true
SECURITY_SCHEMA=security
HELPDESK_SCHEMA=helpdesk
RAG_SCHEMA=helpdesk_rag
CSRF_SECRET=...
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
LOG_LEVEL=INFO
ENV=development
```

## 7. Padrões inspirados em apps irmãs (referência local)

- `~/apps-staging/boardadvisor` — layout chat-first, sidebar com conversas, header limpo.
- `~/apps-staging/flowsds` — fluxo multi-stage, status visual, transições controladas server-side.

**Não copiar nomes próprios nem strings hard-coded** dessas apps.


<!-- appsds:dev-local -->
## Dev local (AppsDS)

Este app é desenvolvido em `/root/AppsDS/helpdesk-ai` — o código-fonte nunca volta pro servidor. Deploy: `scripts/deploy.sh helpdesk-ai` (rodado a partir da raiz de `/root/AppsDS`) builda a imagem aqui, sincroniza só config (compose/Dockerfile/.env) e manda a imagem pro `hetzner-app-01` via `docker save | ssh | docker load`.

**Bancos/cache**: o `.env` aponta pro DNS interno do Swarm (`tasks.infra_*`), que só resolve dentro do `hetzner-app-01`. Pra rodar local, use `.env.local` (git-ignorado, nunca sincronizado — já existe neste app):

- Postgres (infra_postgres): `hetzner-app-01:5433`

Detalhes/histórico: `/root/AppsDS/CLAUDE.md` e `/root/AppsDS/LEARNINGS.md`.
