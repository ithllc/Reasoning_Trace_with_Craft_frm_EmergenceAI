# EmergeGPT architecture

## The simple mental model

EmergeGPT is a vendor-neutral control plane. Interchangeable harnesses create auditable examples from synthetic, public, or separately authorized evidence. Provider adapters perform capability-gated training and inference; the repository stores synthetic fixtures, trace contracts, sanitized diagnostics, and application code.

```text
User -> EmergeGPT UI/API -> workflow, approval, schedule, eval, cost, health
                  |       -> documentation index + two MCP policy gateways
                  |       -> Codex / Claude Code / OpenCode / OpenClaw / Gemini / NemoClaw
                  |       -> authorized provider adapters
                  v
       synthetic reviewed examples -> train/validation -> LoRA or full tuning
                                                     -> evaluation -> promotion gate
```

## What a reasoning trace means here

A reasoning trace is an auditable record of what an agent or workflow did. It includes the request, relevant asset identifiers, evidence references, tool calls, policy checks, a concise decision summary, output, and validation status. It intentionally excludes hidden chain-of-thought.

## Domain views

| Domain | Question the trace answers | Likely trace keys |
| --- | --- | --- |
| Data Catalog | Which data assets and metadata supported the result? | connection, dataset, schema, column, classification |
| Workflows | Which run and steps produced the result? | workflow, run, step, attempt, state |
| Agent Registry | Which agent definition and skill acted? | agent, version, skill, protocol, endpoint |
| Service Registry | Which runtime service fulfilled a call? | service, version, environment, endpoint, health |

CRAFT's public documentation describes Assets for agents, data connections, artifacts, files, and models; Prefect-backed workflows in Data Governance; and A2A agent cards. The public solution guide also says there is not yet a Backstage-style service catalog. Therefore, the Service Registry design in this workspace is initially a proposed abstraction and must not be represented as an existing CRAFT API until the MCP documentation confirms one.

The active public demo category is **Digital Analytics** and uses synthetic mobile/web metadata only. No event tenant snapshot or source row is part of the public fixture. A named live connector is optional and requires the deployer's own current legal authorization and credentials.

## Trace lifecycle

1. A user request, event, or schedule creates the trace.
2. Sol or a runtime component attaches stable identifiers for affected catalog/registry assets.
3. Each external lookup or tool action is recorded with timestamps and status.
4. Policy and permission checks are recorded without credentials.
5. A concise decision summary and output references are attached.
6. Validation marks the trace `passed`, `failed`, or `needs_review`.
7. Related domain traces link to one another using trace IDs.

## Current runtime boundaries

- Public documentation and live tenant authorization are separate capabilities.
- CRAFT tenant access is disabled by default and fails closed without a current authorization attestation and deployer-owned scope.
- Catalog discovery is synthetic unless a separately authorized connector is enabled.
- Workflow and agent-registry operations in examples are proposed trace conventions unless a live tool proves otherwise.
- Fine-tuning submission is an explicit Nebius mutation with a wall-clock cancellation guard.
- Completed datasets and sessions are immutable in the dashboard.
- Historical LoRA diagnostics are sanitized and not promoted; identical-prompt base-versus-candidate evaluation remains pending deployment.
- Credentials remain only in ignored `.env` and Codex's OAuth cache.
