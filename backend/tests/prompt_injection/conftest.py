"""Prompt injection test suite — Sprint 0 scaffold.

All cases are xfail until the LLM orchestrator is implemented in Sprint 1.
The suite runs in CI on every PR (pytest -m prompt_injection).
A single failure blocks merge.

Minimum 10 cases required per SECURITY.md §9.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def orchestrator_stub() -> object:
    """Returns the Sprint 0 stub orchestrator. Tests must be updated in Sprint 1."""
    from app.services.ai.orchestrator import orchestrator

    return orchestrator
