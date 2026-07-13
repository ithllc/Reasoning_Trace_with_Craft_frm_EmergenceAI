#!/usr/bin/env python3
"""Nebius documentation and approval-gated Token Factory MCP gateway."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.server.fastmcp import FastMCP

from emergegpt.approvals import consume
from emergegpt.providers.nebius import NebiusProvider
from emergegpt_mcp.common import docs_search, runtime

settings, database = runtime()
provider = NebiusProvider(settings)
server = FastMCP("EmergeGPT Nebius MCP")


@server.tool()
def nebius_docs_search(query: str) -> dict:
    """Search approved Nebius-related documentation indexed by EmergeGPT."""
    return docs_search(database, query, "Nebius Token Factory")


@server.tool()
def nebius_models_list() -> dict:
    """List current models from the configured deployer-owned Nebius account."""
    return {"data": provider.models(), "source_kind": "live_provider_api", "policy": {"live_mutation": False}}


@server.tool()
def nebius_jobs_list() -> dict:
    """List fine-tuning jobs without returning credentials."""
    return {"data": provider.jobs(), "source_kind": "live_provider_api", "policy": {"live_mutation": False}}


@server.tool()
def nebius_job_get(job_id: str) -> dict:
    """Get one fine-tuning job."""
    return {"data": provider.job(job_id), "source_kind": "live_provider_api", "policy": {"live_mutation": False}}


@server.tool()
def nebius_job_checkpoints(job_id: str) -> dict:
    """List checkpoints for one fine-tuning job."""
    return {"data": provider.checkpoints(job_id), "source_kind": "live_provider_api", "policy": {"live_mutation": False}}


@server.tool()
def nebius_job_cancel(job_id: str, workflow_id: str, approval_id: str, approval_nonce: str,
                      config_hash: str, estimated_cost_usd: float = 0.0) -> dict:
    """Cancel a job only with an exact, one-time EmergeGPT approval."""
    scope = {"provider": "nebius", "mutation": "job_cancel", "job_id": job_id}
    consume(database, approval_id, approval_nonce, workflow_id=workflow_id, scope=scope,
            config_hash=config_hash, estimated_cost=estimated_cost_usd)
    return {"data": provider.request("POST", f"fine_tuning/jobs/{job_id}/cancel", {}),
            "source_kind": "live_provider_api", "policy": {"live_mutation": True, "approval_id": approval_id}}


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
