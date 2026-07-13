"""Fail-closed scope manifest for EmergeGPT-only harness activity."""

from __future__ import annotations

import fnmatch
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def canonical_payload(manifest: dict) -> bytes:
    payload = {key: value for key, value in manifest.items() if key not in {"signature", "manifest_hash"}}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_manifest(manifest: dict, signing_key: str) -> dict:
    if len(signing_key) < 32:
        raise ValueError("scope signing key must contain at least 32 characters")
    result = dict(manifest)
    payload = canonical_payload(result)
    result["manifest_hash"] = hashlib.sha256(payload).hexdigest()
    result["signature"] = hmac.new(signing_key.encode(), payload, hashlib.sha256).hexdigest()
    return result


def verify_manifest(manifest: dict, signing_key: str, now: datetime | None = None) -> None:
    payload = canonical_payload(manifest)
    expected_hash = hashlib.sha256(payload).hexdigest()
    expected_signature = hmac.new(signing_key.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(str(manifest.get("manifest_hash", "")), expected_hash):
        raise PermissionError("product scope manifest hash mismatch")
    if not hmac.compare_digest(str(manifest.get("signature", "")), expected_signature):
        raise PermissionError("product scope manifest signature mismatch")
    expiry = datetime.fromisoformat(str(manifest["expires_at"]).replace("Z", "+00:00"))
    if expiry <= (now or datetime.now(timezone.utc)):
        raise PermissionError("product scope manifest expired")
    if manifest.get("product_id") != "emergegpt":
        raise PermissionError("scope manifest is not for EmergeGPT")


def authorize_run(
    manifest: dict,
    signing_key: str,
    *,
    repository: Path,
    changed_paths: Iterable[Path],
    requirement_id: str,
    operation_class: str,
    mcp_tools: Iterable[str] = (),
    network_destinations: Iterable[str] = (),
) -> dict:
    verify_manifest(manifest, signing_key)
    root = repository.resolve(strict=True)
    allowed_repositories = {str(Path(path).resolve(strict=True)) for path in manifest.get("repositories", [])}
    if str(root) not in allowed_repositories:
        raise PermissionError("repository is outside the EmergeGPT product scope")
    if requirement_id not in manifest.get("requirement_ids", []):
        raise PermissionError("requirement is outside the EmergeGPT product scope")
    if operation_class not in manifest.get("operation_classes", []):
        raise PermissionError("operation class is outside the EmergeGPT product scope")
    patterns = manifest.get("path_allowlist", [])
    normalized_paths = []
    for candidate in changed_paths:
        resolved = (root / candidate).resolve(strict=False)
        if root != resolved and root not in resolved.parents:
            raise PermissionError("changed path escapes the scoped repository")
        relative = resolved.relative_to(root).as_posix()
        if not any(fnmatch.fnmatch(relative, pattern) for pattern in patterns):
            raise PermissionError(f"changed path is outside product scope: {relative}")
        normalized_paths.append(relative)
    _require_subset("MCP tool", mcp_tools, manifest.get("mcp_tools", []))
    _require_subset("network destination", network_destinations, manifest.get("network_allowlist", []))
    return {"authorized": True, "manifest_hash": manifest["manifest_hash"], "paths": normalized_paths}


def _require_subset(label: str, requested: Iterable[str], allowed: Iterable[str]) -> None:
    extras = sorted(set(requested) - set(allowed))
    if extras:
        raise PermissionError(f"{label} outside product scope: {', '.join(extras)}")
