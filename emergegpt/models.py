"""Exact-ID model registry and capability decisions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .db import Database


def register(db: Database, *, provider: str, provider_model_id: str, license_name: str | None,
             open_weights: bool, roles: list[str], metadata: dict) -> dict:
    model_id = str(uuid.uuid4())
    with db.connect() as connection:
        connection.execute("INSERT INTO models VALUES (?,?,?,?,?,?,?)",
                           (model_id, provider, provider_model_id, license_name, int(open_weights),
                            json.dumps(sorted(set(roles))), json.dumps(metadata, sort_keys=True)))
    return {"id": model_id, "provider": provider, "provider_model_id": provider_model_id}


def record_capabilities(db: Database, model_id: str, *, inference: bool, lora: bool, full: bool,
                        deploy: bool, evidence: dict) -> dict:
    observed = datetime.now(timezone.utc).isoformat()
    with db.connect() as connection:
        connection.execute("INSERT INTO model_capabilities VALUES (?,?,?,?,?,?,?)",
                           (model_id, observed, int(inference), int(lora), int(full), int(deploy), json.dumps(evidence, sort_keys=True)))
    return {"model_id": model_id, "observed_at": observed, "inference": inference, "lora": lora, "full": full, "deploy": deploy}


def eligible_training_mode(capability: dict, requested_mode: str) -> bool:
    if requested_mode not in {"lora", "full"}:
        raise ValueError("training mode must be lora or full")
    return bool(capability.get(requested_mode))
