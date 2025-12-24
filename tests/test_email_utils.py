from app.infra import email as email_module


def test_email_is_not_configured_returns_false(monkeypatch):
    monkeypatch.setattr(email_module.settings, "SMTP_HOST", None)
    monkeypatch.setattr(email_module.settings, "SMTP_FROM", "no-reply@example.com")
    assert email_module.is_smtp_configured() is False
    # отправка не падает, но и не отправляет
    assert email_module.send_order_confirmation("x@y.z", order_id=1) is False
