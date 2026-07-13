"""Deterministic intent/policy contracts around non-deterministic harness advice."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def intent_contract(payload: dict) -> dict:
    required = ("actor", "objective", "operation_classes", "budgets", "approval_policy")
    missing = [field for field in required if field not in payload]
    if missing: raise ValueError("intent missing: " + ", ".join(missing))
    result = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), **payload}
    result["intent_hash"] = canonical_hash(result)
    return result


def harness_suggestion(intent: dict, proposal: dict) -> dict:
    required = ("recommendations", "confidence", "rationale", "evidence_citations", "assumptions")
    missing = [field for field in required if field not in proposal]
    if missing: raise ValueError("harness suggestion missing: " + ", ".join(missing))
    if not 0 <= float(proposal["confidence"]) <= 1: raise ValueError("confidence must be between zero and one")
    return {"schema_version": 1, "intent_hash": intent["intent_hash"], **proposal,
            "suggestion_hash": canonical_hash({"intent_hash": intent["intent_hash"], **proposal})}


def policy_decision(intent: dict, suggestion: dict, allowed_operations: set[str]) -> dict:
    requested = set(intent["operation_classes"])
    allowed = not (requested - allowed_operations)
    return {"schema_version": 1, "intent_hash": intent["intent_hash"],
            "suggestion_hash": suggestion["suggestion_hash"],
            "decision": "approval_required" if allowed else "denied",
            "matched_rules": ["operation_allowlist", "immutable_intent", "explicit_approval"],
            "denied_operations": sorted(requested - allowed_operations)}


def accept_suggestion(intent: dict, suggestion: dict, accepted_recommendations: list[dict]) -> dict:
    # Acceptance creates a new deterministic intent; it never mutates the old one.
    payload = {key: value for key, value in intent.items() if key not in {"intent_hash", "created_at", "schema_version"}}
    payload["accepted_harness_suggestion"] = suggestion["suggestion_hash"]
    payload["accepted_recommendations"] = accepted_recommendations
    return intent_contract(payload)
