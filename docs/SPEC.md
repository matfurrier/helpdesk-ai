# SPEC — helpdesk-ai

Especificação funcional. O **como** vive em `ARCHITECTURE.md`.

## 1. Fluxo principal — abertura de chamado

```
Colaborador → Dashboard → [Novo chamado]
   ↓
Chat de triagem com IA (1ª mensagem livre)
   ↓
IA faz perguntas curtas (máx. 3 turns) para entender:
   - O que está acontecendo? (descrição)
   - Quando começou? (timing)
   - Já tentou algo? (contexto)
   ↓
IA consulta RAG (base interna) e propõe 1–3 sugestões acionáveis
   ↓
Colaborador valida:
   ├─ "Resolveu" → ticket fechado como AUTO_RESOLVED + feedback
   └─ "Não resolveu" / "Quero abrir chamado mesmo assim"
        ↓
IA gera:
   - Título
   - Resumo executivo
   - Categoria sugerida + prioridade sugerida
   - Tags
   - Transcript completo do chat (anexado ao ticket)
        ↓
Ticket entra na fila do TI com status NEW
```

## 2. Autenticação

**Email apenas.** A autenticação é feita exclusivamente pelo campo `email` de
`public.users` (banco `security`), comparação case-insensitive.

O campo `login` (AD username) existe na tabela mas **não é critério de busca**.
Query executada em infra_postgres em 2026-06-09 confirmou 0 usuários ativos com
`login` diferente do prefixo do email:

```sql
SELECT count(*) FROM public.users
WHERE active = 1 AND login IS NOT NULL
  AND login != split_part(email, '@', 1);
-- Resultado: 0
```

**Decisão:** Wontfix — login por AD username não é necessário. Se o cenário
mudar (ex: usuários AD sem email corporativo), abrir nova issue antes de
reativar a condição `login = :credential` em `auth_service.py`.

## 3. Papéis e permissões

| Papel        | Pode                                                                 | Não pode                                |
|--------------|----------------------------------------------------------------------|------------------------------------------|
| `employee`   | Abrir chamado, ver/comentar/anexar nos próprios chamados, avaliar    | Ver fila, ver chamados de terceiros      |
| `it_agent`   | Tudo de `employee` + ver fila, assumir, reatribuir, responder, fechar | Configurar categorias, alterar SLA       |
| `it_lead`    | Tudo de `it_agent` + dashboards gerenciais, reabrir, mesclar tickets | Mexer em prompts/RAG sources             |
| `it_admin`   | Tudo                                                                 | —                                        |

Mapping para o schema `security` existente: derivado de `departmentid` (Sprint 0/1)
e futuramente de `helpdesk.role_overrides` (Sprint 2). Default implícito = `employee`
para qualquer usuário autenticado.

## 3. Telas

### 3.1 Dashboard do colaborador (`/`)

- **Card "Abrir chamado"** com CTA grande e ilustração (estilo BoardAdvisor)
- **Lista "Meus chamados"** com chips de status e SLA
- **Card "Sugestões da base"** (3 artigos populares da KB para a área dele)
- **Histórico** colapsável com chamados antigos

### 3.2 Chat de triagem (`/chat/new` e `/chat/:conversationId`)

- Layout estilo BoardAdvisor (chat central, sidebar mínima)
- Input com suporte a anexos (drag-and-drop ou botão), markdown básico
- Bubbles diferenciados (assistente vs. usuário)
- Quando a IA propõe sugestões, renderiza **action cards** com:
  - Título da sugestão
  - Passos numerados
  - Botões: `Funcionou` / `Não funcionou` / `Não consigo executar`
- Indicador "digitando" enquanto a IA processa
- Botão sempre visível: **"Abrir chamado mesmo assim"** (não esconder do usuário)

### 3.3 Detalhe do ticket — visão colaborador (`/tickets/:id`)

