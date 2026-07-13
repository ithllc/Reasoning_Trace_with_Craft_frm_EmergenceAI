"""User notification profiles, topic subscriptions, severity policy, and delivery."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from .db import Database
from .notifications import Notification, fingerprint

SEVERITIES = {"info": 0, "warning": 1, "critical": 2}
TOPIC_FLOORS = {
    "pipeline.started": "info", "pipeline.completed": "info", "pipeline.failed": "warning",
    "pipeline.timed_out": "warning", "approval.required": "warning",
    "schedule.misfire": "warning", "schedule.failed": "warning",
    "evaluation.regression": "warning", "model.degraded": "warning",
    "fine_tuning.recommended": "info", "budget.warning": "warning", "budget.exceeded": "critical",
    "provider.outage": "warning", "model.deprecated": "warning",
    "craft.authorization_failed": "warning", "security.violation": "critical",
}


class NotificationService:
    def __init__(self, db: Database, adapters: dict | None = None):
        self.db, self.adapters = db, adapters or {}

    def create_profile(self, payload: dict) -> dict:
        channel = payload["channel"]
        if channel not in {"email", "slack", "telegram"}:
            raise ValueError("notification channel must be email, slack, or telegram")
        config = _safe_config(channel, payload.get("config", {}))
        profile_id, now = str(uuid.uuid4()), _now()
        with self.db.connect() as connection:
            connection.execute("INSERT INTO notification_profiles VALUES (?,?,?,?,?,?,?)",
                               (profile_id, payload["name"].strip(), channel, json.dumps(config, sort_keys=True), 1, now, now))
        return self.get_profile(profile_id)

    def get_profile(self, profile_id: str) -> dict:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM notification_profiles WHERE id=?", (profile_id,)).fetchone()
            if not row: raise KeyError("notification profile not found")
            subscriptions = [dict(item) for item in connection.execute(
                "SELECT id,topic,minimum_severity,enabled,created_at FROM notification_subscriptions WHERE profile_id=? ORDER BY topic",
                (profile_id,))]
        result = dict(row); result["enabled"] = bool(result["enabled"])
        result["config"] = json.loads(result.pop("config_json")); result["subscriptions"] = subscriptions
        return result

    def list_profiles(self) -> list[dict]:
        with self.db.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM notification_profiles ORDER BY created_at DESC")]
        return [self.get_profile(item) for item in ids]

    def set_enabled(self, profile_id: str, enabled: bool) -> dict:
        self.get_profile(profile_id)
        with self.db.connect() as connection:
            connection.execute("UPDATE notification_profiles SET enabled=?,updated_at=? WHERE id=?",
                               (int(enabled), _now(), profile_id))
        return self.get_profile(profile_id)

    def delete_profile(self, profile_id: str) -> None:
        self.get_profile(profile_id)
        with self.db.connect() as connection:
            connection.execute("DELETE FROM notification_profiles WHERE id=?", (profile_id,))

    def subscribe(self, profile_id: str, topic: str, minimum_severity: str = "info") -> dict:
        self.get_profile(profile_id)
        if topic not in TOPIC_FLOORS: raise ValueError("unknown notification topic")
        if minimum_severity not in SEVERITIES: raise ValueError("invalid minimum severity")
        subscription_id, now = str(uuid.uuid4()), _now()
        with self.db.connect() as connection:
            connection.execute(
                "INSERT INTO notification_subscriptions VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(profile_id,topic) DO UPDATE SET minimum_severity=excluded.minimum_severity,enabled=1",
                (subscription_id, profile_id, topic, minimum_severity, 1, now))
        return {"id": subscription_id, "profile_id": profile_id, "topic": topic,
                "minimum_severity": minimum_severity, "enabled": True}

    def unsubscribe(self, profile_id: str, topic: str) -> None:
        with self.db.connect() as connection:
            connection.execute("DELETE FROM notification_subscriptions WHERE profile_id=? AND topic=?", (profile_id, topic))

    def list_alerts(self, limit: int = 50) -> list[dict]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM alerts ORDER BY updated_at DESC LIMIT ?", (max(1, min(limit, 200)),)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    def set_alert_state(self, alert_id: str, state: str) -> dict:
        if state not in {"open", "acknowledged", "resolved"}:
            raise ValueError("alert state must be open, acknowledged, or resolved")
        with self.db.connect() as connection:
            found = connection.execute("SELECT id FROM alerts WHERE id=?", (alert_id,)).fetchone()
            if not found:
                raise KeyError("alert not found")
            connection.execute("UPDATE alerts SET state=?,updated_at=? WHERE id=?", (state, _now(), alert_id))
        return next(item for item in self.list_alerts(200) if item["id"] == alert_id)

    def publish(self, event: dict, harness_assessment: dict | None = None) -> dict:
        topic = event["topic"]
        if topic not in TOPIC_FLOORS: raise ValueError("unknown notification topic")
        requested = event.get("severity", "info")
        if requested not in SEVERITIES: raise ValueError("invalid event severity")
        severity = _max_severity(TOPIC_FLOORS[topic], requested)
        if harness_assessment:
            proposed = harness_assessment.get("severity", severity)
            if proposed not in SEVERITIES: raise ValueError("invalid harness severity")
            severity = _max_severity(severity, proposed)
        condition = {"topic": topic, "resource_id": event.get("resource_id"),
                     "occurrence_key": event.get("occurrence_key")}
        alert_id, now, fp = str(uuid.uuid4()), _now(), fingerprint(condition)
        with self.db.connect() as connection:
            existing = connection.execute("SELECT id FROM alerts WHERE fingerprint=?", (fp,)).fetchone()
            if existing:
                return {"alert_id": existing["id"], "deduplicated": True, "deliveries": []}
            details = {**event, "severity": severity, "harness_assessment": harness_assessment}
            connection.execute("INSERT INTO alerts VALUES (?,?,?,?,?,?,?)",
                               (alert_id, fp, severity, "open", now, now, json.dumps(details, sort_keys=True)))
            rows = [dict(row) for row in connection.execute(
                "SELECT s.*,p.channel,p.config_json FROM notification_subscriptions s "
                "JOIN notification_profiles p ON p.id=s.profile_id "
                "WHERE s.topic=? AND s.enabled=1 AND p.enabled=1", (topic,))]
        deliveries = []
        for row in rows:
            if SEVERITIES[severity] < SEVERITIES[row["minimum_severity"]]: continue
            deliveries.append(self._deliver(alert_id, row, event, severity, harness_assessment))
        return {"alert_id": alert_id, "deduplicated": False, "severity": severity, "deliveries": deliveries}

    def _deliver(self, alert_id: str, row: dict, event: dict, severity: str, assessment: dict | None) -> dict:
        adapter_factory = self.adapters.get(row["channel"])
        if not adapter_factory:
            return self._record_delivery(alert_id, row["channel"], 1, "not_configured", "adapter_missing")
        adapter = adapter_factory(json.loads(row["config_json"]))
        context = assessment.get("rationale") if assessment else None
        body = event.get("message", event["topic"]) + (f"\nHarness context: {context}" if context else "")
        notification = Notification(event.get("subject", event["topic"]), body, severity, alert_id)
        last = None
        for attempt in range(1, 4):
            try:
                result = adapter.send(notification)
                return self._record_delivery(alert_id, row["channel"], attempt, "sent", result.get("status"))
            except Exception as exc:
                last = type(exc).__name__
                self._record_delivery(alert_id, row["channel"], attempt, "retrying" if attempt < 3 else "failed", last)
        return {"status": "failed", "channel": row["channel"], "attempts": 3, "response_class": last}

    def _record_delivery(self, alert_id: str, channel: str, attempt: int, status: str, response_class: str | None) -> dict:
        delivery_id = str(uuid.uuid4())
        with self.db.connect() as connection:
            connection.execute("INSERT INTO notification_deliveries VALUES (?,?,?,?,?,?,?)",
                               (delivery_id, alert_id, channel, attempt, status, _now(), response_class))
        return {"id": delivery_id, "status": status, "channel": channel, "attempt": attempt,
                "response_class": response_class}


def _safe_config(channel: str, config: dict) -> dict:
    allowed = {"email": {"recipient"}, "slack": {"webhook_env"}, "telegram": {"chat_id", "token_env"}}[channel]
    unknown = set(config) - allowed
    if unknown: raise ValueError("notification profile contains unsupported or secret fields")
    result = {key: str(value).strip() for key, value in config.items() if str(value).strip()}
    if not result: raise ValueError("notification profile requires channel configuration")
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_]*", value) for key, value in result.items() if key.endswith("_env")):
        raise ValueError("secret references must be environment variable names, not values")
    return result


def _max_severity(one: str, two: str) -> str:
    return one if SEVERITIES[one] >= SEVERITIES[two] else two


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
