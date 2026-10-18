import smtplib
from email.message import EmailMessage

import requests

from jarvis.config import setting


def email_configured():
    return all(setting(name) for name in ("SMTP_USER", "SMTP_PASSWORD", "ALERT_EMAIL_TO"))


def push_configured():
    return bool(setting("NTFY_TOPIC"))


def channels():
    return [name for name, ready in (("email", email_configured()), ("phone", push_configured())) if ready]


def send_email(subject, body, smtp_factory=smtplib.SMTP_SSL):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = setting("SMTP_USER")
    message["To"] = setting("ALERT_EMAIL_TO")
    message.set_content(body)
    with smtp_factory(setting("SMTP_HOST", "smtp.gmail.com"), int(setting("SMTP_PORT", "465"))) as server:
        server.login(setting("SMTP_USER"), setting("SMTP_PASSWORD"))
        server.send_message(message)


def send_push(title, body, priority="default", post=requests.post):
    response = post(
        f"{setting('NTFY_SERVER', 'https://ntfy.sh').rstrip('/')}/{setting('NTFY_TOPIC')}",
        data=body.encode("utf-8"),
        headers={"Title": title.encode("ascii", "ignore").decode(), "Priority": priority, "Tags": "robot"},
        timeout=20,
    )
    response.raise_for_status()


def notify(title, body, urgent=False):
    sent, errors = [], []
    if email_configured():
        try:
            send_email(title, body)
            sent.append("email")
        except Exception as error:
            errors.append(f"email: {error}")
    if push_configured():
        try:
            send_push(title, body, "high" if urgent else "default")
            sent.append("phone")
        except Exception as error:
            errors.append(f"phone: {error}")
    return sent, errors