- Cabeçalho: título, status, categoria, SLA (deadline + cor)
- Thread de mensagens (incluindo o transcript inicial do chat colapsado)
- Composer para responder + anexar
- Botão "Adicionar contexto"
- Avaliação NPS ao fechar (1–5 estrelas + comentário opcional)

### 3.4 Fila (`/queue`) — `it_agent+`

- Tabela com filtros: status, categoria, prioridade, SLA, atribuído a, solicitante
- Colunas: ID, título, solicitante, categoria, prioridade, SLA restante, status, agente
- Ação rápida: assumir, reatribuir
- Vista alternativa: **Kanban** por status (`NEW`, `TRIAGE`, `IN_PROGRESS`, `WAITING_USER`, `RESOLVED`)

### 3.5 Detalhe do ticket — visão TI (`/queue/:id`)

- Mesma thread, mas com:
  - Painel lateral com metadados (categoria, prioridade, SLA, histórico de atribuições)
  - **Botão "Sugerir resposta com IA"** (rascunho, nunca envio automático)
  - Ações: reatribuir, mudar prioridade, mudar status, marcar como spam, mesclar, transformar em artigo da KB
  - Notas internas (não visíveis ao colaborador)

### 3.6 Base de Conhecimento (`/kb`)

- Listagem por categoria
- Busca (textual + semântica)
- Artigo: markdown renderizado, com badges de versão, autor, "última atualização"
- `it_lead+` podem criar/editar; aprovação simples (rascunho → publicado)

### 3.7 Admin (`/admin`) — `it_admin`

- Categorias e subcategorias (CRUD)
- Matriz de SLA (categoria × prioridade → horas)
- Fontes do RAG (URLs internas, repos, pastas MinIO, paths SharePoint, etc.) + status de ingestão
- Prompts (versionados, com diff e rollback)
- Modelos de IA (provider primário/fallback, modelo, temperatura, max tokens)
- Usuários e grupos (read-only, vem do schema `security`)

## 4. Workflow de status

```
NEW ──► TRIAGE ──► IN_PROGRESS ──► WAITING_USER ─┐
                       │                           │
                       └────────► RESOLVED ◄───────┘
                                     │
                                     ├─► CLOSED (após 72h sem reabertura ou avaliação)
                                     └─► REOPENED → IN_PROGRESS

AUTO_RESOLVED (resolvido pela IA antes da abertura, não passa pela fila)
CANCELLED (colaborador desistiu antes de virar ticket)
```

- `AUTO_RESOLVED` e `CANCELLED` não geram SLA nem entram em fila.
- Reabertura permitida em até **30 dias** após `CLOSED`.

## 5. SLA

- Matriz `categoria × prioridade → horas úteis` (configurável)
- Horário comercial padrão: **08:00–18:00, seg–sex, fuso `America/Sao_Paulo`** (configurável)
- Job assíncrono recalcula SLA a cada mudança de status e a cada 5 minutos
- Notificação em `WARN` (75% consumido) e `BREACH` (100%) ao agente e ao `it_lead`

## 6. Categorias iniciais (sugestão)

- Acesso (login, senha, MFA, SSO)
- VPN e Rede
- SAP B1
- Email e Microsoft 365
- Apps internos (NPD Flow, RNC Flow, FlowSDS, BoardAdvisor, CargoLoad, sso-manager, etc.)
- Estação de trabalho (notebook, periféricos)
- Impressão
- Telefonia
- Solicitação (novo equipamento, novo acesso)
- Segurança da informação (incidente, suspeita de phishing)
- Outro

Cada categoria tem `default_priority`, `default_sla_hours`, `auto_route_to_group` (opcional).

## 7. Anexos

- Tipos permitidos: `png, jpg, jpeg, gif, webp, pdf, docx, xlsx, pptx, txt, log, csv, json, eml, msg, zip`
- Tamanho máximo: 25 MB por arquivo, 100 MB total por ticket
- Armazenados em MinIO (`infra_minio`), bucket `helpdesk-attachments`, key pattern: `tickets/{ticket_id}/{uuid}-{filename}`
- Acesso via **presigned URL** com expiração curta (5 minutos), gerada pelo backend após verificação de autorização
- Scan antivírus assíncrono (ClamAV ou equivalente) antes de liberar o presigned URL — anexo em `quarantine` enquanto não escaneado
- EXIF removido de imagens

