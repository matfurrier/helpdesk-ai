# Bootstrap prompt — Sprint 0

> Cole este prompt em uma sessão **nova** do Claude Code rodando no diretório raiz do projeto `helpdesk-ai/`. Use modelo **opusplan**. Tenha o pacote `docs/` no diretório antes de iniciar.

---

You are starting work on **helpdesk-ai**, a new internal IT helpdesk application that will replace a legacy GLPI install. Before writing any code, read the full specification package in this order:

1. `README.md`
2. `CLAUDE.md` — conventions, OPSEC rules, stack versions. Treat OPSEC section as inviolable.
3. `docs/SPEC.md` — functional spec
4. `docs/ARCHITECTURE.md` — technical architecture
5. `docs/SECURITY.md` — threat model, prompt injection defenses, LGPD
6. `docs/RAG_KNOWLEDGE_BASE.md` — RAG ingestion and retrieval
7. `docs/PROMPTS.md` — prompts library and CI test cases
8. `docs/DATABASE_SCHEMA.sql` — initial migration

You may also look (read-only, for visual/architectural inspiration) at:
- `~/apps-staging/boardadvisor` — chat-first layout, sidebar pattern
- `~/apps-staging/flowsds` — multi-stage workflow, server-side transitions

**Do not copy** literal strings, project names, or proprietary content from those references. Use them only to mimic structure, naming patterns, and ShadCN composition.

## Sprint 0 — your objective

Stand up the skeleton with no business logic yet. At the end of Sprint 0 the following must work:

1. **`docker-compose.yml`** at the repo root bringing up:
   - `postgres:16` with pgvector preinstalled, exposing 5436 to the host (avoid collision with FlowSDS 5435).
   - `redis:7-alpine` on 6380.
   - `minio:latest` on 9100/9101.
   - `clamav/clamav:latest` on 3310.
   - `backend` (FastAPI) on `:8004`, hot-reload.
   - `frontend` (Next.js 16) on `:3004`, hot-reload.

2. **Backend** at `backend/`:
   - `pyproject.toml` with the stack listed in `CLAUDE.md` §1.
   - Settings via `pydantic-settings` reading `.env` (provide `.env.example` covering every variable from `CLAUDE.md` §6).
   - `app/main.py` exposing:
     - `GET /api/v1/health` → `{"status":"ok","version":"0.1.0"}`
     - `GET /api/v1/me` → current user (requires auth middleware, returns 401 if no cookie)
   - Auth middleware that validates the existing `__Host-sds_session` cookie against the `security` schema (same pattern as the sister apps; if you don't see clear documentation locally, scaffold a stub `verify_session(cookie) -> User | None` returning a fake test user in dev mode, with a `TODO(security)` comment, and surface the question explicitly to the user).
   - Alembic configured, with the initial migration generated **from `docs/DATABASE_SCHEMA.sql`** (you may convert it into idiomatic SQLAlchemy models + autogenerate, or import the SQL as a single non-autogen migration — your choice, document the decision in an ADR).
   - `structlog` configured (JSON in prod, console in dev).
   - `ruff`, `mypy --strict` configured for `app/services`, `app/core`.
   - `pytest` + `pytest-asyncio` skeleton with one passing test for `/health`.
   - `tests/prompt_injection/` directory with a `conftest.py` and a placeholder `test_pi_00_smoke.py` that imports the orchestrator (stub for now) — wired into CI but marked xfail until Sprint 1.

3. **Frontend** at `frontend/`:
   - `package.json` with Next.js 16, React 19, TS strict, Tailwind 4, ShadCN init.
   - App Router with:
     - `/login` page (server action posts to backend, sets cookie).
     - `/` protected dashboard (placeholder: "Olá, {name}").
     - `/chat/new` placeholder.
   - ShadCN baseline components installed: `button`, `input`, `card`, `dialog`, `toast`.
   - `lib/api.ts` with a fetch helper that forwards cookies and handles 401 → redirect to /login.
   - `vitest` skeleton with one passing test.
   - Theme matches BoardAdvisor — clean, minimal, soft borders. Use ShadCN defaults; do not copy any text content.

4. **CI** (`.github/workflows/ci.yml`):
   - On PR: lint (ruff + eslint), typecheck (mypy + tsc), tests (pytest + vitest), prompt-injection suite (`pytest -m prompt_injection`).
   - Cache `pip` and `pnpm`.

5. **Documentation**:
   - Update `README.md` (already exists) with `make dev`, `make test`, `make migrate` instructions.
   - Create `docs/adr/0001-monorepo-and-stack.md` recording the stack choice.
   - Create `docs/adr/0002-alembic-bootstrap.md` recording how you handled the initial SQL.

## Hard constraints (do NOT break)

- Ports: backend **8004**, frontend **3004**, Postgres **5436**, Redis **6380**, MinIO **9100/9101**, ClamAV **3310**. Adjust only if a real conflict is detected; document any adjustment.
- Schemas: keep `security`, `helpdesk`, `helpdesk_rag` separate. Never `ALTER TABLE security.*`. Read only via the view + function defined in `DATABASE_SCHEMA.sql`.
- Do not add any third-party SaaS dependency beyond OpenAI and Anthropic without explicit user approval.
- OPSEC: zero mentions of the real employer name in any file you create. Use "French agribusiness multinational" in any human-readable doc that could leak.
- Never call OpenAI or Anthropic from outside `app/services/ai/`. In Sprint 0 do not actually call them — just leave the orchestrator stub.

## Before you start coding

1. Run the `@database-architect` subagent on `docs/DATABASE_SCHEMA.sql` and report any concerns (especially around partitioning and the chunks HNSW index).
2. Run the `@security-auditor` subagent on `docs/SECURITY.md` and `docs/PROMPTS.md`, summarize gaps you'd want to close in Sprint 1.
3. Present a concrete file-by-file plan for Sprint 0 to the user for approval before writing files.

## After Sprint 0

Hand back:
- A short status summary (what works, what's stubbed).
- The ADRs you created.
- Open questions for the user (especially around `security` schema reuse, MAK activation of dev DB, MinIO credential provisioning).
- Suggested order for Sprint 1: AI orchestrator + redactor + first end-to-end chat turn (no RAG yet, no tickets yet).

Stay strict about scope. Do not implement RAG, prompts, or ticket logic in Sprint 0 — that is Sprint 1+.
