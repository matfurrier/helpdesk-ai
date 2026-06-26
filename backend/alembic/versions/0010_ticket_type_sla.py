"""Add ticket_type to tickets and sla_matrix; update TICKET_DRAFT_SYSTEM to v2.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-26
"""

from __future__ import annotations

import hashlib

from alembic import op
from sqlalchemy import text

revision: str = "0010"
down_revision: str = "0009"
branch_labels = None
depends_on = None

_TICKET_DRAFT_BODY_V2 = """\
You generate ticket metadata from a triage transcript. Output JSON only.

Inputs:
- <history>: full conversation between user and AI triage assistant
- <category_catalog>: list of {slug, description} for available categories
- <user_profile>: requester role and department (PII already redacted)

Constraints:
- title: action-oriented, ≤ 120 chars, in pt-BR ("Não consigo acessar VPN no notebook X")
- summary: ≤ 1000 chars, pt-BR, factual, no speculation, no filler
- category: MUST be a slug from <category_catalog>; if unsure use "other"
- priority: low|normal|high|urgent — map by impact:
    urgent = business fully stopped or security risk
    high   = single person completely blocked
    normal = moderate impact, workaround exists
    low    = question or request, no blocking
- ticket_type — classify by nature of the request:
    incident        = something stopped working: error, crash, outage, access lost, broken
    service_request = request for something new: access, tool, automation, setup, license
    change_request  = modify something existing: config change, policy update, infrastructure
- tags: 0–6 tokens, lowercase, hyphens (e.g. "vpn", "remote-access")
- never include PII tokens [PII_*] in title or summary; replace with a generic noun

Output schema (JSON only, no commentary):
{
  "title": "string ≤ 120 chars pt-BR",
  "summary": "string ≤ 1000 chars pt-BR",
  "category_slug": "string (slug from catalog)",
  "priority": "low" | "normal" | "high" | "urgent",
  "ticket_type": "incident" | "service_request" | "change_request",
  "tags": ["string", ...]
}
"""

_SHA256_V2 = hashlib.sha256(_TICKET_DRAFT_BODY_V2.encode()).hexdigest()
_SYSTEM_UUID = "00000000-0000-0000-0000-000000000000"

