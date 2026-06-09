# helpdesk-ai

> Sistema de atendimento interno (substituto do GLPI) com triagem por IA, base de conhecimento RAG e fluxo de chamados completo. Inspirado no padrão visual e arquitetural do **BoardAdvisor** e do **FlowSDS**.

## Visão de produto

O colaborador entra na aplicação e vê seu dashboard pessoal. Quando precisa de suporte, **não preenche um formulário** — ele inicia um **bate-papo com um assistente de IA**, que faz uma triagem conversacional curta, consulta a base de conhecimento (RAG) e sugere ações de autoatendimento.

- Se a sugestão **resolve** → o "chamado" é fechado como auto-resolvido (com registro para métricas e enriquecimento da base).
- Se a sugestão **não resolve** → o chat é convertido em **ticket oficial**, já categorizado, com resumo gerado pela IA, contexto da conversa e anexos preservados.

O atendimento (fila, triagem, encaminhamento, resolução) é restrito ao time de TI.

## Personas

| Persona             | O que faz                                                                 |
|---------------------|--------------------------------------------------------------------------|
| **Colaborador**     | Abre chamados via chat com IA, acompanha próprios tickets, anexa arquivos |
| **Analista TI**     | Atende a fila, reatribui, responde, fecha chamados, alimenta base de conhecimento |
| **Gestor TI**       | Dashboards de SLA, volume, categorias, taxa de auto-resolução, satisfação |
| **Admin TI**        | Configurações (categorias, SLA, modelos de IA, prompts, RAG sources)      |

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy 2.x + Alembic + Pydantic v2
- **Frontend**: Next.js 16 (App Router) + React 19 + TypeScript + ShadCN UI + Tailwind + Zustand + TanStack Query
- **Banco**: PostgreSQL (schema `helpdesk` no cluster compartilhado `infra_postgres`)
- **Vetorial**: `pgvector` no mesmo Postgres (schema `helpdesk_rag`)
- **Storage**: MinIO compartilhado (`infra_minio`), bucket dedicado `helpdesk-attachments`
- **Auth**: banco `security`, tabela `public.users` (diretório compartilhado de colaboradores, read-only)
- **LLM**:
  - Primário: **OpenAI GPT-5 mini** (configurável via env)
  - Fallback: **Anthropic Claude Haiku 4.5** (mesmo padrão do `notion-project-sync`)
- **Embeddings**: `text-embedding-3-small` (OpenAI) — 1536 dims
- **Observabilidade**: structlog + OpenTelemetry (OTLP) + Sentry
- **Deploy**: Docker Swarm em Hetzner CPX62 (mesma stack onde rodam as outras apps internas)

## Portas

| Serviço            | Porta host | Porta interna |
|--------------------|-----------|---------------|
| Backend (FastAPI)  | 8004      | 8004          |
| Frontend (Next.js) | 8081      | 3004          |
| Postgres (local)   | 5436      | 5432          |
| Redis              | 6380      | 6379          |
| MinIO              | 9100/9101 | 9000/9101     |
| ClamAV             | 3310      | 3310          |

## Dev quick start

```bash
cp .env.example .env   # preencher .env
make dev               # sobe todos os containers
make migrate           # aplica migration 0001
open http://localhost:3004
```

Para ter role `it_admin` antes do Sprint 2, adicionar ao `.env`:
```
BOOTSTRAP_ADMIN_UUIDS=<seu-uuid-da-coluna-public.users.uuid>
```
Ver ADR-0003 para detalhes e prazo de remoção.

## Issues abertas

### Sprint 1
1. **Email vs AD username**: confirmar se login por email é suficiente ou se é necessário
   lookup direto no AD (atualmente `auth_service.py` aceita os dois via `OR`).
2. **Prefixo de hash de senha**: confirmar se `public.users.password` usa argon2id em
   100% dos usuários antes do Sprint 1. Fixture de teste parametrizada com `# TODO`.

### Sprint 2
3. **helpdesk.role_overrides**: implementar tabela própria no schema `helpdesk` para
   distinguir `it_lead`/`it_admin` de `it_agent` sem depender de alterações em apps
   externas. Substitui o mecanismo provisório `BOOTSTRAP_ADMIN_UUIDS`.
