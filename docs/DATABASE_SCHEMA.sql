-- =============================================================================
-- helpdesk-ai — initial schema
--
-- Targets the existing shared Postgres cluster.
-- Reuses banco `security`, tabela `public.users` (read-only, diretório compartilhado de colaboradores).
-- Creates two new schemas:
--   - helpdesk      : operational data (tickets, messages, attachments, etc.)
--   - helpdesk_rag  : knowledge base sources, chunks, embeddings
--
-- All tables use UUID PKs except where a human-friendly sequential number is
-- required (e.g. tickets.number bigserial -> HD-000123).
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE SCHEMA IF NOT EXISTS helpdesk;
CREATE SCHEMA IF NOT EXISTS helpdesk_rag;

-- -----------------------------------------------------------------------------
-- updated_at trigger
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION helpdesk.tg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END $$;

-- -----------------------------------------------------------------------------
-- Bridge to security database
-- -----------------------------------------------------------------------------
-- View exposing the minimum user fields needed by helpdesk-ai.
-- Coluna 'uuid' é char(36); coluna 'active' é boolean; 'departmentid' é integer.
-- NOTA: 'display_name' não existe na tabela real — usar 'name'. Ajustar se necessário.
CREATE OR REPLACE VIEW helpdesk.v_users AS
SELECT
  u.uuid          AS user_uuid,
  u.email         AS email,
  u.name          AS display_name,
  u.active        AS is_active
FROM security.public.users u;

-- Resolve papel do usuário via departmentid (sem dependência de tabelas de grupos).
-- Sprint 2: substituir pelo lookup em helpdesk.role_overrides + departmentid.
-- NOTA: security.user_groups e security.groups NÃO existem no banco real (confirmado
-- em 2026-06-09). A implementação em alembic/versions/0001 usa departmentid diretamente.
CREATE OR REPLACE FUNCTION helpdesk.fn_user_role(p_user_id text)
RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE v_dept int;
BEGIN
  BEGIN
    SELECT departmentid INTO v_dept FROM security.public.users WHERE uuid = p_user_id;
  EXCEPTION WHEN undefined_table THEN RETURN 'employee'; END;
  IF v_dept = 1 THEN RETURN 'it_agent'; END IF;
  RETURN 'employee';
END $$;

-- =============================================================================
-- helpdesk schema
-- =============================================================================

