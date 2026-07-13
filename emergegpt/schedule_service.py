"""Durable schedule lifecycle, leases, idempotent fires, and history."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from .db import Database
from .scheduling import fire_key, next_fires
from .workflows import canonical_hash


class ScheduleService:
    def __init__(self, db: Database):
        self.db = db

    def create(self, payload: dict) -> dict:
        expression, zone = payload["expression"], payload["timezone"]
        upcoming = next_fires(expression, zone, 5)
        schedule_id, now = str(uuid.uuid4()), _now()
        workflow = _workflow(payload.get("workflow", {}))
        with self.db.connect() as connection:
            connection.execute("INSERT INTO schedules VALUES (?,?,?,?,?,?,?,?)",
                               (schedule_id, payload["name"].strip(), expression, zone,
                                json.dumps(workflow, sort_keys=True), 1, upcoming[0], now))
        return self.get(schedule_id)

    def list(self) -> list[dict]:
        with self.db.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM schedules ORDER BY created_at DESC")]
        return [self.get(item) for item in ids]

    def get(self, schedule_id: str) -> dict:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,)).fetchone()
            if not row:
                raise KeyError("schedule not found")
            fires = [dict(item) for item in connection.execute(
                "SELECT id,intended_fire_at,state,started_at,finished_at,workflow_run_id,error_summary,details_json "
                "FROM schedule_fires WHERE schedule_id=? ORDER BY intended_fire_at DESC LIMIT 25", (schedule_id,))]
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        result["workflow"] = json.loads(result.pop("workflow_json"))
        result["next_fires"] = next_fires(result["expression"], result["timezone"], 5) if result["enabled"] else []
        for item in fires:
            item["details"] = json.loads(item.pop("details_json"))
        result["fires"] = fires
        return result

    def update(self, schedule_id: str, payload: dict) -> dict:
        current = self.get(schedule_id)
        expression = payload.get("expression", current["expression"])
        zone = payload.get("timezone", current["timezone"])
        upcoming = next_fires(expression, zone, 5)
        workflow = _workflow(payload.get("workflow", current["workflow"]))
        name = payload.get("name", current["name"]).strip()
        with self.db.connect() as connection:
            connection.execute("UPDATE schedules SET name=?,expression=?,timezone=?,workflow_json=?,next_fire_at=? WHERE id=?",
                               (name, expression, zone, json.dumps(workflow, sort_keys=True), upcoming[0], schedule_id))
        return self.get(schedule_id)

    def set_enabled(self, schedule_id: str, enabled: bool) -> dict:
        current = self.get(schedule_id)
        next_fire = next_fires(current["expression"], current["timezone"], 1)[0] if enabled else None
        with self.db.connect() as connection:
            connection.execute("UPDATE schedules SET enabled=?,next_fire_at=? WHERE id=?", (int(enabled), next_fire, schedule_id))
        return self.get(schedule_id)

    def delete(self, schedule_id: str) -> None:
        self.get(schedule_id)
        with self.db.connect() as connection:
            connection.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))

    def run_now(self, schedule_id: str, dispatcher=None) -> dict:
        schedule = self.get(schedule_id)
        intended = datetime.now(timezone.utc)
        return self._fire(schedule, intended, dispatcher, manual=True)

    def fire_due(self, owner: str, dispatcher=None, now: datetime | None = None) -> list[dict]:
        current = now or datetime.now(timezone.utc)
        if not self.acquire_lease(owner, current):
            return []
        with self.db.connect() as connection:
            ids = [row[0] for row in connection.execute(
                "SELECT id FROM schedules WHERE enabled=1 AND next_fire_at IS NOT NULL AND next_fire_at<=? ORDER BY next_fire_at",
                (current.isoformat(),))]
        results = []
        for schedule_id in ids:
            schedule = self.get(schedule_id)
            intended = datetime.fromisoformat(schedule["next_fire_at"])
            policy = schedule["workflow"].get("schedule_policy", {})
            misfire = policy.get("misfire", "fire_once")
            max_concurrency = max(1, int(policy.get("max_concurrency", 1)))
            with self.db.connect() as connection:
                active = connection.execute("SELECT COUNT(*) FROM schedule_fires WHERE schedule_id=? AND state='running'",
                                            (schedule_id,)).fetchone()[0]
            if active >= max_concurrency:
                results.append(self._record_skipped(schedule, intended, "maximum concurrency reached", current))
            elif misfire == "skip" and intended < current - timedelta(minutes=1):
                results.append(self._record_skipped(schedule, intended, "misfire policy skipped late fire", current))
            else:
                results.append(self._fire(schedule, intended, dispatcher, manual=False,
                                          next_from=current if misfire == "fire_once" else intended))
        return results

    def acquire_lease(self, owner: str, now: datetime | None = None, ttl_seconds: int = 60) -> bool:
        current = now or datetime.now(timezone.utc)
        expires = current + timedelta(seconds=ttl_seconds)
        with self.db.connect() as connection:
            row = connection.execute("SELECT owner,expires_at FROM scheduler_leases WHERE name='scheduler'").fetchone()
            if row and datetime.fromisoformat(row["expires_at"]) > current and row["owner"] != owner:
                return False
            connection.execute(
                "INSERT INTO scheduler_leases VALUES ('scheduler',?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET owner=excluded.owner,acquired_at=excluded.acquired_at,expires_at=excluded.expires_at",
                (owner, current.isoformat(), expires.isoformat()))
        return True

    def _fire(self, schedule: dict, intended: datetime, dispatcher, manual: bool,
              next_from: datetime | None = None) -> dict:
        config_hash = canonical_hash(schedule["workflow"])
        key = fire_key(schedule["id"], intended, config_hash)
        fire_id, started = str(uuid.uuid4()), _now()
        with self.db.connect() as connection:
            existing = connection.execute("SELECT id FROM schedule_fires WHERE fire_key=?", (key,)).fetchone()
            if existing:
                return self._get_fire(existing["id"])
            connection.execute(
                "INSERT INTO schedule_fires VALUES (?,?,?,?,?,?,?,?,?,?)",
                (fire_id, schedule["id"], intended.isoformat(), key, "running", started, None, None, None,
                 json.dumps({"manual": manual, "workflow_config_hash": config_hash}, sort_keys=True)))
        try:
            outcome = dispatcher(schedule["workflow"], key) if dispatcher else {"status": "planned", "workflow_run_id": None}
            state = outcome.get("status", "succeeded")
            workflow_run_id = outcome.get("workflow_run_id")
            error = None
        except Exception as exc:
            state, workflow_run_id, error = "failed", None, str(exc)[-500:]
        with self.db.connect() as connection:
            connection.execute("UPDATE schedule_fires SET state=?,finished_at=?,workflow_run_id=?,error_summary=? WHERE id=?",
                               (state, _now(), workflow_run_id, error, fire_id))
            if not manual:
                following = next_fires(schedule["expression"], schedule["timezone"], 1, start=next_from or intended)[0]
                connection.execute("UPDATE schedules SET next_fire_at=? WHERE id=?", (following, schedule["id"]))
        return self._get_fire(fire_id)

    def _record_skipped(self, schedule: dict, intended: datetime, reason: str, next_from: datetime) -> dict:
        config_hash = canonical_hash(schedule["workflow"])
        key = fire_key(schedule["id"], intended, config_hash)
        fire_id, now = str(uuid.uuid4()), _now()
        with self.db.connect() as connection:
            existing = connection.execute("SELECT id FROM schedule_fires WHERE fire_key=?", (key,)).fetchone()
            if existing:
                return self._get_fire(existing["id"])
            connection.execute("INSERT INTO schedule_fires VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (fire_id, schedule["id"], intended.isoformat(), key, "skipped", now, now,
                                None, reason, json.dumps({"manual": False, "workflow_config_hash": config_hash}, sort_keys=True)))
            following = next_fires(schedule["expression"], schedule["timezone"], 1, start=next_from)[0]
            connection.execute("UPDATE schedules SET next_fire_at=? WHERE id=?", (following, schedule["id"]))
        return self._get_fire(fire_id)

    def _get_fire(self, fire_id: str) -> dict:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM schedule_fires WHERE id=?", (fire_id,)).fetchone()
        result = dict(row)
        result["details"] = json.loads(result.pop("details_json"))
        return result


def _workflow(value: dict) -> dict:
    if not isinstance(value, dict) or not value.get("action"):
        raise ValueError("schedule workflow requires an action")
    result = dict(value)
    policy = dict(result.get("schedule_policy", {}))
    if policy.get("misfire", "fire_once") not in {"fire_once", "skip", "catch_up"}:
        raise ValueError("misfire policy must be fire_once, skip, or catch_up")
    policy["misfire"] = policy.get("misfire", "fire_once")
    policy["max_concurrency"] = max(1, int(policy.get("max_concurrency", 1)))
    result["schedule_policy"] = policy
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
