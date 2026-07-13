"""Typed environment configuration with safe public projections."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true or false")
    return value in {"true", "1", "yes"}


def _url(name: str, default: str = "", *, required: bool = False) -> str:
    value = os.getenv(name, default).strip().rstrip("/")
    if not value and not required:
        return ""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{name} must be an HTTP(S) URL")
    return value


@dataclass(frozen=True)
class Settings:
    environment: str
    database_path: Path
    bind_host: str
    port: int
    public_origin: str
    session_secret: str
    csrf_secret: str
    nebius_api_key: str
    nebius_project_id: str
    nebius_base_url: str
    craft_connector_enabled: bool
    craft_authorization_attested: bool
    craft_authorization_expires_at: str
    craft_docs_mcp_url: str
    craft_tenant_mcp_url: str
    craft_project_id: str
    craft_oauth_client_id: str
    craft_tool_schema_hash: str
    craft_read_probe_succeeded: bool
    craft_read_probe_at: str
    experimental_nemoclaw: bool
    email_enabled: bool
    slack_enabled: bool
    telegram_enabled: bool

    @classmethod
    def load(cls) -> "Settings":
        environment = os.getenv("EMERGEGPT_ENV", "development").strip().lower()
        result = cls(
            environment=environment,
            database_path=Path(os.getenv("EMERGEGPT_DB_PATH", str(ROOT / "runs" / "emergegpt.db"))),
            bind_host=os.getenv("EMERGEGPT_BIND_HOST", "127.0.0.1").strip(),
            port=int(os.getenv("EMERGEGPT_PORT", "8765")),
            public_origin=_url("EMERGEGPT_PUBLIC_ORIGIN", "http://127.0.0.1:8765", required=True),
            session_secret=os.getenv("EMERGEGPT_SESSION_SECRET", ""),
            csrf_secret=os.getenv("EMERGEGPT_CSRF_SECRET", ""),
            nebius_api_key=os.getenv("NEBIUS_API_KEY", ""),
            nebius_project_id=os.getenv("NEBIUS_PROJECT_ID", ""),
            nebius_base_url=_url("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1", required=True),
            craft_connector_enabled=_bool("CRAFT_CONNECTOR_ENABLED"),
            craft_authorization_attested=_bool("CRAFT_AUTHORIZATION_ATTESTED"),
            craft_authorization_expires_at=os.getenv("CRAFT_AUTHORIZATION_EXPIRES_AT", ""),
            craft_docs_mcp_url=_url("CRAFT_DOCS_MCP_URL", "https://docs.emergence.ai/mcp", required=True),
            craft_tenant_mcp_url=_url("CRAFT_TENANT_MCP_URL"),
            craft_project_id=os.getenv("CRAFT_PROJECT_ID", ""),
            craft_oauth_client_id=os.getenv("CRAFT_OAUTH_CLIENT_ID", ""),
            craft_tool_schema_hash=os.getenv("CRAFT_TOOL_SCHEMA_HASH", "").strip(),
            craft_read_probe_succeeded=_bool("CRAFT_READ_PROBE_SUCCEEDED"),
            craft_read_probe_at=os.getenv("CRAFT_READ_PROBE_AT", "").strip(),
            experimental_nemoclaw=_bool("EMERGEGPT_EXPERIMENTAL_NEMOCLAW"),
            email_enabled=_bool("EMERGEGPT_EMAIL_ENABLED"),
            slack_enabled=_bool("EMERGEGPT_SLACK_ENABLED"),
            telegram_enabled=_bool("EMERGEGPT_TELEGRAM_ENABLED"),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("EMERGEGPT_PORT must be between 1 and 65535")
        if self.environment == "production":
            if self.session_secret in {"", "replace-in-production"} or len(self.session_secret) < 32:
                raise ValueError("production requires a strong EMERGEGPT_SESSION_SECRET")
            if self.csrf_secret in {"", "replace-in-production"} or len(self.csrf_secret) < 32:
                raise ValueError("production requires a strong EMERGEGPT_CSRF_SECRET")
            if self.public_origin.endswith("*"):
                raise ValueError("wildcard production origins are forbidden")
        if self.craft_connector_enabled:
            missing = []
            if not self.craft_authorization_attested:
                missing.append("CRAFT_AUTHORIZATION_ATTESTED=true")
            for name, value in (
                ("CRAFT_TENANT_MCP_URL", self.craft_tenant_mcp_url),
                ("CRAFT_PROJECT_ID", self.craft_project_id),
                ("CRAFT_AUTHORIZATION_EXPIRES_AT", self.craft_authorization_expires_at),
            ):
                if not value or value.startswith("replace-"):
                    missing.append(name)
            if missing:
                raise ValueError("CRAFT connector authorization gate failed: " + ", ".join(missing))

    def public_configuration(self) -> dict:
        sensitive = {"session_secret", "csrf_secret", "nebius_api_key", "nebius_project_id", "craft_project_id",
                     "craft_tenant_mcp_url", "craft_oauth_client_id", "craft_tool_schema_hash"}
        values = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in sensitive:
                values[field.name] = {"configured": bool(value and not str(value).startswith("replace-"))}
            else:
                values[field.name] = str(value) if isinstance(value, Path) else value
        return values
