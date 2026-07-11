# Architecture

## The simple mental model

Codex is the design environment. **Sol** is the name used for the Codex agent in this workspace. The CRAFT MCP server supplies current public documentation. The files in this repository hold the designs. A future CRAFT tenant connection will supply and receive real operational data.

```text
You -> Sol in Codex -> CRAFT documentation MCP
                 |
                 +-> versioned designs and example traces
                 |
                 +-> future authenticated CRAFT tenant connection
```

## What a reasoning trace means here

A reasoning trace is an auditable record of what an agent or workflow did. It includes the request, relevant asset identifiers, evidence references, tool calls, policy checks, a concise decision summary, output, and validation status. It intentionally excludes hidden chain-of-thought.

## Four domain views

| Domain | Question the trace answers | Likely trace keys |
| --- | --- | --- |
| Data Catalog | Which data assets and metadata supported the result? | connection, dataset, schema, column, classification |
| Workflows | Which run and steps produced the result? | workflow, run, step, attempt, state |
| Agent Registry | Which agent definition and skill acted? | agent, version, skill, protocol, endpoint |
| Service Registry | Which runtime service fulfilled a call? | service, version, environment, endpoint, health |

CRAFT's public documentation describes Assets for agents, data connections, artifacts, files, and models; Prefect-backed workflows in Data Governance; and A2A agent cards. The public solution guide also says there is not yet a Backstage-style service catalog. Therefore, the Service Registry design in this workspace is initially a proposed abstraction and must not be represented as an existing CRAFT API until the MCP documentation confirms one.

## Trace lifecycle

1. A user request, event, or schedule creates the trace.
2. Sol or a runtime component attaches stable identifiers for affected catalog/registry assets.
3. Each external lookup or tool action is recorded with timestamps and status.
4. Policy and permission checks are recorded without credentials.
5. A concise decision summary and output references are attached.
6. Validation marks the trace `passed`, `failed`, or `needs_review`.
7. Related domain traces link to one another using trace IDs.

## Next connection milestone

The current MCP server searches public documentation. To work against a real CRAFT installation, collect these without committing secrets:

- CRAFT tenant/base URL
- organization and project identifiers
- authentication method (for example OIDC/JWT)
- the user's role and allowed operations
- relevant Assets, workflow, agent, and service endpoints
- a safe secret-injection method

Use environment variables or the platform secret manager for secret values.
