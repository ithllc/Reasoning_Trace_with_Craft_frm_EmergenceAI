#!/usr/bin/env python3
"""CRAFT public-docs and separately authorized tenant-read MCP gateway."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.server.fastmcp import FastMCP

from emergegpt.providers.craft import CraftProvider
from emergegpt_mcp.common import docs_search, runtime

settings, database = runtime()
provider = CraftProvider(settings)
server = FastMCP("EmergeGPT CRAFT MCP")


@server.tool()
def craft_docs_search(query: str) -> dict:
    """Search approved documentation indexed by EmergeGPT; results include repository source paths."""
    return docs_search(database, query, "CRAFT")


@server.tool()
def craft_connection_status() -> dict:
    """Return public-doc and tenant authorization status without identifiers or credentials."""
    return provider.connection_status()


@server.tool()
def craft_tenant_readiness() -> dict:
    """Verify all read gates; this does not create an entitlement or approve mutations."""
    provider.require_authorized()
    return {"ready": True, **provider.authorization_status(),
            "notice": "No tenant data was requested; upstream tools require runtime capability discovery."}


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
