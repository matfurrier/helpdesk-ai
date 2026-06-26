"""SMTP email sender via aiosmtplib (Office365 / STARTTLS)."""

from __future__ import annotations

import email.mime.multipart
import email.mime.text

import aiosmtplib
import structlog

from app.core.config import settings

log = structlog.get_logger()


def _mime(to: list[str], subject: str, body_html: str) -> email.mime.multipart.MIMEMultipart:
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.mail_from
    msg["To"] = ", ".join(to)
    msg.attach(email.mime.text.MIMEText(body_html, "html", "utf-8"))
    return msg


async def send_email(to: list[str], subject: str, body_html: str) -> bool:
    """Send an HTML email. Returns True on success, False on failure."""
    if not settings.smtp_user or not to:
        log.warning("email.skipped", reason="no_smtp_config_or_recipients")
        return False
    try:
        msg = _mime(to, subject, body_html)
        await aiosmtplib.send(
            msg,
            hostname=settings.mail_host,
            port=settings.mail_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
        )
        log.info("email.sent", to=to, subject=subject)
        return True
    except Exception as exc:  # noqa: BLE001
        log.error("email.failed", to=to, subject=subject, error=str(exc))
        return False


# ---------------------------------------------------------------------------
# HTML templates
# ---------------------------------------------------------------------------

_BASE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8">
<style>
body{{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0}}
.wrap{{max-width:600px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden}}
.hdr{{background:#1e3a5f;padding:24px 32px;color:#fff;font-size:18px;font-weight:bold}}
.body{{padding:24px 32px;color:#333;line-height:1.6}}
.btn{{display:inline-block;margin-top:16px;padding:12px 24px;background:#2563eb;
      color:#fff;border-radius:6px;text-decoration:none;font-weight:bold}}
.ftr{{padding:16px 32px;background:#f0f0f0;font-size:11px;color:#888}}
</style>
</head>
<body><div class="wrap">
<div class="hdr">IT Helpdesk</div>
<div class="body">{content}</div>
<div class="ftr">Este é um e-mail automático do sistema de suporte interno.</div>
</div></body></html>
"""


def tpl_ticket_opened(
    ticket_number: str,
    title: str,
    requester_name: str,
    priority: str,
    category: str | None,
) -> tuple[str, str]:
    subject = f"[{ticket_number}] Novo chamado aberto"
    content = (
        f"<p>Um novo chamado foi aberto.</p>"
        f"<table style='width:100%;border-collapse:collapse'>"
        f"<tr><td style='padding:4px 0;color:#555;width:130px'><b>Chamado</b></td>"
        f"<td>{ticket_number}</td></tr>"
        f"<tr><td><b>Título</b></td><td>{title}</td></tr>"
        f"<tr><td><b>Solicitante</b></td><td>{requester_name}</td></tr>"
        f"<tr><td><b>Prioridade</b></td><td>{priority.upper()}</td></tr>"
        f"<tr><td><b>Categoria</b></td><td>{category or '—'}</td></tr>"
        f"</table>"
    )
    return subject, _BASE.format(content=content)


def tpl_ticket_message(
    ticket_number: str,
    title: str,
    author_name: str,
    message_body: str,
    base_url: str = "",
) -> tuple[str, str]:
    subject = f"[{ticket_number}] Nova mensagem no chamado"
    safe_body = message_body[:800].replace("<", "&lt;").replace(">", "&gt;")
    content = (
        f"<p>Uma nova mensagem foi adicionada ao chamado <b>{ticket_number}</b>.</p>"
        f"<p><b>Título:</b> {title}</p>"
        f"<p><b>De:</b> {author_name}</p>"
        f"<blockquote style='border-left:3px solid #2563eb;padding-left:12px;color:#555'>"
        f"{safe_body}</blockquote>"
        f"<a class='btn' href='{base_url}/tickets/{ticket_number}'>Ver chamado</a>"
    )
    return subject, _BASE.format(content=content)


def tpl_ticket_assigned(
    ticket_number: str,
    title: str,
    assignee_name: str,
) -> tuple[str, str]:
    subject = f"[{ticket_number}] Chamado atribuído a você"
    content = (
        f"<p>O chamado <b>{ticket_number}</b> foi atribuído a <b>{assignee_name}</b>.</p>"
        f"<p><b>Título:</b> {title}</p>"
    )
    return subject, _BASE.format(content=content)


def tpl_ticket_status(
    ticket_number: str,
    title: str,
    new_status: str,
) -> tuple[str, str]:
    labels = {
        "OPEN": "Em aberto",
        "IN_PROGRESS": "Em andamento",
        "WAITING_USER": "Aguardando sua resposta",
        "RESOLVED": "Resolvido",
        "CLOSED": "Encerrado",
        "REOPENED": "Reaberto",
    }
    label = labels.get(new_status, new_status)
    subject = f"[{ticket_number}] Status atualizado: {label}"
    content = (
        f"<p>O status do chamado <b>{ticket_number}</b> foi atualizado para "
        f"<b>{label}</b>.</p>"
        f"<p><b>Título:</b> {title}</p>"
    )
    return subject, _BASE.format(content=content)


def tpl_csat_request(
    ticket_number: str,
    title: str,
    csat_url: str,
) -> tuple[str, str]:
    subject = f"[{ticket_number}] Como foi o atendimento?"
    content = (
        f"<p>Seu chamado <b>{ticket_number}</b> foi encerrado. "
        f"Gostaríamos de saber como foi o atendimento.</p>"
        f"<p><b>Título:</b> {title}</p>"
        f"<p>Por favor, avalie o atendimento em até 5 estrelas:</p>"
        f"<a class='btn' href='{csat_url}'>Avaliar atendimento</a>"
        f"<p style='font-size:12px;color:#888;margin-top:16px'>"
        f"A pesquisa leva menos de 1 minuto. Sua opinião é importante!</p>"
    )
    return subject, _BASE.format(content=content)
