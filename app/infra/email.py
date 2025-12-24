import logging
import smtplib
from email.message import EmailMessage

from app.core.settings import settings

log = logging.getLogger(__name__)


def is_smtp_configured() -> bool:
    """Упрощенная проверка настройки SMTP."""
    return bool(settings.SMTP_HOST and settings.SMTP_FROM)


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Отправляет письмо через SMTP. Возвращает True, если письмо поставлено в отправку.
    Не бросает исключений наружу, чтобы основной сценарий не падал из-за SMTP.
    """
    if not is_smtp_configured():
        log.info("SMTP не настроен, письмо не отправлено: to_email=%s subject=%s", to_email, subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        log.info("SMTP: письмо отправлено to=%s subject=%s", to_email, subject)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("SMTP: не удалось отправить письмо: %s", exc, exc_info=True)
        return False


def send_order_confirmation(to_email: str, order_id: int, address: str | None = None, phone: str | None = None) -> bool:
    """Отправка письма о создании заказа."""
    lines = [
        f"Спасибо за заказ! Номер заказа: {order_id}",
    ]
    if address:
        lines.append(f"Адрес доставки: {address}")
    if phone:
        lines.append(f"Контактный телефон: {phone}")
    body = "\n".join(lines)
    return send_email(to_email=to_email, subject=f"Подтверждение заказа №{order_id}", body=body)


__all__ = ["send_email", "send_order_confirmation", "is_smtp_configured"]
