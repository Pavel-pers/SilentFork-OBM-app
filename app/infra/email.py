import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.core.settings import settings

log = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10


def smtp_enabled() -> bool:
    return bool(settings.SMTP_HOST)


def _build_message(to_email: str, subject: str, text: str, html: Optional[str] = None) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send_email(to_email: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    """
    Отправляет email через SMTP.
    - Если SMTP не настроен, ничего не отправляет (только логирует) и возвращает False.
    - Ошибки SMTP не пробрасываются наружу, чтобы не ломать пользовательские сценарии.
    """
    if not smtp_enabled():
        log.info("SMTP не настроен, пропуск отправки письма: to=%s subject=%s", to_email, subject)
        return False

    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    msg = _build_message(to_email, subject, text, html=html)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(
                    host,
                    port,
                    timeout=SMTP_TIMEOUT_SECONDS,
                    context=ssl.create_default_context()
            ) as s:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                s.send_message(msg)
            return True

        with smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT_SECONDS) as s:
            s.ehlo()
            s.starttls(context=ssl.create_default_context())
            s.ehlo()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:
        log.exception("Ошибка отправки письма: to=%s subject=%s", to_email, subject)
        return False


def send_order_confirmation(
        to_email: str,
        order_id: int,
        total_price: str | None = None,
        address: str | None = None
) -> bool:
    subject = f"Подтверждение заказа №{order_id}"
    lines = [
        "Спасибо за заказ в СтройМаг!",
        f"Номер заказа: {order_id}",
    ]
    if total_price:
        lines.append(f"Сумма: {total_price} руб.")
    if address:
        lines.append(f"Адрес доставки: {address}")
    lines.append("")
    lines.append("Если вы не оформляли заказ, просто проигнорируйте это письмо.")
    return send_email(to_email, subject, "\n".join(lines))


def send_staff_new_order_notification(to_email: str, order_id: int) -> bool:
    subject = f"Новый заказ №{order_id}"
    text = (
        f"Поступил новый заказ №{order_id}.\n"
        "Откройте панель/админку для обработки."
    )
    return send_email(to_email, subject, text)


def send_password_changed_notification(to_email: str) -> bool:
    subject = "Пароль изменен"
    text = (
        "Ваш пароль был изменен.\n\n"
        "Если это были не вы, пожалуйста, срочно смените пароль и обратитесь в поддержку."
    )
    return send_email(to_email, subject, text)
