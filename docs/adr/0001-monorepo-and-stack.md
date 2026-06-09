# ADR-0001 — Stack base e estrutura de monorepo

**Data:** 2026-06-09  
**Status:** Aceito

## Contexto

O helpdesk-ai é uma aplicação interna nova que precisa coexistir com outras apps internas
(flowsds, boardadvisor, cargoload, etc.) no mesmo cluster Docker Swarm Hetzner.
O time já domina Python/FastAPI e Next.js; a base de dados compartilhada é Postgres 16.

## Decisão

| Camada    | Tecnologia                              | Justificativa |
|-----------|------------------------------------------|---------------|
| Backend   | Python 3.12 + FastAPI 0.115+            | Mesmo padrão das apps irmãs; async nativo; suporte pgvector via asyncpg |
| Frontend  | Next.js 15 + React 19 + TypeScript 5    | App Router, RSC, SSE; padrão interno |
| ORM/DB    | SQLAlchemy 2.x async + asyncpg          | Performance; sem ORM mágico |
| Migrations| Alembic                                 | Versionamento explícito, sem autogenerate para o schema inicial |
| Auth      | Argon2id (argon2-cffi) + JWT cookie     | Mesmo hash usado pelas demais apps internas; cookie HttpOnly > Bearer para browser apps |
| UI        | Tailwind 4 + ShadCN                     | Consistência com boardadvisor; zero custom CSS |
| Testes    | pytest-asyncio + vitest                 | Padrão interno |

## Estrutura

Monorepo único (`helpdesk-ai/`) com `backend/` e `frontend/` separados.
Justificativa: CI pode testar cada camada independentemente; Docker images distintas.

## Consequências

- PRs devem manter `backend/` e `frontend/` isolados (nunca misturar commits das duas camadas).
- Porta 8004 (backend) e 3004 (frontend) reservadas — verificar conflito com outras apps antes de subir.