-- Categories
CREATE TABLE helpdesk.categories (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug         text NOT NULL UNIQUE,
  name         text NOT NULL,
  description  text,
  is_active    boolean NOT NULL DEFAULT true,
  sort_order   int NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER tg_categories_updated BEFORE UPDATE ON helpdesk.categories
  FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();

-- SLA matrix: priority x business hours target
CREATE TABLE helpdesk.sla_matrix (
  priority             text PRIMARY KEY
    CHECK (priority IN ('low','normal','high','urgent')),
  first_response_hours int NOT NULL,
  resolution_hours     int NOT NULL,
  description          text
);

-- AI conversations (the chat before/instead of a ticket)
CREATE TABLE helpdesk.ai_conversations (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  status          text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','converted','auto_resolved','abandoned')),
  channel         text NOT NULL DEFAULT 'web'
    CHECK (channel IN ('web','mobile','api')),
  started_at      timestamptz NOT NULL DEFAULT now(),
  closed_at       timestamptz,
  turn_count      int NOT NULL DEFAULT 0,
  guardrail_hits  int NOT NULL DEFAULT 0,
  ticket_id       uuid,  -- FK set after conversion
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_conv_user ON helpdesk.ai_conversations (user_id, started_at DESC);
CREATE INDEX ix_ai_conv_status ON helpdesk.ai_conversations (status);
CREATE TRIGGER tg_ai_conv_updated BEFORE UPDATE ON helpdesk.ai_conversations
  FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();

-- Messages inside the AI conversation
CREATE TABLE helpdesk.ai_conversation_messages (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id  uuid NOT NULL REFERENCES helpdesk.ai_conversations(id) ON DELETE CASCADE,
  role             text NOT NULL CHECK (role IN ('user','assistant','system')),
  content          text NOT NULL,
  content_redacted text,  -- with PII tokens, what was actually sent to LLM
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_msg_conv ON helpdesk.ai_conversation_messages (conversation_id, created_at);

-- Structured AI suggestions per turn (parsed from LLM output)
CREATE TABLE helpdesk.ai_suggestions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id       uuid NOT NULL REFERENCES helpdesk.ai_conversation_messages(id) ON DELETE CASCADE,
  next_action      text NOT NULL
    CHECK (next_action IN ('ask_more','suggest_kb','offer_open_ticket','auto_resolve','escalate_human')),
  suggestions      jsonb NOT NULL DEFAULT '[]'::jsonb,
  ticket_draft     jsonb,
  citations        text[] NOT NULL DEFAULT '{}',
  guardrails       text[] NOT NULL DEFAULT '{}',
  user_feedback    text CHECK (user_feedback IN ('helpful','not_helpful','resolved','reject') OR user_feedback IS NULL),
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_sugg_msg ON helpdesk.ai_suggestions (message_id);

-- Tickets
CREATE TABLE helpdesk.tickets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  number          bigserial NOT NULL UNIQUE,           -- HD-000123 displayed
  title           text NOT NULL CHECK (length(title) <= 200),
  summary         text NOT NULL,
  status          text NOT NULL DEFAULT 'NEW'
    CHECK (status IN ('NEW','TRIAGE','IN_PROGRESS','WAITING_USER','RESOLVED','CLOSED','AUTO_RESOLVED','CANCELLED','REOPENED')),
  priority        text NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','urgent')),
  category_id     uuid REFERENCES helpdesk.categories(id),
  requester_id    uuid NOT NULL,
  assignee_id     uuid,
  conversation_id uuid REFERENCES helpdesk.ai_conversations(id),  -- source chat, nullable
  tags            text[] NOT NULL DEFAULT '{}',
  first_response_due_at timestamptz,
  resolution_due_at     timestamptz,
  first_response_at     timestamptz,
  resolved_at           timestamptz,
  closed_at             timestamptz,
  reopened_count        int NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_tickets_requester ON helpdesk.tickets (requester_id, created_at DESC);
CREATE INDEX ix_tickets_assignee  ON helpdesk.tickets (assignee_id, status);
CREATE INDEX ix_tickets_status    ON helpdesk.tickets (status, priority, created_at);
CREATE INDEX ix_tickets_category  ON helpdesk.tickets (category_id);
CREATE INDEX ix_tickets_tags      ON helpdesk.tickets USING gin (tags);
CREATE TRIGGER tg_tickets_updated BEFORE UPDATE ON helpdesk.tickets
  FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();

-- Backfill FK from conversation -> ticket
ALTER TABLE helpdesk.ai_conversations
  ADD CONSTRAINT fk_ai_conv_ticket FOREIGN KEY (ticket_id) REFERENCES helpdesk.tickets(id) ON DELETE SET NULL;

-- Ticket messages (post-conversion, between user and analyst)
CREATE TABLE helpdesk.ticket_messages (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id    uuid NOT NULL REFERENCES helpdesk.tickets(id) ON DELETE CASCADE,
  author_id    uuid NOT NULL,
  author_role  text NOT NULL CHECK (author_role IN ('requester','agent','system','ai')),
  visibility   text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','internal')),
  body         text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ticket_msg ON helpdesk.ticket_messages (ticket_id, created_at);

-- Attachments (owned by ticket OR conversation, never both, never neither)
CREATE TABLE helpdesk.ticket_attachments (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id       uuid REFERENCES helpdesk.tickets(id) ON DELETE CASCADE,
  conversation_id uuid REFERENCES helpdesk.ai_conversations(id) ON DELETE CASCADE,
  uploader_id     uuid NOT NULL,
  original_name   text NOT NULL,
  stored_key      text NOT NULL,           -- MinIO object key
  mime_type       text NOT NULL,
  size_bytes      bigint NOT NULL,
  sha256          text NOT NULL,
  scanned_status  text NOT NULL DEFAULT 'pending'
    CHECK (scanned_status IN ('pending','clean','infected','error')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_attachment_owner_xor
    CHECK ((ticket_id IS NULL) <> (conversation_id IS NULL))
);
CREATE INDEX ix_attach_ticket ON helpdesk.ticket_attachments (ticket_id);
CREATE INDEX ix_attach_conv   ON helpdesk.ticket_attachments (conversation_id);

-- Status history
CREATE TABLE helpdesk.ticket_status_history (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   uuid NOT NULL REFERENCES helpdesk.tickets(id) ON DELETE CASCADE,
  from_status text,
  to_status   text NOT NULL,
  changed_by  uuid NOT NULL,
  reason      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_status_hist_ticket ON helpdesk.ticket_status_history (ticket_id, created_at);

-- Assignments history
CREATE TABLE helpdesk.ticket_assignments (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id    uuid NOT NULL REFERENCES helpdesk.tickets(id) ON DELETE CASCADE,
  from_user_id uuid,
  to_user_id   uuid NOT NULL,
  changed_by   uuid NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_assign_ticket ON helpdesk.ticket_assignments (ticket_id, created_at);

-- Satisfaction (CSAT after closure)
CREATE TABLE helpdesk.user_satisfaction (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id     uuid NOT NULL UNIQUE REFERENCES helpdesk.tickets(id) ON DELETE CASCADE,
  rating        smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment       text,
  responded_at  timestamptz NOT NULL DEFAULT now()
);

-- KB articles (the curated knowledge base feeding RAG)
CREATE TABLE helpdesk.kb_articles (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug              text NOT NULL UNIQUE,
  title             text NOT NULL,
  category_id       uuid REFERENCES helpdesk.categories(id),
  tags              text[] NOT NULL DEFAULT '{}',
  trust_level       text NOT NULL DEFAULT 'internal_draft'
    CHECK (trust_level IN ('internal_published','internal_draft','internal_only','external_doc')),
  current_version   int NOT NULL DEFAULT 1,
  is_archived       boolean NOT NULL DEFAULT false,
  created_by        uuid NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_kb_trust ON helpdesk.kb_articles (trust_level) WHERE is_archived = false;
CREATE TRIGGER tg_kb_updated BEFORE UPDATE ON helpdesk.kb_articles
  FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();

CREATE TABLE helpdesk.kb_article_versions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id      uuid NOT NULL REFERENCES helpdesk.kb_articles(id) ON DELETE CASCADE,
  version         int NOT NULL,
  body_markdown   text NOT NULL,
  edited_by       uuid NOT NULL,
  edit_summary    text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (article_id, version)
);

-- AI settings (model, embedding, fallback, params) — single active row
CREATE TABLE helpdesk.ai_settings (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  primary_provider         text NOT NULL CHECK (primary_provider IN ('openai','anthropic')),
  primary_model            text NOT NULL,
  fallback_provider        text CHECK (fallback_provider IN ('openai','anthropic')),
  fallback_model           text,
  embedding_provider       text NOT NULL CHECK (embedding_provider IN ('openai','anthropic')),
  embedding_model          text NOT NULL,
  embedding_set_id         text NOT NULL,            -- used by helpdesk_rag.chunks
  max_turns_before_ticket  int NOT NULL DEFAULT 3,
  temperature_primary      numeric(3,2) NOT NULL DEFAULT 0.20,
  is_active                boolean NOT NULL DEFAULT false,
  created_by               uuid NOT NULL,
  created_at               timestamptz NOT NULL DEFAULT now()
);
-- only one active settings row
CREATE UNIQUE INDEX uq_ai_settings_one_active
  ON helpdesk.ai_settings ((true)) WHERE is_active = true;

-- Prompts library (versioned)
CREATE TABLE helpdesk.prompts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  prompt_key   text NOT NULL,
  version      int NOT NULL,
  body         text NOT NULL,
  sha256       text NOT NULL,
  published    boolean NOT NULL DEFAULT false,
  created_by   uuid NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (prompt_key, version)
);
-- exactly one published version per key
CREATE UNIQUE INDEX uq_prompt_one_published
  ON helpdesk.prompts (prompt_key) WHERE published = true;

-- AI call log (every LLM call)
CREATE TABLE helpdesk.ai_call_log (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id   uuid,
  ticket_id         uuid,
  user_id           uuid,
  prompt_key        text NOT NULL,
  prompt_version    int NOT NULL,
  prompt_sha256     text NOT NULL,
  provider          text NOT NULL,
  model             text NOT NULL,
  input_tokens      int,
  output_tokens     int,
  total_tokens      int,
  latency_ms        int,
  http_status       int,
  guardrail_flags   text[] NOT NULL DEFAULT '{}',
  was_fallback      boolean NOT NULL DEFAULT false,
  validation_status text NOT NULL DEFAULT 'ok'
    CHECK (validation_status IN ('ok','retry','failed')),
  request_payload   jsonb,   -- redacted, no PII
  response_payload  jsonb,   -- redacted
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_log_conv   ON helpdesk.ai_call_log (conversation_id, created_at);
CREATE INDEX ix_ai_log_ticket ON helpdesk.ai_call_log (ticket_id, created_at);
CREATE INDEX ix_ai_log_user   ON helpdesk.ai_call_log (user_id, created_at);
CREATE INDEX ix_ai_log_flags  ON helpdesk.ai_call_log USING gin (guardrail_flags);

-- Notifications outbox (delivered async)
CREATE TABLE helpdesk.notification_outbox (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL,
  channel       text NOT NULL CHECK (channel IN ('email','teams','inapp')),
  template_key  text NOT NULL,
  payload       jsonb NOT NULL,
  status        text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','sent','failed','skipped')),
  attempts      int NOT NULL DEFAULT 0,
  last_error    text,
  scheduled_for timestamptz NOT NULL DEFAULT now(),
  sent_at       timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_notif_pending ON helpdesk.notification_outbox (status, scheduled_for)
  WHERE status = 'pending';

CREATE TABLE helpdesk.notification_preferences (
  user_id              uuid PRIMARY KEY,
  email_on_new_message boolean NOT NULL DEFAULT true,
  email_on_status      boolean NOT NULL DEFAULT true,
  teams_on_new_message boolean NOT NULL DEFAULT false,
  digest_enabled       boolean NOT NULL DEFAULT false,
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- Audit log (partitioned by month)
CREATE TABLE helpdesk.audit_log (
  id           uuid NOT NULL DEFAULT gen_random_uuid(),
  actor_id     uuid,
  actor_role   text,
  action       text NOT NULL,
  target_type  text NOT NULL,
  target_id    text,
  before       jsonb,
  after        jsonb,
  ip           inet,
  user_agent   text,
  request_id   text,
  at           timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id, at)
) PARTITION BY RANGE (at);

CREATE TABLE helpdesk.audit_log_y2026m06 PARTITION OF helpdesk.audit_log
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- TODO: schedule monthly partition creation via worker.

CREATE INDEX ix_audit_actor  ON helpdesk.audit_log (actor_id, at);
CREATE INDEX ix_audit_target ON helpdesk.audit_log (target_type, target_id, at);

-- =============================================================================
-- helpdesk_rag schema
-- =============================================================================

CREATE TABLE helpdesk_rag.sources (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type   text NOT NULL
    CHECK (source_type IN ('internal_kb','manual_pdf','internal_docs','repo_md','runbook','legacy_kb','external_doc')),
  name          text NOT NULL,
  config        jsonb NOT NULL DEFAULT '{}'::jsonb,  -- e.g. path, url, schedule
  schedule_cron text,
  default_trust text NOT NULL
    CHECK (default_trust IN ('internal_published','internal_draft','internal_only','external_doc')),
  enabled       boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER tg_sources_updated BEFORE UPDATE ON helpdesk_rag.sources
  FOR EACH ROW EXECUTE FUNCTION helpdesk.tg_set_updated_at();

CREATE TABLE helpdesk_rag.ingestion_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       uuid NOT NULL REFERENCES helpdesk_rag.sources(id) ON DELETE CASCADE,
  status          text NOT NULL CHECK (status IN ('running','succeeded','failed')),
  started_at      timestamptz NOT NULL DEFAULT now(),
  finished_at     timestamptz,
  fetched         int NOT NULL DEFAULT 0,
  extracted       int NOT NULL DEFAULT 0,
  chunked         int NOT NULL DEFAULT 0,
  embedded        int NOT NULL DEFAULT 0,
  dedup_skipped   int NOT NULL DEFAULT 0,
  suspicious_hits int NOT NULL DEFAULT 0,
  duration_ms     int,
  error_log       jsonb NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX ix_runs_source ON helpdesk_rag.ingestion_runs (source_id, started_at DESC);

CREATE TABLE helpdesk_rag.documents (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id   uuid NOT NULL REFERENCES helpdesk_rag.sources(id) ON DELETE CASCADE,
  external_id text,                    -- e.g. file path, URL, KB article slug
  title       text NOT NULL,
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
  trust_level text NOT NULL
    CHECK (trust_level IN ('internal_published','internal_draft','internal_only','external_doc')),
  last_seen   timestamptz NOT NULL DEFAULT now(),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_id, external_id)
);
CREATE INDEX ix_docs_source ON helpdesk_rag.documents (source_id);

CREATE TABLE helpdesk_rag.chunks (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id      uuid NOT NULL REFERENCES helpdesk_rag.documents(id) ON DELETE CASCADE,
  source_id        uuid NOT NULL REFERENCES helpdesk_rag.sources(id) ON DELETE CASCADE,
  position         int NOT NULL,
  section_path     text,
  text             text NOT NULL,
  text_hash        text NOT NULL,
  trust_level      text NOT NULL
    CHECK (trust_level IN ('internal_published','internal_draft','internal_only','external_doc')),
  suspicious       boolean NOT NULL DEFAULT false,
  embedding_set_id text NOT NULL,
  embedding        vector(1536),
  token_count      int,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, position, embedding_set_id)
);
CREATE INDEX ix_chunks_doc       ON helpdesk_rag.chunks (document_id);
CREATE INDEX ix_chunks_source    ON helpdesk_rag.chunks (source_id);
CREATE INDEX ix_chunks_trust     ON helpdesk_rag.chunks (trust_level) WHERE suspicious = false;
CREATE INDEX ix_chunks_embed_hnsw
  ON helpdesk_rag.chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE TABLE helpdesk_rag.gaps (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid,
  ticket_id       uuid,
  original_query  text NOT NULL,
  top_score       numeric(6,4),
  suggested_topic text,
  resolved        boolean NOT NULL DEFAULT false,
  kb_article_id   uuid REFERENCES helpdesk.kb_articles(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_gaps_resolved ON helpdesk_rag.gaps (resolved, created_at);

-- =============================================================================
-- Seeds
-- =============================================================================

INSERT INTO helpdesk.sla_matrix (priority, first_response_hours, resolution_hours, description) VALUES
  ('urgent', 1,  2,  'Negócio parado / risco de segurança'),
  ('high',   2,  8,  'Indivíduo bloqueado'),
  ('normal', 4, 24,  'Impacto moderado'),
  ('low',    8, 72,  'Solicitação ou dúvida sem bloqueio')
ON CONFLICT (priority) DO NOTHING;

INSERT INTO helpdesk.categories (slug, name, description, sort_order) VALUES
  ('access',         'Acesso & senhas',           'Reset, MFA, contas bloqueadas',                       10),
  ('vpn',            'VPN & rede remota',         'Conexão VPN, túneis, acesso externo',                 20),
  ('email',          'E-mail',                    'Outlook, listas, regras, spam',                       30),
  ('hardware',       'Hardware',                  'Notebook, monitor, periféricos, impressora',          40),
  ('software',       'Software',                  'Instalação, atualização, licenças',                   50),
  ('erp',            'SAP / ERP',                 'Acessos e dúvidas SAP B1',                            60),
  ('mobile',         'Celular corporativo',       'Aparelho, plano, MDM',                                70),
  ('share',          'Compartilhamentos',         'Pastas de rede, permissões, SharePoint',              80),
  ('printer',        'Impressão',                 'Filas de impressão, multifuncionais',                 90),
  ('telephony',      'Telefonia',                 'Ramais, headset, teams calls',                       100),
  ('other',          'Outros',                    'Quando nenhuma das outras se aplica',                999)
ON CONFLICT (slug) DO NOTHING;
