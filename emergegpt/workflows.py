"""Idempotent workflow state machine."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from .db import Database

STATES = {
    "draft": {"preflight", "cancelled"},
    "preflight": {"awaiting_review", "blocked", "failed"},
    "awaiting_review": {"approved", "cancelled", "expired"},
    "approved": {"queued", "expired", "cancelled"},
    "queued": {"running", "cancelled", "failed"},
    "running": {"evaluating", "failed", "cancelled"},
    "evaluating": {"awaiting_promotion", "failed"},
    "awaiting_promotion": {"completed", "cancelled"},
    "blocked": set(), "failed": set(), "cancelled": set(), "expired": set(), "completed": set(),
}


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def create(db: Database, definition_id: str, config: dict, idempotency_key: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    workflow_id = str(uuid.uuid4())
    with db.connect() as connection:
        existing = connection.execute("SELECT * FROM workflow_runs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
        if existing:
            return dict(existing)
        connection.execute(
            "INSERT INTO workflow_runs VALUES (?,?,?,?,?,?,?,?)",
            (workflow_id, definition_id, "draft", canonical_hash(config), idempotency_key, now, now, json.dumps(config, sort_keys=True)),
        )
    return {"id": workflow_id, "state": "draft", "config_hash": canonical_hash(config), "idempotency_key": idempotency_key}


def transition(db: Database, workflow_id: str, target: str) -> dict:
    if target not in STATES:
        raise ValueError("unknown workflow state")
    with db.connect() as connection:
        row = connection.execute("SELECT * FROM workflow_runs WHERE id=?", (workflow_id,)).fetchone()
        if not row:
            raise KeyError("workflow not found")
        if target not in STATES[row["state"]]:
            raise ValueError(f"invalid transition {row['state']} -> {target}")
        now = datetime.now(timezone.utc).isoformat()
        connection.execute("UPDATE workflow_runs SET state=?, updated_at=? WHERE id=?", (target, now, workflow_id))
        return {"id": workflow_id, "state": target, "updated_at": now}
