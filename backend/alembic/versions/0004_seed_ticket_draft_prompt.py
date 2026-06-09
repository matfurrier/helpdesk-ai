"""Seed TICKET_DRAFT_SYSTEM prompt v1 into helpdesk.prompts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-09
"""

from __future__ import annotations

import hashlib

from alembic import op
from sqlalchemy import text

revision: str = "0004"
down_revision: str = "0003"
branch_labels = None
depends_on = None

_TICKET_DRAFT_BODY = """\
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
- tags: 0–6 tokens, lowercase, hyphens (e.g. "vpn", "remote-access")
- never include PII tokens [PII_*] in title or summary; replace with a generic noun

Output schema (JSON only, no commentary):
{
  "title": "string ≤ 120 chars pt-BR",
  "summary": "string ≤ 1000 chars pt-BR",
  "category_slug": "string (slug from catalog)",
  "priority": "low" | "normal" | "high" | "urgent",
  "tags": ["string", ...]
}
"""

_SHA256 = hashlib.sha256(_TICKET_DRAFT_BODY.encode()).hexdigest()
_SYSTEM_UUID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    conn = op.get_bind()

    # Serialize concurrent Swarm rolling-deploy instances to prevent a race on the
    # uq_prompt_one_published partial index (only one row WHERE published=true per key).
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('seed_prompts_0004'))"))

    conn.execute(
        text(
            "INSERT INTO helpdesk.prompts "
            "(prompt_key, version, body, sha256, published, created_by) "
            "VALUES (:key, :ver, :body, :sha256, true, CAST(:created_by AS uuid)) "
            "ON CONFLICT (prompt_key, version) DO NOTHING"
        ),
        {
            "key": "TICKET_DRAFT_SYSTEM",
            "ver": 1,
            "body": _TICKET_DRAFT_BODY,
            "sha256": _SHA256,
            "created_by": _SYSTEM_UUID,
        },
    )

    conn.execute(
        text(
            "UPDATE helpdesk.prompts SET published = true "
            "WHERE prompt_key = :key AND version = :ver AND published = false"
        ),
        {"key": "TICKET_DRAFT_SYSTEM", "ver": 1},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE helpdesk.prompts SET published = false "
            "WHERE prompt_key = :key AND version = :ver"
        ),
        {"key": "TICKET_DRAFT_SYSTEM", "ver": 1},
    )
