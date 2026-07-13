"""Append-only audit events."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .db import Database
from .redaction import redact


def record(db: Database, *, actor: str, action: str, resource_type: str, resource_id: str | None,
           outcome: str, details: dict, trace_id: str | None = None) -> str:
    event_id = str(uuid.uuid4())
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?)",
            (event_id, datetime.now(timezone.utc).isoformat(), actor, action, resource_type, resource_id,
             outcome, trace_id, json.dumps(redact(details), sort_keys=True)),
        )
    return event_id
