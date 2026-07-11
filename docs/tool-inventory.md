# Tool inventory

This separates platform interfaces from functions a trained model may choose to call.

## Emergence.ai CRAFT

| Surface | Use in this project | Access status |
| --- | --- | --- |
| Public documentation MCP (`emergence-craft`) | Ground teacher tasks in current CRAFT concepts and API documentation | Connected |
| Hackathon tenant MCP (`craft`) | Project-scoped database catalog, SQL generation, workflows, and shipped agent tools | Configured; OAuth login required |
| Assets service / SDK | Data connections, artifacts, files, models, and agent records | Tenant connection required |
| Agent-card validation and registry | Validate A2A v0.3/v1.0 cards and select agent skills | Tenant connection required |
| Pipeline/workflow framework | Stateful steps, run state, retries, outputs, cancellation | Tenant connection required |
| Governance/OpenFGA checks | Record authorization outcomes | Tenant connection required |
| Secrets API | Resolve credentials without placing them in traces | Tenant connection required |
| Langfuse and OpenTelemetry | LLM and cross-service operational traces | Deployment/configuration required |

CRAFT's public guide says there is no Backstage-style service catalog today. Do not invent one; use documented Assets and deployment identities until a target tenant exposes something more specific.

## Nebius Token Factory

| Surface | Use in this project |
| --- | --- |
| `GET /v1/models` | Live model availability preflight |
| `POST /v1/files` | Upload training and validation JSONL |
| `POST /v1/fine_tuning/jobs` | Create an SFT/LoRA job |
| Fine-tuning job retrieval/events | Monitor validation and training |
| Job checkpoints and file content | Retrieve adapters or full checkpoints |
| Data Lab | Version/filter inference logs and structured datasets |
| Responses/Chat Completions | Inference and teacher/student evaluation |
| Function tools and MCP tools | Execute external capabilities through an application loop |
| Custom LoRA deployment APIs | Validate and deploy eligible adapters |
| Dedicated endpoints | Host eligible custom weights with controlled capacity |

Nebius models emit tool-call instructions; the application executes the tool and returns its result. The initial model evaluation tool set is `python` and `web_search`, matching Qwythos's published custom harness. CRAFT-specific evaluation later adds read-only asset lookup, workflow status, agent discovery, and permission-check tools.