# SLA matrix: (ticket_type, priority) → (first_response_hours, resolution_hours)
# first_response is about urgency (same across types); resolution varies by complexity.
_SLA_ROWS = [
    # incidents — something broken, resolve fast
    ("incident", "urgent",  1,   2,  "Incidente crítico — negócio parado"),
    ("incident", "high",    2,   8,  "Incidente de alta prioridade — pessoa bloqueada"),
    ("incident", "normal",  4,  24,  "Incidente moderado — solução de contorno disponível"),
    ("incident", "low",     8,  72,  "Incidente baixo impacto"),
    # service requests — new things, more lead time
    ("service_request", "urgent",  1,   8,  "Solicitação urgente de serviço"),
    ("service_request", "high",    2,  24,  "Solicitação de serviço prioritária"),
    ("service_request", "normal",  4,  72,  "Solicitação de serviço — prazo padrão 3 dias úteis"),
    ("service_request", "low",     8, 120,  "Solicitação de serviço — prazo estendido 5 dias úteis"),
    # change requests — planned work, longest lead time
    ("change_request", "urgent",  1,  24,  "Mudança urgente"),
    ("change_request", "high",    2,  48,  "Mudança de alta prioridade"),
    ("change_request", "normal",  4, 120,  "Mudança planejada — prazo 5 dias úteis"),
    ("change_request", "low",     8, 240,  "Mudança de baixo impacto — prazo 10 dias úteis"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add ticket_type to tickets (default incident for existing rows)
    conn.execute(text(
        "ALTER TABLE helpdesk.tickets "
        "ADD COLUMN IF NOT EXISTS ticket_type text NOT NULL DEFAULT 'incident' "
        "CHECK (ticket_type IN ('incident', 'service_request', 'change_request'))"
    ))

    # 2. Migrate sla_matrix: drop old PK, add ticket_type column, new PK
    conn.execute(text("ALTER TABLE helpdesk.sla_matrix DROP CONSTRAINT IF EXISTS sla_matrix_pkey"))
    conn.execute(text(
        "ALTER TABLE helpdesk.sla_matrix "
        "ADD COLUMN IF NOT EXISTS ticket_type text NOT NULL DEFAULT 'incident'"
    ))
    # Tag existing rows as incident before adding the check constraint
    conn.execute(text("UPDATE helpdesk.sla_matrix SET ticket_type = 'incident'"))
    conn.execute(text(
        "ALTER TABLE helpdesk.sla_matrix "
        "ADD CONSTRAINT sla_matrix_ticket_type_check "
        "CHECK (ticket_type IN ('incident', 'service_request', 'change_request'))"
    ))
    conn.execute(text(
        "ALTER TABLE helpdesk.sla_matrix "
        "ADD CONSTRAINT sla_matrix_pkey PRIMARY KEY (priority, ticket_type)"
    ))

    # 3. Upsert all 12 SLA rows
    for (ttype, priority, frh, rh, desc) in _SLA_ROWS:
        conn.execute(
            text(
                "INSERT INTO helpdesk.sla_matrix "
                "(priority, ticket_type, first_response_hours, resolution_hours, description) "
                "VALUES (:p, :tt, :frh, :rh, :desc) "
                "ON CONFLICT (priority, ticket_type) DO UPDATE "
                "SET first_response_hours = EXCLUDED.first_response_hours, "
                "    resolution_hours = EXCLUDED.resolution_hours, "
                "    description = EXCLUDED.description"
            ),
            {"p": priority, "tt": ttype, "frh": frh, "rh": rh, "desc": desc},
        )

    # 4. Seed TICKET_DRAFT_SYSTEM v2 and publish it
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('seed_prompts_0010'))"))
    conn.execute(
        text(
            "UPDATE helpdesk.prompts SET published = false "
            "WHERE prompt_key = 'TICKET_DRAFT_SYSTEM' AND published = true"
        )
    )
    conn.execute(
        text(
            "INSERT INTO helpdesk.prompts "
            "(prompt_key, version, body, sha256, published, created_by) "
            "VALUES (:key, :ver, :body, :sha256, true, CAST(:created_by AS uuid)) "
            "ON CONFLICT (prompt_key, version) DO UPDATE "
            "SET body = EXCLUDED.body, sha256 = EXCLUDED.sha256, published = true"
        ),
        {
            "key": "TICKET_DRAFT_SYSTEM",
            "ver": 2,
            "body": _TICKET_DRAFT_BODY_V2,
            "sha256": _SHA256_V2,
            "created_by": _SYSTEM_UUID,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Revert prompt
    conn.execute(text(
        "UPDATE helpdesk.prompts SET published = false "
        "WHERE prompt_key = 'TICKET_DRAFT_SYSTEM' AND version = 2"
    ))
    conn.execute(text(
        "UPDATE helpdesk.prompts SET published = true "
        "WHERE prompt_key = 'TICKET_DRAFT_SYSTEM' AND version = 1"
    ))

    # Revert sla_matrix
    conn.execute(text("ALTER TABLE helpdesk.sla_matrix DROP CONSTRAINT IF EXISTS sla_matrix_pkey"))
    conn.execute(text("ALTER TABLE helpdesk.sla_matrix DROP CONSTRAINT IF EXISTS sla_matrix_ticket_type_check"))
    conn.execute(text("DELETE FROM helpdesk.sla_matrix WHERE ticket_type != 'incident'"))
    conn.execute(text("ALTER TABLE helpdesk.sla_matrix DROP COLUMN IF EXISTS ticket_type"))
    conn.execute(text(
        "ALTER TABLE helpdesk.sla_matrix ADD CONSTRAINT sla_matrix_pkey PRIMARY KEY (priority)"
    ))

    # Revert tickets column
    conn.execute(text("ALTER TABLE helpdesk.tickets DROP COLUMN IF EXISTS ticket_type"))
