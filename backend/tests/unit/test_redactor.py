"""Unit tests for app.services.ai.redactor — ≥ 90% coverage required."""

from __future__ import annotations

from app.services.ai.redactor import redact

# ---------------------------------------------------------------------------
# CPF
# ---------------------------------------------------------------------------


def test_cpf_with_mask_is_redacted() -> None:
    text, pii = redact("Meu CPF é 111.444.777-35, preciso de ajuda.")
    assert "[PII_CPF_1]" in text
    assert pii["[PII_CPF_1]"] == "111.444.777-35"
    assert "111.444.777-35" not in text


def test_cpf_digits_only_is_redacted() -> None:
    text, pii = redact("CPF 11144477735")
    assert "[PII_CPF_1]" in text
    assert "11144477735" not in text


def test_cpf_invalid_dv_not_redacted() -> None:
    # 111.444.777-00 — DV incorreto
    text, pii = redact("Número 111.444.777-00")
    assert "[PII_CPF" not in text
    assert not pii


def test_cpf_all_same_digits_not_redacted() -> None:
    text, pii = redact("número 111.111.111-11")
    assert "[PII_CPF" not in text


# ---------------------------------------------------------------------------
# CNPJ
# ---------------------------------------------------------------------------


def test_cnpj_with_mask_is_redacted() -> None:
    text, pii = redact("CNPJ: 11.222.333/0001-81 da empresa.")
    assert "[PII_CNPJ_1]" in text
    assert pii["[PII_CNPJ_1]"] == "11.222.333/0001-81"


def test_cnpj_invalid_dv_not_redacted() -> None:
    text, pii = redact("CNPJ 11.222.333/0001-00")
    assert "[PII_CNPJ" not in text


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def test_email_is_redacted() -> None:
    text, pii = redact("Envie para joao.silva@empresa.com.br por favor.")
    assert "[PII_EMAIL_1]" in text
    assert "joao.silva@empresa.com.br" not in text
    assert pii["[PII_EMAIL_1]"] == "joao.silva@empresa.com.br"


# ---------------------------------------------------------------------------
# Phone BR
# ---------------------------------------------------------------------------


def test_phone_with_parens_is_redacted() -> None:
    text, pii = redact("Ligue para (11) 99999-8888 amanhã.")
    assert "[PII_PHONE_1]" in text
    assert "(11) 99999-8888" not in text


def test_phone_without_parens_is_redacted() -> None:
    text, pii = redact("Fone: 11 3456-7890")
    assert "[PII_PHONE_1]" in text


def test_phone_digits_only_is_redacted() -> None:
    text, pii = redact("tel 11987654321")
    assert "[PII_PHONE_1]" in text


# ---------------------------------------------------------------------------
# CEP
# ---------------------------------------------------------------------------


def test_cep_with_hyphen_is_redacted() -> None:
    text, pii = redact("CEP 01310-100 em São Paulo.")
    assert "[PII_CEP_1]" in text
    assert "01310-100" not in text


# ---------------------------------------------------------------------------
# IPv4
# ---------------------------------------------------------------------------


def test_ipv4_valid_is_redacted() -> None:
    text, pii = redact("Servidor em 192.168.1.100 não responde.")
    assert "[PII_IPV4_1]" in text
    assert "192.168.1.100" not in text


def test_ipv4_invalid_range_not_redacted() -> None:
    # 999.999.999.999 — octeto inválido
    text, pii = redact("endereço 999.999.999.999")
    assert "[PII_IPV4" not in text


# ---------------------------------------------------------------------------
# IPv6
# ---------------------------------------------------------------------------


def test_ipv6_is_redacted() -> None:
    text, pii = redact("Host 2001:0db8:85a3:0000:0000:8a2e:0370:7334 offline.")
    assert "[PII_IPV6_1]" in text
    assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" not in text


# ---------------------------------------------------------------------------
# Credit card (Luhn)
# ---------------------------------------------------------------------------


def test_card_luhn_valid_is_redacted() -> None:
    # 4111 1111 1111 1111 — Visa test number, passes Luhn
    text, pii = redact("Cartão 4111 1111 1111 1111 não funciona.")
    assert "[PII_CARD_1]" in text


def test_card_luhn_invalid_not_redacted() -> None:
    # 4111 1111 1111 1112 — fails Luhn
    text, pii = redact("número 4111111111111112")
    assert "[PII_CARD" not in text


# ---------------------------------------------------------------------------
# Multiple PII in same text
# ---------------------------------------------------------------------------


def test_multiple_pii_types_in_one_text() -> None:
    text = "CPF 111.444.777-35 email test@test.com e CEP 01310-100."
    result, pii = redact(text)
    assert "[PII_CPF_1]" in result
    assert "[PII_EMAIL_1]" in result
    assert "[PII_CEP_1]" in result
    assert "111.444.777-35" not in result
    assert "test@test.com" not in result
    assert "01310-100" not in result
    assert len(pii) == 3


def test_no_pii_returns_empty_map() -> None:
    text = "Meu VPN não conecta após o update do Windows."
    result, pii = redact(text)
    assert result == text
    assert pii == {}


def test_pii_map_allows_restore() -> None:
    original = "CPF 111.444.777-35 é válido."
    redacted, pii = redact(original)
    restored = redacted
    for token, value in pii.items():
        restored = restored.replace(token, value)
    assert restored == original
