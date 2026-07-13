"""Notification contracts and deduplication fingerprints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    subject: str
    body: str
    severity: str
    alert_id: str


class NotificationAdapter:
    def validate_configuration(self) -> dict:
        raise NotImplementedError

    def send(self, notification: Notification) -> dict:
        raise NotImplementedError


def fingerprint(condition: dict) -> str:
    return hashlib.sha256(json.dumps(condition, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
