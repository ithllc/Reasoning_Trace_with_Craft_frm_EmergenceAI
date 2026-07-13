"""Email, Slack, and Telegram notification adapters."""

from __future__ import annotations

import json
import os
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

from .notifications import Notification, NotificationAdapter


class EmailAdapter(NotificationAdapter):
    def __init__(self, config: dict): self.config = config
    def validate_configuration(self):
        required = ["EMERGEGPT_SMTP_HOST", "EMERGEGPT_EMAIL_FROM"]
        missing = [name for name in required if not os.getenv(name)]
        if not self.config.get("recipient"): missing.append("profile.recipient")
        return {"configured": not missing, "missing": missing}
    def send(self, notification: Notification):
        status = self.validate_configuration()
        if not status["configured"]: raise RuntimeError("email adapter is not configured")
        message = EmailMessage(); message["Subject"] = notification.subject
        message["From"] = os.environ["EMERGEGPT_EMAIL_FROM"]; message["To"] = self.config["recipient"]
        message.set_content(notification.body)
        with smtplib.SMTP(os.environ["EMERGEGPT_SMTP_HOST"], int(os.getenv("EMERGEGPT_SMTP_PORT", "587")), timeout=20) as client:
            client.starttls()
            if os.getenv("EMERGEGPT_SMTP_USER"):
                client.login(os.environ["EMERGEGPT_SMTP_USER"], os.environ["EMERGEGPT_SMTP_PASSWORD"])
            client.send_message(message)
        return {"status": "sent", "channel": "email"}


class SlackAdapter(NotificationAdapter):
    def __init__(self, config: dict): self.config = config
    def _url(self): return os.getenv(self.config.get("webhook_env", ""), "")
    def validate_configuration(self): return {"configured": bool(self._url())}
    def send(self, notification):
        if not self.validate_configuration()["configured"]: raise RuntimeError("Slack adapter is not configured")
        request = urllib.request.Request(self._url(), data=json.dumps({"text": f"*{notification.subject}*\n{notification.body}"}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response: response.read()
        return {"status": "sent", "channel": "slack"}


class TelegramAdapter(NotificationAdapter):
    def __init__(self, config: dict): self.config = config
    def validate_configuration(self):
        missing = []
        if not os.getenv(self.config.get("token_env", "")): missing.append("profile.token_env")
        if not self.config.get("chat_id"): missing.append("profile.chat_id")
        return {"configured": not missing, "missing": missing}
    def send(self, notification):
        if not self.validate_configuration()["configured"]: raise RuntimeError("Telegram adapter is not configured")
        token = os.environ[self.config["token_env"]]
        body = urllib.parse.urlencode({"chat_id": self.config["chat_id"],
                                      "text": f"{notification.subject}\n{notification.body}"}).encode()
        request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response: response.read()
        return {"status": "sent", "channel": "telegram"}
