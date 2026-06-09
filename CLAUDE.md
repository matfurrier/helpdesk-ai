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
| Next.js      | 16 (App Router, Server Components)      |
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
OPENAI_MODEL=gpt-5-mini
OPENAI_EMBED_MODEL=text-embedding-3-small
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
AI_FALLBACK_ENABLED=true
SECURITY_SCHEMA=security
HELPDESK_SCHEMA=helpdesk
RAG_SCHEMA=helpdesk_rag
SESSION_COOKIE_NAME=__Host-sds_session
CSRF_SECRET=...
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
LOG_LEVEL=INFO
ENV=development
```

## 7. Sprint 0 — entregáveis mínimos

1. `docker-compose.yml` dev com Postgres + Redis + MinIO + ClamAV + backend + frontend.
2. Backend respondendo `GET /api/v1/health` em `:8004`.
3. Frontend rodando em `:3004` com tela de login funcional contra `security` schema.
4. Migração inicial criando schemas `helpdesk` e `helpdesk_rag` a partir de `docs/DATABASE_SCHEMA.sql`.
5. CI: lint + typecheck + testes unitários básicos + suite de prompt injection.
6. README com instruções `docker compose up` → login → tela vazia.

## 8. Subagents recomendados (Claude Code)

- `@database-architect` — revisar migrations e índices.
- `@security-auditor` — revisar qualquer mudança em `services/ai/`, `services/auth/`, sanitização, RBAC.
- `@code-reviewer` — PRs gerais.
- `@devops-engineer` — `docker-compose`, CI/CD, deploy Hetzner.

Modelo padrão: **opusplan** (Opus planeja, Sonnet executa).

## 9. MCP servers úteis nesta sessão

- `postgres` apontando para o `infra_postgres` (leitura do schema `security` para entender modelo de usuários).
- `github` para abrir PRs.
- `sequential-thinking` para o orquestrador de IA.
- `playwright` para os testes E2E.

## 10. Padrões inspirados em apps irmãs (referência local)

- `~/apps-staging/boardadvisor` — layout chat-first, sidebar com conversas, header limpo.
- `~/apps-staging/flowsds` — fluxo multi-stage, status visual, transições controladas server-side.

**Não copiar nomes próprios nem strings hard-coded** dessas apps.