4. **Remover BOOTSTRAP_ADMIN_UUIDS** de `.env`/`.env.example` e de `role_resolver.py`
   quando `helpdesk.role_overrides` estiver pronta. Adicionar lint CI que falha se var
   estiver não-vazia em `ENV=production`.

### Resolvidas no Sprint 0
5. **Conectividade dev ao banco security**: em dev local o backend conecta no
   `tasks.infra_postgres` real (read-only) via rede overlay `data`. A variável
   `SECURITY_DB_HOST` do `.env` nunca é sobrescrita pelo `docker-compose.yml` —
   removidas as overrides incorretas que apontavam para o postgres local.
   O `scripts/dev_security_stub.sql` é usado exclusivamente pelo CI (GitHub Actions
   não tem acesso ao overlay). Manter o stub sincronizado com o schema real.
6. **Schema correto para public.users**: `SECURITY_SCHEMA=public` no `.env` (schema
   dentro do banco security é sempre `public`). Corrigido após tentativa incorreta de
   usar schema `security`.

### Setup inicial frontend
7. **Makefile frontend-bootstrap**: executar `make frontend-bootstrap` para instalar
   dependências Node e componentes ShadCN antes do primeiro `make dev`.
   Ver `Makefile` para o alvo completo.

## Estrutura do repositório (alvo)

```
helpdesk-ai/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                # config, logging, security, db
│   │   ├── domain/              # modelos SQLAlchemy + schemas Pydantic
│   │   ├── api/v1/              # routers REST
│   │   ├── services/
│   │   │   ├── tickets/         # workflow, SLA, atribuição
│   │   │   ├── ai/              # OpenAI + Anthropic + guardrails
│   │   │   ├── rag/             # ingestion, retrieval, reranking
│   │   │   └── auth/            # adapter para schema `security`
│   │   ├── workers/             # jobs assíncronos (ingestion, embeddings, notif)
│   │   └── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router
│   │   ├── components/
│   │   ├── lib/
│   │   └── hooks/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── docs/
│   ├── SPEC.md
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── RAG_KNOWLEDGE_BASE.md
│   ├── PROMPTS.md
│   ├── DATABASE_SCHEMA.sql
│   └── adr/
└── CLAUDE.md
```

## Princípios de projeto

1. **Conversa primeiro, formulário depois.** Nada de campos obrigatórios na abertura. A IA extrai o que precisa.
2. **A IA é colega, não porteiro.** Ela tenta resolver; se não conseguir, abre o chamado. **Nunca** bloqueia o colaborador.
3. **TI atende, todos abrem.** RBAC simples: papel `it_agent` necessário para tudo que envolva fila/atendimento.
4. **Sem dados sensíveis no prompt.** Sanitização e PII tagging antes de enviar ao LLM (vide `SECURITY.md`).
5. **Prompt injection é tratado como entrada hostil por padrão.** Conteúdo de usuário sempre vai entre delimitadores e nunca como instrução.
6. **Auditoria total.** Toda interação com LLM, todo acesso a anexos, toda mudança de status é logada (`helpdesk.audit_log`).

## Documentos para o Claude Code

Leia nesta ordem antes de começar:

1. `docs/SPEC.md` — o que construir
2. `docs/ARCHITECTURE.md` — como estruturar
3. `docs/DATABASE_SCHEMA.sql` — modelo de dados
4. `docs/SECURITY.md` — guardrails obrigatórios
5. `docs/RAG_KNOWLEDGE_BASE.md` — pipeline de conhecimento
6. `docs/PROMPTS.md` — prompts iniciais (templates)
7. `CLAUDE.md` — convenções de código, testes, OPSEC
8. `prompts/bootstrap.md` — prompt inicial para iniciar o desenvolvimento

## Referências internas (paths locais)

- `/home/mateusfurrier/apps-staging/boardadvisor` — padrão visual (chat-first, shadcn), patterns de IA
- `/home/mateusfurrier/apps-staging/flowsds` — estrutura de stages, lanes, status workflow