## 8. RAG — base de conhecimento

Detalhado em `RAG_KNOWLEDGE_BASE.md`. Resumo:

- Fontes: artigos da KB interna, docs das aplicações em `apps-staging`, manuais de VPN, runbooks
- Chunking: ~800 tokens com overlap de 100
- Embedding: `text-embedding-3-small` (OpenAI) — 1536 dims, `cosine`
- Retrieval: top-k=8 → reranking → top-3 ao prompt
- Citação obrigatória: a IA precisa retornar `source_ids` que renderizam como links no chat

## 9. Notificações

- Canais: email (SMTP corporativo), Microsoft Teams (webhook por grupo), in-app
- Eventos: novo ticket, atribuição, novo comentário, mudança de status, SLA warn/breach, fechamento
- Preferências por usuário (opt-in/opt-out por canal e evento)

## 10. Métricas (dashboard gerencial)

- Volume de chamados (período, categoria, prioridade)
- Taxa de **auto-resolução** (chamados resolvidos só pela IA / total iniciado)
- TMR (tempo médio de resolução) por categoria/prioridade
- SLA: % no prazo, % em warn, % em breach
- NPS / CSAT
- Top categorias / top solicitantes
- Carga por agente
- Top consultas RAG sem match satisfatório (sinal de lacuna na KB)

## 11. Não-objetivos (out of scope no MVP)

- Não substitui ITSM completo (CMDB, change, problem, asset)
- Não tem chatbot público externo (cliente final)
- Não integra com SCCM/Intune (deixar para futuras integrações)
- Não há mobile app nativo — PWA responsivo é suficiente
- Não traduz chamados (PT-BR apenas no MVP)

## 12. LGPD / Compliance

- Base legal: legítimo interesse (suporte interno)
- Dados pessoais tratados: nome, email corporativo, matrícula, conteúdo das mensagens
- Retenção: tickets fechados por **5 anos**, depois anonimização (mantém métricas, perde PII)
- Direito de acesso/eliminação: requisições passam pelo DPO (Mateus). Endpoint admin para export de dados por titular.
- Conteúdo enviado ao LLM: PII redatada (CPF, e-mails de terceiros, telefones) **antes** do envio. Provider OpenAI configurado com `data retention zero` (DPA já existente).
- Logs de auditoria imutáveis: tabela `helpdesk.audit_log` append-only.

## 13. ISO 27001 — controles relacionados

- A.5.16 — Identidade (reuso do schema `security`)
- A.5.18 — Direitos de acesso (RBAC)
- A.5.23 — Segurança em serviços de nuvem (DPA OpenAI/Anthropic)
- A.8.2 — Acesso privilegiado (papel `it_admin` separado)
- A.8.15 — Registros (audit_log)
- A.8.28 — Codificação segura (vide `SECURITY.md`)

## 14. Aceite do MVP (definition of done)

- [ ] Login via schema `security` funcional
- [ ] Dashboard do colaborador
- [ ] Chat de triagem com IA + RAG + sugestões + auto-resolução
- [ ] Conversão chat → ticket
- [ ] Fila para TI (lista + kanban)
- [ ] Detalhe do ticket (ambas visões) com anexos
- [ ] SLA básico (matriz + notificação warn/breach)
- [ ] Notificação por email
- [ ] Admin: categorias, SLA, fontes RAG, prompts
- [ ] Métricas básicas (volume, auto-resolução, SLA, NPS)
- [ ] LGPD: redação de PII antes do LLM, retenção configurada, export do titular
- [ ] Guardrails contra prompt injection (vide `SECURITY.md`)
- [ ] Auditoria de toda interação com LLM
- [ ] Testes: cobertura ≥70% backend, ≥50% frontend; smoke E2E do fluxo principal
