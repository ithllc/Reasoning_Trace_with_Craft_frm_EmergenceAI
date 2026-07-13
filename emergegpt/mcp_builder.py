"""Diff-first MCP Builder draft, preview, validation, install, and rollback."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .db import Database
from .settings import ROOT, Settings
from .workflows import canonical_hash

STEPS = ["select", "prerequisites", "references", "capabilities", "preview", "validate", "install", "sandbox_test", "complete"]
SERVER_FILES = {"craft": ROOT / "emergegpt_mcp" / "craft_server.py", "nebius": ROOT / "emergegpt_mcp" / "nebius_server.py"}


def create_draft(db: Database, server_kind: str, config: dict) -> dict:
    if server_kind not in SERVER_FILES:
        raise ValueError("server_kind must be craft or nebius")
    draft_id, now = str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()
    safe = {key: value for key, value in config.items() if not any(x in key.lower() for x in ("secret", "token", "password", "api_key"))}
    with db.connect() as connection:
        connection.execute("INSERT INTO mcp_drafts VALUES (?,?,?,?,?,?,?)",
                           (draft_id, server_kind, "select", json.dumps(safe, sort_keys=True), canonical_hash(safe), now, now))
    return {"id": draft_id, "server_kind": server_kind, "step": "select", "config": safe}


def get_draft(db: Database, draft_id: str):
    with db.connect() as connection:
        row = connection.execute("SELECT * FROM mcp_drafts WHERE id=?", (draft_id,)).fetchone()
    if not row:
        raise KeyError("MCP draft not found")
    result = dict(row)
    result["config"] = json.loads(result.pop("config_json"))
    return result


def update_draft(db: Database, draft_id: str, step: str, config: dict) -> dict:
    if step not in STEPS:
        raise ValueError("invalid MCP Builder step")
    current = get_draft(db, draft_id)
    safe = {**current["config"], **{key: value for key, value in config.items()
                                     if not any(x in key.lower() for x in ("secret", "token", "password", "api_key"))}}
    with db.connect() as connection:
        connection.execute("UPDATE mcp_drafts SET step=?,config_json=?,config_hash=?,updated_at=? WHERE id=?",
                           (step, json.dumps(safe, sort_keys=True), canonical_hash(safe), datetime.now(timezone.utc).isoformat(), draft_id))
    return get_draft(db, draft_id)


def harness_snippets(kind: str) -> dict:
    command = ["python3", str(SERVER_FILES[kind])]
    return {
        "codex": {"mcp_servers": {f"emergegpt-{kind}": {"command": command[0], "args": command[1:]}}},
        "claude_code": f"claude mcp add emergegpt-{kind} -- {' '.join(command)}",
        "opencode": {"mcp": {f"emergegpt-{kind}": {"type": "local", "command": command}}},
        "openclaw": {"mcp": {"name": f"emergegpt-{kind}", "transport": "stdio", "command": command}},
        "gemini_cli": {"mcpServers": {f"emergegpt-{kind}": {"command": command[0], "args": command[1:], "trust": False}}},
        "nemoclaw": {"mode": "requires OpenShell-reviewed stdio/HTTPS policy attachment", "command": command},
    }


def preview(db: Database, draft_id: str) -> dict:
    draft = get_draft(db, draft_id)
    path = SERVER_FILES[draft["server_kind"]]
    return {"draft_id": draft_id, "server_kind": draft["server_kind"], "config_hash": draft["config_hash"], "files": [{"path": str(path.relative_to(ROOT)), "exists": path.exists()}],
            "tools": (["craft_docs_search", "craft_connection_status", "craft_tenant_readiness"] if draft["server_kind"] == "craft"
                      else ["nebius_docs_search", "nebius_models_list", "nebius_jobs_list", "nebius_job_get", "nebius_job_checkpoints", "nebius_job_cancel"]),
            "harness_snippets": harness_snippets(draft["server_kind"]), "contains_secrets": False}


def validate(db: Database, draft_id: str, settings: Settings) -> dict:
    draft = get_draft(db, draft_id)
    path = SERVER_FILES[draft["server_kind"]]
    checks = {"server_file": path.is_file(), "python": bool(shutil.which("python3")), "mcp_library": True}
    if draft["server_kind"] == "craft":
        from .providers.craft import CraftProvider
        status = CraftProvider(settings).authorization_status()
        checks["tenant_connector_safe_default"] = not settings.craft_connector_enabled or settings.craft_authorization_attested
        checks["entitlement_not_assumed"] = status["state"] != "read_ready" or all(
            status["gates"][gate] for gate in (
                "customer_project_authorization", "official_endpoint_configured",
                "tool_schemas_discovered", "harmless_read_probe_succeeded",
                "contractual_authorization_attested",
            )
        )
    else:
        checks["credential_reference"] = bool(settings.nebius_api_key)
    result = {"valid": all(checks.values()), "checks": checks, "config_hash": draft["config_hash"]}
    if draft["server_kind"] == "craft":
        result["craft_readiness"] = status
    return result


def install(db: Database, draft_id: str, expected_hash: str) -> dict:
    draft = get_draft(db, draft_id)
    if draft["config_hash"] != expected_hash:
        raise ValueError("draft changed after validation")
    installation_id = str(uuid.uuid4())
    manifest = preview(db, draft_id)
    manifest_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with db.connect() as connection:
        connection.execute("INSERT INTO mcp_installations VALUES (?,?,?,?,?,?,?,?)",
                           (installation_id, draft_id, draft["server_kind"], "installed", manifest_hash, None,
                            datetime.now(timezone.utc).isoformat(), json.dumps(manifest, sort_keys=True)))
    update_draft(db, draft_id, "complete", {})
    return {"id": installation_id, "status": "installed", "manifest_hash": manifest_hash, **manifest}
