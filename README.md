# Emergence CRAFT Reasoning Trace Workspace

This workspace is the home for designing auditable reasoning traces with Codex (agent name: **Sol**) and the Emergence.ai CRAFT documentation MCP server.

It now also contains a gated automation pipeline for distilling those traces into `Qwen/Qwen3.5-9B` and fine-tuning through Nebius Token Factory. Start with [the automation guide](docs/automation.md) and [tool inventory](docs/tool-inventory.md).

## Where everything lives

| Item | Location | Purpose |
| --- | --- | --- |
| Codex project configuration | `.codex/config.toml` | Connects this workspace to the CRAFT MCP server |
| Codex user configuration | `/root/.codex/config.toml` | Makes the same MCP server available across local workspaces |
| Sol's standing instructions | `AGENTS.md` | Tells Codex how to work in this repository |
| Architecture and vocabulary | `docs/architecture.md` | Explains the design in beginner-friendly language |
| Trace contract | `schemas/reasoning-trace.schema.json` | Defines the shared auditable trace format |
| Domain designs | `designs/<domain>/design.yaml` | Captures each catalog or registry design |
| Worked traces | `examples/` | Holds example trace instances as they are created |
| Fine-tuning configuration | `config/pipeline.json` | Pins teacher, student, CRAFT, Nebius, and eval settings |
| Automation CLI | `scripts/pipeline.py` | Generates, validates, submits, monitors, and evaluates |

The server is also registered in `/root/.codex/config.toml` under the name `emergence-craft`, so it is available outside this workspace too. That user file is managed by `codex mcp` commands; the project copy is the version-controlled declaration for this workspace.

## Start here

1. Change into this directory:

   ```bash
   cd /llm_models_python_code_src/emergence-craft-reasoning
   ```

2. Confirm the server is registered:

   ```bash
   codex mcp list
   ```

3. Start a fresh Codex session from this directory. Project `.codex/config.toml` settings are loaded when the repository is trusted.

4. Ask Sol to test the server:

   > Sol, use the emergence-craft MCP server to find CRAFT documentation about agents, workflows, and the Assets service. Summarize which public APIs map to this workspace's four design domains. Do not modify files yet.

5. Begin with one domain, preferably the Data Catalog:

   > Sol, use the CRAFT docs and `schemas/reasoning-trace.schema.json` to draft the first Data Catalog trace in `examples/`. Clearly label assumptions and unresolved CRAFT API mappings.

## Connection details

- Server name: `emergence-craft`
- Endpoint: `https://docs.emergence.ai/mcp`
- Scope: public CRAFT documentation search
- Authentication: none documented for the public endpoint

This MCP endpoint provides documentation lookup. It does not by itself connect to a deployed CRAFT tenant or its private Data Catalog, Workflows, Agent Registry, or service data. That later connection will require the tenant URL and its authentication/authorization details.

## Useful commands

```bash
codex mcp get emergence-craft
codex mcp list
codex mcp remove emergence-craft
```

## Safety rule

Store concise decision summaries and evidence references, never private chain-of-thought, passwords, access tokens, raw secrets, or sensitive source records.
