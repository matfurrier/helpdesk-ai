"""Input guardrail checks — Sprint 1.

Returns a list of flag strings for any suspicious patterns detected in user input.
All patterns compiled at module load; check() has no I/O.

Called BEFORE redactor so that CPF/phone in the payload also trigger pii_exposure flag.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Patterns (compiled once)
# ---------------------------------------------------------------------------

_RE_PROMPT_INJECTION = re.compile(
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|rules?|prompts?)|"
    r"disregard\s+(all\s+)?(previous|prior)\s+instructions?|"
    r"esque[cç][ae]?\s+(as?\s+)?(instru[çc][oõ]es?|regras?)\s+anteriores?",
    re.I | re.U,
)

_RE_SYSTEM_TAG = re.compile(r"</?\s*system\s*>", re.I)

_RE_BASE64_PAYLOAD = re.compile(
    r"(?:[A-Za-z0-9+/]{4}){8,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?",
    re.A,
)

_RE_KB_OVERRIDE = re.compile(
    r"SYSTEM\s+OVERRIDE|you\s+are\s+now\s+(unrestricted|unfiltered)|"
    r"voc[eê]\s+[eé]\s+agora\s+(irrestrito|sem\s+filtros?|livre)",
    re.I | re.U,
)

_RE_FOREIGN_TICKET = re.compile(r"ticket\s+(?:ID\s+|#\s*)?\d{3,}", re.I | re.U)

_RE_CREDENTIAL_HARVEST = re.compile(
    r"me\s+pass[ae]\s+(sua?\s+)?senha|"
    r"senha\s+do\s+sistema|"
    r"informe?\s+(sua?\s+)?senha|"
    r"enter\s+your\s+password|"
    r"provide\s+your\s+(credentials?|password)",
    re.I | re.U,
)

_RE_SSRF_URL = re.compile(
    # Matches any URL whose hostname does NOT end exactly in a trusted domain.
    # Uses a word-boundary-style approach: trusted TLD must end the hostname component.
    r"https?://(?!(?:(?:[\w-]+\.)*)?(?:microsoft|google|apple|github)\.com(?:[:/]|$))\S+",
    re.I,
)

# Detect Cyrillic or Greek lookalike characters in the first 50 chars.
# Unicode ranges: Cyrillic U+0400-U+04FF, Greek U+0370-U+03FF
_RE_HOMOGLYPH = re.compile(r"[Ͱ-ϿЀ-ӿ]")

_RE_ROLE_INJECT = re.compile(
    r"^\s*\[(assistant|system|user|ai)\]\s*",
    re.I | re.M,
)

_RE_CODE_EXEC = re.compile(
    r"rm\s+-rf|os\.system\s*\(|subprocess\.|exec\s*\(|eval\s*\(|"
    r"__import__\s*\(|import\s+os\b",
    re.I,
)

_RE_JAILBREAK = re.compile(
    r"\bjailbreak\b|DAN\s+mode|unrestricted\s+mode|"
    r"pretend\s+you\s+(have\s+no\s+(rules?|limits?)|are\s+(?:evil|uncensored))",
    re.I,
)

# PII patterns (simplified — full validation in redactor.py)
_RE_CPF_QUICK = re.compile(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b")
_RE_CNPJ_QUICK = re.compile(r"\b\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2}\b")
_RE_CARD_QUICK = re.compile(r"\b(?:\d[\s-]?){13,19}\d\b")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check(text: str) -> list[str]:
    """Return a list of guardrail flag strings found in *text* (may be empty)."""
    normalized = unicodedata.normalize("NFKC", text)
    flags: list[str] = []

    if _RE_PROMPT_INJECTION.search(normalized):
        flags.append("prompt_injection")

    if _RE_SYSTEM_TAG.search(normalized):
        flags.append("system_tag_inject")

    # Base64: require decodeable block ≥ 40 chars that's not alphanumeric-only
    b64_match = _RE_BASE64_PAYLOAD.search(normalized)
    if b64_match and len(b64_match.group()) >= 40:
        flags.append("base64_payload")

    if _RE_KB_OVERRIDE.search(normalized):
        flags.append("kb_override")

    if _RE_FOREIGN_TICKET.search(normalized):
        flags.append("foreign_ticket")

    if _RE_CREDENTIAL_HARVEST.search(normalized):
        flags.append("credential_harvest")

    if _RE_SSRF_URL.search(normalized):
        flags.append("ssrf_url")

    # Scan full text (not just first 50 chars) to catch padded injections
    if _RE_HOMOGLYPH.search(normalized):
        flags.append("homoglyph")

    if _RE_ROLE_INJECT.search(normalized):
        flags.append("role_inject")

    if _RE_CODE_EXEC.search(normalized):
        flags.append("code_execution")

    if _RE_JAILBREAK.search(normalized):
        flags.append("jailbreak_keyword")

    if (
        _RE_CPF_QUICK.search(normalized)
        or _RE_CNPJ_QUICK.search(normalized)
        or _RE_CARD_QUICK.search(normalized)
    ):
        flags.append("pii_exposure")

    return flags
