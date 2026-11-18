"""SMTP transport with bounded timeout and intentionally non-sensitive errors."""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from uuid import UUID

from app.core.recovery_config import RecoverySettings


class RecoveryDeliveryError(Exception):
    """Never include SMTP response text, addresses, credentials or the link."""


def _send(settings: RecoverySettings, recipient: str, token: str, job_id: UUID) -> None:
    url = f"{settings.public_url.rstrip('/')}/restablecer-contrasena#token={token}"
    message = EmailMessage()
    message["Subject"] = "WABOGADOS · Recuperar su contraseña"
    message["From"] = f"WABOGADOS <{settings.mail_from}>"
    message["To"] = recipient
    domain = settings.mail_from.rsplit("@", 1)[-1]
    message["Message-ID"] = f"<recovery-{job_id}@{domain}>"
    message.set_content(
        f"Para elegir una nueva contraseña, abra este enlace:\n{url}\n\n"
        f"El enlace es de un solo uso y caduca a los {settings.ttl_minutes} minutos "
        "de solicitarlo. Si no solicitó este cambio, ignore este correo. "
        "WABOGADOS nunca le pedirá su contraseña por correo."
    )
    message.add_alternative(
        "<h1>Recuperar su acceso a WABOGADOS</h1>"
        f'<p><a href="{escape(url, quote=True)}">Elegir una nueva contraseña</a></p>'
        f"<p>Un solo uso; caduca a los {settings.ttl_minutes} minutos de solicitarlo.</p>"
        "<p>Si no solicitó el cambio, ignore este correo. Nunca le pediremos su contraseña.</p>",
        subtype="html",
    )
    try:
        if settings.smtp_security == "tls":
            connection: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
        else:
            connection = smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
            )
        with connection:
            if settings.smtp_security == "starttls":
                connection.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                connection.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            connection.send_message(message)
    except Exception:
        raise RecoveryDeliveryError("smtp_delivery_failed") from None


async def send_recovery_mail(
    settings: RecoverySettings, recipient: str, token: str, job_id: UUID
) -> None:
    await asyncio.to_thread(_send, settings, recipient, token, job_id)
