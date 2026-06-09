from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

_TRUST_LEVELS = frozenset({"internal_published", "internal_draft", "internal_only", "external_doc"})


class ArticleCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    slug: str
    title: str
    body_markdown: str
    tags: list[str] = []
    trust_level: str = "internal_draft"

    @field_validator("trust_level")
    @classmethod
    def _validate_trust(cls, v: str) -> str:
        if v not in _TRUST_LEVELS:
            raise ValueError(f"trust_level must be one of {sorted(_TRUST_LEVELS)}")
        return v


class ArticleIngestOut(BaseModel):
    model_config = ConfigDict(strict=True)

    article_id: str
    slug: str
    chunks_created: int
