"""CRAFT connector gate. Tenant operations require separate written authorization."""

from __future__ import annotations

from datetime import datetime, timezone

from ..redaction import stable_scope_hash
from ..settings import Settings


class CraftProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def authorization_status(self) -> dict:
        expiry = None
        valid_expiry = False
        if self.settings.craft_authorization_expires_at:
            try:
                expiry = datetime.fromisoformat(self.settings.craft_authorization_expires_at.replace("Z", "+00:00"))
                valid_expiry = expiry > datetime.now(timezone.utc)
            except ValueError:
                pass
        base_authorized = self.settings.craft_connector_enabled and self.settings.craft_authorization_attested and valid_expiry
        schema_discovered = bool(self.settings.craft_tool_schema_hash)
        probe_recorded = self.settings.craft_read_probe_succeeded and bool(self.settings.craft_read_probe_at)
        read_ready = base_authorized and bool(self.settings.craft_tenant_mcp_url) and bool(self.settings.craft_project_id) and schema_discovered and probe_recorded
        gates = {
            "customer_project_authorization": base_authorized and bool(self.settings.craft_project_id),
            "official_endpoint_configured": bool(self.settings.craft_tenant_mcp_url),
            "tool_schemas_discovered": schema_discovered,
            "harmless_read_probe_succeeded": probe_recorded,
            "contractual_authorization_attested": self.settings.craft_authorization_attested and valid_expiry,
            "mutations_separately_approved": False,
        }
        state = "read_ready" if read_ready else ("authorization_pending" if self.settings.craft_connector_enabled else "documentation_only")
        return {"enabled": read_ready, "authorization_attested": self.settings.craft_authorization_attested,
                "authorization_current": valid_expiry, "project_scope_hash": stable_scope_hash(self.settings.craft_project_id),
                "tenant_endpoint_configured": bool(self.settings.craft_tenant_mcp_url), "state": state,
                "read_ready": read_ready, "gates": gates, "schema_hash_configured": schema_discovered,
                "read_probe_at": self.settings.craft_read_probe_at or None,
                "notice": "MCP Builder cannot create a CRAFT entitlement; mutation approval is always separate."}

    def require_authorized(self) -> None:
        if not self.authorization_status()["read_ready"]:
            raise PermissionError("CRAFT tenant reads are blocked until customer authorization, official endpoint, schema discovery, contractual authorization, and a harmless read probe all pass")

    def connection_status(self) -> dict:
        return {"public_documentation": {"configured": True, "url": self.settings.craft_docs_mcp_url},
                "tenant": self.authorization_status()}
