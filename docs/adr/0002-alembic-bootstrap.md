# ADR-0002 — Estratégia de migration inicial (Alembic)

**Data:** 2026-06-09  
**Status:** Aceito

## Contexto

O `docs/DATABASE_SCHEMA.sql` foi criado manualmente pela equipe e contém o DDL
completo dos schemas `helpdesk` e `helpdesk_rag` (incluindo pgvector, particionamento,
seeds de SLA e categorias).

Há duas abordagens para converter isso em Alembic:
1. **Autogenerate**: criar models SQLAlchemy e usar `alembic revision --autogenerate`.
2. **Import direto**: converter o SQL em uma única migration manual (`op.execute(text(...))`).

## Decisão

**Opção 2 — import direto** na revision `0001`.

Motivos:
- O SQL já foi revisado e aprovado; autogenerate adicionaria ruído (colunas na ordem errada,
  constraints com nomes diferentes, etc.).
- Em Sprint 0 não há models SQLAlchemy ainda — gerá-los só para autogenerate seria esforço
  prematuro que não muda o comportamento de runtime.
- Manutenção futura: a partir do Sprint 1, novos campos serão adicionados com autogenerate
  sobre os models que serão criados então.

## Adaptações em relação ao SQL original

1. **User IDs como `text`** (não `uuid`): `public.users.uuid` no banco `security` é `char(36)`,
   não um `uuid` PostgreSQL nativo. Usar `text` no schema `helpdesk` evita casts explícitos
   e mantém compatibilidade com a tabela compartilhada.
2. **Partição `default`**: adicionada `audit_log_default` além das partições mensais,
   evitando erro de inserção fora do range definido.
3. **HNSW index parcial**: `WHERE embedding IS NOT NULL` — index não cobre linhas sem
   embedding ainda (ingestão assíncrona), reduzindo overhead inicial.
4. **Cross-schema references**: `v_users` e `fn_user_role` são criadas via bloco `DO $$...
   EXCEPTION...END` que captura `undefined_table` e loga aviso em vez de falhar. Isso
   permite rodar a migration no postgres local de dev (que usa stub).
5. **`IF NOT EXISTS`** em todas as DDLs para idempotência (migration pode ser re-rodada
   em caso de rollback parcial).

## Consequências

- A migration `0001` é idempotente mas não reversível de forma segura (downgrade dropa
  os schemas inteiros com `CASCADE`). Usar downgrade apenas em dev.
- A partir do Sprint 1: criar models em `app/models/` e usar autogenerate normalmente.
