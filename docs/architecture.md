# Architecture

## The simple mental model

Codex is the design environment and **Sol** is the teacher agent. The authenticated CRAFT tenant MCP supplies project-scoped catalog metadata; the public CRAFT MCP supplies product documentation. The repository stores read-only catalog snapshots, auditable traces, deterministic datasets, Nebius run records, and dashboard code.

```text
You -> Sol in Codex -> authenticated CRAFT tenant MCP
                 |                 |
                 |                 +-> Firebase + GA4 metadata
                 +-> 200 trace examples -> 100 train / 100 validation
                                           |
                                           +-> Nebius Qwen3 LoRA
                                                        |
                                                        +-> run history + UI
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

The active demo category is **Digital Analytics**. All nine tenant connections were inventoried; Firebase and GA4 were selected from their live descriptions. Firebase supplies mobile-app interaction metadata, while GA4 supplies e-commerce events, sessions, engagement, purchase, and conversion metadata. No source rows are committed or used in traces.

## Trace lifecycle

1. A user request, event, or schedule creates the trace.
2. Sol or a runtime component attaches stable identifiers for affected catalog/registry assets.
3. Each external lookup or tool action is recorded with timestamps and status.
4. Policy and permission checks are recorded without credentials.
5. A concise decision summary and output references are attached.
6. Validation marks the trace `passed`, `failed`, or `needs_review`.
7. Related domain traces link to one another using trace IDs.

## Current runtime boundaries

- Tenant metadata access is authenticated with Keycloak PKCE and scoped by `X-Project-ID`.
- Catalog discovery and schema retrieval are read-only.
- Workflow and agent-registry operations in examples are proposed trace conventions unless a live tool proves otherwise.
- Fine-tuning submission is an explicit Nebius mutation with a wall-clock cancellation guard.
- Completed datasets and sessions are immutable in the dashboard.
- The LoRA checkpoints are trained but not promoted; identical-prompt base-versus-LoRA evaluation remains pending adapter deployment.
- Credentials remain only in ignored `.env` and Codex's OAuth cache.
