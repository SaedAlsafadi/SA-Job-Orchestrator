"""Generic application-email provider (Phase 19).

A minimal ``EmailProvider`` interface with two implementations reusing the existing
``settings.email`` configuration (``provider=log`` for dev/CI, ``provider=smtp`` for real
delivery). No credentials are hardcoded — everything comes from settings.

``SendResult.status == "sent"`` means the provider ACCEPTED the message (relay
acceptance). Delivery is never claimed without delivery evidence.
"""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from dataclasses import dataclass, field
from email.message import EmailMessage

import structlog

from app.config.settings import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class OutgoingEmail:
    """The exact email to send — persisted BEFORE the provider is called."""

    to: str
    subject: str
    body: str
    attachments: list[tuple[str, bytes, str]] = field(default_factory=list)
    sender: str | None = None


@dataclass
class SendResult:
    """Provider response. ``status`` is "sent" (accepted) or "failed"."""

    status: str
    message_id: str | None = None
    provider_response: str | None = None
    error: str | None = None


class EmailProvider:
    """Minimal provider interface for application emails."""

    async def send(self, message: OutgoingEmail) -> SendResult:  # pragma: no cover
        raise NotImplementedError


class LogEmailProvider(EmailProvider):
    """Dev/CI provider: logs the email and reports it as accepted (simulated).

    The result is clearly marked ``log provider (simulated acceptance)`` so a send
    record produced in dev is never mistaken for real delivery evidence.
    """

    async def send(self, message: OutgoingEmail) -> SendResult:
        logger.info(
            "application_email_simulated",
            to=message.to,
            subject=message.subject,
            attachments=[a[0] for a in message.attachments],
            body_preview=message.body[:200],
        )
        return SendResult(
            status="sent",
            message_id=f"sim-{uuid.uuid4().hex}@autoapply.local",
            provider_response="log provider (simulated acceptance)",
        )


class SMTPEmailProvider(EmailProvider):
    """Real delivery via any SMTP relay (settings.email). Runs in a worker thread."""

    async def send(self, message: OutgoingEmail) -> SendResult:
        try:
            return await asyncio.to_thread(self._send_sync, message)
        except (
            Exception
        ) as exc:  # provider boundary: report, never raise past this line
            logger.error("application_email_send_failed", error=str(exc))
            return SendResult(status="failed", error=str(exc))

    def _send_sync(self, message: OutgoingEmail) -> SendResult:
        cfg = get_settings().email
        msg = EmailMessage()
        msg["From"] = message.sender or f"{cfg.from_name} <{cfg.from_address}>"
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg.set_content(message.body)
        for filename, data, content_type in message.attachments:
            maintype, _, subtype = content_type.partition("/")
            msg.add_attachment(
                data,
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=filename,
            )

        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
            if cfg.smtp_starttls:
                server.starttls()
            if cfg.smtp_username:
                server.login(cfg.smtp_username, cfg.smtp_password.get_secret_value())
            refused = server.send_message(msg)

        # send_message returns a dict of refused recipients (empty = all accepted).
        if refused:
            return SendResult(
                status="failed",
                provider_response=f"recipients refused: {refused}",
                error="recipient refused by relay",
            )
        message_id = msg.get("Message-ID")
        return SendResult(
            status="sent",
            message_id=message_id.strip() if message_id else None,
            provider_response="accepted by SMTP relay",
        )


def get_email_provider() -> EmailProvider:
    """Resolve the configured provider from settings (no credentials hardcoded)."""
    cfg = get_settings().email
    return SMTPEmailProvider() if cfg.provider == "smtp" else LogEmailProvider()
