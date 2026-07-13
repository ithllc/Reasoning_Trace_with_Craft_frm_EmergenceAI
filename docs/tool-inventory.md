# Tool inventory

This separates platform interfaces from functions a trained model may choose to call.

## Emergence.ai CRAFT

| Surface | Use in this project | Access status |
| --- | --- | --- |
| Public documentation MCP (`emergence-craft`) | Ground teacher tasks in current CRAFT concepts and API documentation | Configured for documentation |
| EmergeGPT CRAFT MCP | Public-doc search plus optional authorized tenant readiness/read tooling | Tenant capability disabled by default |
| Catalog tools | Discovered at runtime from a separately authorized tenant | Omitted when unavailable or unauthorized |
| SQL/data tools | Not part of the public product's default tool surface | Require separate documented authorization and policy review |
| Assets service / SDK | Data connections, artifacts, files, models, and agent records | Documented surface; not directly used by this demo |
| Agent/workflow/governance capabilities | Use only when confirmed by current public docs and authorized runtime discovery | Never inferred from event access |

Do not invent vendor APIs. Public documentation claims, runtime-discovered capabilities, synthetic EmergeGPT conventions, and tenant evidence must remain visibly distinct.

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

Hosted models may emit tool-call instructions; the application executes only allowlisted tools and returns their results. EmergeGPT evaluations measure tool selection, JSON argument validity, grounding, permission behavior, and final-answer correctness through versioned project-owned cases.

The active inference and fine-tuning model is `Qwen/Qwen3-30B-A3B-Instruct-2507`. Dashboard Q&A uses the base serverless model, not a trained LoRA checkpoint. The voice service enforces a local `$50` ledger; training uses separately configured wall-clock guards.
