# Tool inventory

This separates platform interfaces from functions a trained model may choose to call.

## Emergence.ai CRAFT

| Surface | Use in this project | Access status |
| --- | --- | --- |
| Public documentation MCP (`emergence-craft`) | Ground teacher tasks in current CRAFT concepts and API documentation | Configured for documentation |
| Hackathon tenant MCP (`craft`) | Project-scoped catalog/schema discovery and read-only query tooling | Connected through OAuth; re-login when expired |
| Catalog tools | `list_data_connections`, `list_databases`, `get_schema`, and `search_schema` | Used to inventory all nine connections and snapshot Firebase/GA4 |
| SQL/data tools | SQL generation, read-only execution, paging, terms, charts, and sampling | Available but not used to copy source rows into training data |
| Assets service / SDK | Data connections, artifacts, files, models, and agent records | Documented surface; not directly used by this demo |
| Agent-card validation and registry | Validate/select agent skills | Not exposed by the current tenant MCP tool list |
| Pipeline/workflow framework | Stateful steps, run state, retries, outputs, cancellation | Trace design only; not exposed by the current tenant MCP tool list |
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

The active inference and fine-tuning model is `Qwen/Qwen3-30B-A3B-Instruct-2507`. Dashboard Q&A uses the base serverless model, not a trained LoRA checkpoint. The voice service enforces a local `$50` ledger; training uses separately configured wall-clock guards.
