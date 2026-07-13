"""Scoped one-time approvals for live mutations."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from .db import Database


def issue(db: Database, workflow_id: str, actor: str, scope: dict, config_hash: str,
          max_cost: float, ttl_seconds: int = 900) -> tuple[str, str]:
    if max_cost < 0 or ttl_seconds < 1:
        raise ValueError("invalid approval budget or TTL")
    approval_id, nonce = str(uuid.uuid4()), secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,NULL)",
            (approval_id, workflow_id, actor, json.dumps(scope, sort_keys=True), config_hash, max_cost,
             hashlib.sha256(nonce.encode()).hexdigest(), expires.isoformat()),
        )
    return approval_id, nonce


def consume(db: Database, approval_id: str, nonce: str, *, workflow_id: str, scope: dict,
            config_hash: str, estimated_cost: float) -> None:
    now = datetime.now(timezone.utc)
    nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
    with db.connect() as connection:
        row = connection.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise PermissionError("approval not found")
        checks = {
            "workflow": row["workflow_id"] == workflow_id,
            "scope": row["scope_json"] == json.dumps(scope, sort_keys=True),
            "config": row["config_hash"] == config_hash,
            "nonce": secrets.compare_digest(row["nonce_hash"], nonce_hash),
            "unused": row["consumed_at"] is None,
            "unexpired": datetime.fromisoformat(row["expires_at"]) > now,
            "budget": estimated_cost <= row["max_cost"],
        }
        if not all(checks.values()):
            raise PermissionError("approval scope, expiry, nonce, configuration, or budget mismatch")
        connection.execute("UPDATE approvals SET consumed_at=? WHERE id=? AND consumed_at IS NULL", (now.isoformat(), approval_id))
        if connection.total_changes != 1:
            raise PermissionError("approval was already consumed")
