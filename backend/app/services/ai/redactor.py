"""PII redactor — Sprint 1.

Replaces sensitive data in user text with reversible placeholder tokens.
Returns (redacted_text, pii_map) where pii_map maps token → original value.

Supported detectors (in priority order):
  CPF (with DV), CNPJ (with DV), credit card (Luhn), email,
  phone BR, CEP, IPv6, IPv4.

The pii_map is passed to token_map.store() for later restoration.
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _validate_cpf(digits: str) -> bool:
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    total = sum(int(d) * (10 - i) for i, d in enumerate(digits[:9]))
    r = total % 11
    if int(digits[9]) != (0 if r < 2 else 11 - r):  # noqa: PLR2004
        return False
    total = sum(int(d) * (11 - i) for i, d in enumerate(digits[:10]))
    r = total % 11
    return int(digits[10]) == (0 if r < 2 else 11 - r)  # noqa: PLR2004


def _validate_cnpj(digits: str) -> bool:
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(digits[:12], w1, strict=True))
    r = total % 11
    if int(digits[12]) != (0 if r < 2 else 11 - r):  # noqa: PLR2004
        return False
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(int(d) * w for d, w in zip(digits[:13], w2, strict=True))
    r = total % 11
    return int(digits[13]) == (0 if r < 2 else 11 - r)  # noqa: PLR2004


def _luhn_check(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:  # noqa: PLR2004
                n -= 9
        total += n
    return total % 10 == 0


def _ipv4_valid(match: str) -> bool:
    parts = match.split(".")
    return all(0 <= int(p) <= 255 for p in parts)  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_RE_CPF = re.compile(r"\b(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})\b")
_RE_CNPJ = re.compile(r"\b(\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2})\b")
_RE_CARD = re.compile(r"\b(\d[\d\s-]{11,17}\d)\b")
_RE_EMAIL = re.compile(
    r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b",
    re.A,
)
_RE_PHONE_BR = re.compile(
    r"\(?\b(\d{2})\)?[\s.\-]?(\d{4,5})[\s.\-]?(\d{4})\b",
)
_RE_CEP = re.compile(r"\b(\d{5}-\d{3})\b|\b(\d{8})\b")
_RE_IPV6 = re.compile(
    r"\b((?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}"
    r"|::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}"
    r"|[0-9a-fA-F]{1,4}::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4})\b",
)
_RE_IPV4 = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def redact(text: str) -> tuple[str, dict[str, str]]:
    """Replace PII in *text* with reversible tokens.

    Returns (redacted_text, pii_map) where pii_map is {token: original}.
    Processing order matters: more specific patterns run first to avoid
    partial matches (card before phone, CPF before generic digit runs).
    """
    normalized = unicodedata.normalize("NFKC", text)
    pii_map: dict[str, str] = {}
    counters: dict[str, int] = {}

    def _token(kind: str) -> str:
        counters[kind] = counters.get(kind, 0) + 1
        return f"[PII_{kind}_{counters[kind]}]"

    result = normalized

    # --- CPF ---
    for m in list(_RE_CPF.finditer(result)):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 11 and _validate_cpf(digits):
            tok = _token("CPF")
            pii_map[tok] = raw
            result = result.replace(raw, tok, 1)

    # --- CNPJ ---
    for m in list(_RE_CNPJ.finditer(result)):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 14 and _validate_cnpj(digits):
            tok = _token("CNPJ")
            pii_map[tok] = raw
            result = result.replace(raw, tok, 1)

    # --- Credit card (Luhn, 13–19 digits) ---
    for m in list(_RE_CARD.finditer(result)):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        if 13 <= len(digits) <= 19 and _luhn_check(digits):
            tok = _token("CARD")
            pii_map[tok] = raw
            result = result.replace(raw, tok, 1)

    # --- Email ---
    for m in list(_RE_EMAIL.finditer(result)):
        raw = m.group(1)
        tok = _token("EMAIL")
        pii_map[tok] = raw
        result = result.replace(raw, tok, 1)

    # --- Phone BR ---
    for m in list(_RE_PHONE_BR.finditer(result)):
        raw = m.group(0)
        tok = _token("PHONE")
        pii_map[tok] = raw
        result = result.replace(raw, tok, 1)

    # --- CEP ---
    for m in list(_RE_CEP.finditer(result)):
        raw = m.group(1) or m.group(2)
        if raw:
            tok = _token("CEP")
            pii_map[tok] = raw
            result = result.replace(raw, tok, 1)

    # --- IPv6 (before IPv4 to avoid partial match) ---
    for m in list(_RE_IPV6.finditer(result)):
        raw = m.group(1)
        tok = _token("IPV6")
        pii_map[tok] = raw
        result = result.replace(raw, tok, 1)

    # --- IPv4 ---
    for m in list(_RE_IPV4.finditer(result)):
        raw = m.group(1)
        if _ipv4_valid(raw):
            tok = _token("IPV4")
            pii_map[tok] = raw
            result = result.replace(raw, tok, 1)

    return result, pii_map
