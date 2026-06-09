# ADR-0006 — Interpolação de schema em queries SQL (noqa S608)

**Status:** Aceito  
**Data:** 2026-06-09  
**Contexto:** helpdesk-ai autentica usuários e resolve roles via queries no banco `security`. O nome do schema (`public` por padrão) é configurável via variável de ambiente `SECURITY_SCHEMA`.

---

## Problema

As queries em `auth_service.py` e `role_resolver.py` interpolam `settings.security_schema`
no SQL usando f-string:

```python
f"SELECT ... FROM {settings.security_schema}.users WHERE ..."
```

O linter ruff (regra S608) emite aviso de possível SQL injection.

---

## Decisão

Usamos `# noqa: S608` nas linhas afetadas. O aviso é **falso positivo** neste contexto
pelos seguintes motivos:

1. **Validação em boot**: `settings.security_schema` é validado por `@field_validator`
   em `app/core/config.py` contra a allowlist `{"public", "security"}` ao inicializar
   o processo. Qualquer valor fora dessa lista lança `ValueError` antes de qualquer
   query ser executada.

2. **Origem controlada**: O valor vem exclusivamente de variável de ambiente definida
   na configuração do deploy (`.env` ou Swarm secret) — nunca de input do usuário,
   de parâmetros de requisição ou de dados lidos do banco.

3. **Sem escalada de privilégio**: Os dois valores permitidos (`public`, `security`)
   são schemas read-only do banco compartilhado. Não há schema com dados mais
   sensíveis que possa ser acessado alterando essa variável.

4. **Parâmetros SQL mantidos**: As colunas de filtro (`email`, `uuid`) continuam
   usando parâmetros SQLAlchemy (`:credential`, `:uuid`) — imunes a injection.

---

## Alternativas consideradas

| Alternativa | Por que não adotada |
|-------------|---------------------|
| Mapa estático `{"public": "public", ...}` lookup | Equivalente funcional; adiciona ruído sem ganho real de segurança |
| `sqlalchemy.schema.quoted_name` | Não resolve: S608 flageia a construção do literal, não o valor |
| Hardcode `public` no código | Impossível — prod usa schema `public` no banco `security`, e testes usam o mesmo schema no banco local; a variável existe para suportar ambientes futuros |

---

## Consequências

- Toda mudança em `SECURITY_SCHEMA` de `.env` ou `.env.prod` que coloque valor fora
  de `{"public", "security"}` falha no startup — comportamento desejado (fail-fast).
- O noqa é documentado aqui para que revisores futuros entendam por que o suppressor
  é intencional, não descuido.
