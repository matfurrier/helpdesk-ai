# ADR-0003 — Identidade via tabela compartilhada public.users (banco security)

**Data:** 2026-06-09  
**Status:** Aceito (mecanismo provisório ativo — rever no Sprint 2)

## Contexto

O helpdesk-ai não é dono da identidade dos colaboradores. Existe uma base de dados
chamada `security` (nome legado, sem significado especial — não é IdP, não é SSO)
que contém a tabela `public.users`. Essa tabela é o diretório compartilhado de todos
os colaboradores e é usada para autenticação por todas as aplicações internas.

helpdesk-ai lê essa tabela de forma **read-only** e nunca a modifica.

## Modelo de identidade

```
banco:  security
schema: public
tabela: public.users

colunas relevantes para o helpdesk-ai:
  uuid          char(36)  — identificador primário; usado no JWT e no audit_log
  login         varchar   — username AD (login corporativo)
  email         varchar   — email corporativo
  password      varchar   — hash argon2id
  active        boolean   — false = conta desativada (bloqueia autenticação)
  departmentid  integer   — determina papel padrão dentro do helpdesk-ai
```

Colunas `role`, flags booleanas e outras colunas presentes em `public.users` pertencem
a outras aplicações que compartilham a tabela. helpdesk-ai **ignora** essas colunas.

## Fluxo de autenticação

1. Cliente envia `credential` (email ou login AD) + `password` via `POST /api/v1/auth/login`.
2. Backend consulta `public.users` no banco `security` (conexão read-only, via `get_security_db()`).
3. Verifica `active = true` e valida hash argon2id via `verify_password()`.
4. Deriva o papel do usuário (ver seção abaixo).
5. Emite JWT com `{uuid, role}` armazenado em cookie HttpOnly `sds_session`.

Cada aplicação interna emite seu próprio JWT. Não há SSO entre apps.

## Derivação de papel (role_resolver.py)

Ordem de precedência, primeiro match ganha:

```
1. uuid ∈ BOOTSTRAP_ADMIN_UUIDS (env var)  →  it_admin   (provisório, Sprint 0)
2. departmentid == IT_DEPARTMENT_ID (1)    →  it_agent
3. caso contrário                          →  employee
```

Não há dependência de tabelas externas de grupos. Os papéis `it_lead` e `it_admin`
serão distinguidos no Sprint 2 via `helpdesk.role_overrides` (ver abaixo).

## Mecanismo provisório: BOOTSTRAP_ADMIN_UUIDS

**Problema**: no Sprint 0 não existe `helpdesk.role_overrides`. O primeiro usuário
precisa ter papel `it_admin` para configurar categorias, SLA e fontes RAG.
Sem esse mecanismo, todo usuário do departamento TI seria apenas `it_agent`.

**Solução provisória**: variável de ambiente `BOOTSTRAP_ADMIN_UUIDS` com lista de
`users.uuid` (char(36)) que recebem papel `it_admin` diretamente.

```ini
# .env
BOOTSTRAP_ADMIN_UUIDS=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

A verificação ocorre **antes** de qualquer consulta ao banco e tem custo O(1) (frozenset
em memória, calculado na inicialização da config).

**Prazo de remoção: Sprint 2.** Quando `helpdesk.role_overrides` estiver implementada:

1. Remover `BOOTSTRAP_ADMIN_UUIDS` de `.env` e `.env.example`.
2. Remover bloco `bootstrap_admin_uuid_set` em `role_resolver.py`.
3. Migrar cada UUID da variável para uma linha em `helpdesk.role_overrides`.
4. Adicionar teste de lint no CI que falha se a variável estiver não-vazia em `ENV=production`.

**Risco**: UUID comprometido equivale a acesso `it_admin` permanente enquanto a variável
existir em produção.  
**Mitigação**: rotacionar ou remover o UUID da variável antes do Sprint 2; monitorar
`helpdesk.audit_log` para ações sensíveis realizadas pelo UUID bootstrapped.

## Separação entre dev e CI

| Ambiente          | Banco security                   | Mecanismo                                           |
|-------------------|----------------------------------|-----------------------------------------------------|
| Dev local         | `tasks.infra_postgres` (real)    | rede overlay `data` no Docker Swarm; read-only      |
| CI (GitHub Actions)| stub local no postgres de teste  | `scripts/dev_security_stub.sql` aplicado antes dos testes |
| Produção (Swarm)  | `tasks.infra_postgres` (real)    | mesmo overlay                                       |

O stub de CI replica apenas as colunas usadas pelo helpdesk-ai (`uuid`, `login`, `email`,
`password`, `active`, `departmentid`). Deve ser mantido sincronizado manualmente com o
schema real sempre que colunas relevantes mudarem.

## Sprint 2: helpdesk.role_overrides

A tabela abaixo substituirá o mecanismo de bootstrap e permitirá distinguir `it_lead`
e `it_admin` de `it_agent` sem depender de alterações em aplicações externas:

```sql
CREATE TABLE helpdesk.role_overrides (
  user_uuid   text        PRIMARY KEY,          -- public.users.uuid (char 36)
  role        text        NOT NULL,             -- 'it_admin' | 'it_lead'
  granted_by  text        NOT NULL,             -- uuid de quem concedeu
  granted_at  timestamptz DEFAULT now()
);
```

`role_resolver.py` consultará `role_overrides` após a verificação de
`bootstrap_admin_uuid_set` e antes da derivação por `departmentid`.

## Consequências

- **Latência**: 1 query extra ao banco `security` por autenticação (aceitável; resultado
  cacheado no JWT até expiração).
- **Isolamento**: o banco `security` nunca é escrito pelo helpdesk-ai — zero risco de
  corromper dados compartilhados entre aplicações.
- **Transição limpa**: adicionar linha em `role_overrides` e remover `BOOTSTRAP_ADMIN_UUIDS`
  são operações independentes — podem ser feitas na mesma deploy sem downtime.
