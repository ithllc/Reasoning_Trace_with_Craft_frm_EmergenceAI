# MCP Builder

The EmergeGPT UI includes **Integrations → MCP Builder**, a step-through helper that generates two independent policy gateways.

## Important: subscription access is required—MCP Builder does not create CRAFT access

A subscribed user can authorize an official CRAFT API or tenant MCP endpoint through this feature only when Emergence supplies that endpoint or tooling and all five gates pass:

1. The customer provides their own project-scoped authorization.
2. EmergeGPT discovers and validates the available tool schemas.
3. A harmless read probe succeeds.
4. The deployment has contractual authorization to use the integration.
5. Mutation permissions are approved separately for the exact operation.

MCP Builder is the configuration and policy foundation. It cannot create a subscription, entitlement, endpoint, API, tool, or permission that Emergence has not made available to the customer. A configured URL is not proof of access. The UI reports documentation-only, blocked, read-ready, and separately mutation-approved states without treating them as interchangeable.

## CRAFT server

The CRAFT server searches approved public documentation and reports tenant-connector readiness. Live tenant access is disabled by default. Enabling it requires separate current written authorization, deployer-owned environment configuration, a valid authorization window, a discovered tool-schema hash, and a successful harmless read probe. The public product does not include event credentials, project IDs, tenant snapshots, or rights to use CRAFT.

## Nebius server

The Nebius server searches approved documentation and exposes configured account reads for models and fine-tuning jobs. Its cancellation tool demonstrates the mutation contract: exact resource scope, workflow/config hash, budget, expiry, and a one-time approval nonce are required before the provider call.

## Wizard

The wizard moves through select, prerequisites, references, capabilities, preview, validation, install, sandbox test, and complete. Drafts contain no secrets. Preview shows files, tool inventory, policy, and harness snippets for Codex, Claude Code, OpenCode, OpenClaw, Gemini CLI, and NemoClaw. Installation is local and hash-gated; global harness configuration is never silently changed.

Run either stdio server directly:

```bash
python3 emergegpt_mcp/craft_server.py
python3 emergegpt_mcp/nebius_server.py
```

Use the UI-generated snippet for the target harness. NemoClaw requires a separately reviewed OpenShell network/provider policy rather than copying a local secret into its configuration.
