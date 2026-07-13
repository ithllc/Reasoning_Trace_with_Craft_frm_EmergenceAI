# Automated fine-tuning architecture

## Goal

Distill auditable, evidence-oriented behavior from an interchangeable teacher harness into an eligible student model through a governed LoRA or full-parameter workflow, then compare base and candidate using project-owned evaluations.

## UI workflow

The dashboard now exposes the backend capabilities directly:

- **MCP Builder · Nebius Model Roles** has two different selectors: teachers are live Nebius inference models joined to recorded license evidence; students are only models in Nebius's official fine-tuning list, with unsupported LoRA/full choices disabled.
- **MCP Builder · Automation · Pipeline Runs** creates an immutable request, notifies the selected Codex/Claude Code/OpenCode/OpenClaw/Gemini CLI/NemoClaw harness, and persists queued, dispatching, running, terminal, and error events. Dry-run planning is the default. Paid Nebius teacher generation, uploads, training submission, monitoring cancellation, and deployment require a matching one-time live approval.
- **Analytics · Cost Savings** compares only matched base/tuned prompts and settings. It reports token and cost savings, amortized one-time costs, cost per success, and break-even requests; mismatched comparison keys produce no savings claim.

Selecting a Nebius teacher changes the generation command. For an approved live run, the harness invokes `pipeline.py generate --teacher-provider nebius --teacher-model <exact-id>`, which requests schema-constrained teacher examples through the configured Token Factory API. The exact teacher model, dataset hash, student, mode, stages, wall-clock limit, and budget are part of the approval and cannot be changed by the harness.

The training examples contain final answers plus concise evidence, action, policy, and validation summaries. They do not collect hidden chain-of-thought.

## Model selection decision

The original student target was `Qwen/Qwen3.5-9B`, which the authenticated project does not expose. The active target is now `Qwen/Qwen3-30B-A3B-Instruct-2507`, which is both API-visible and documented for LoRA. It has about 30B total and 3B active parameters per token.

## Pipeline

```text
CRAFT docs + seed tasks
        |
        v
Sol / Codex teacher --structured output--> validated JSONL
        |                                      |
        |                               deterministic split
        |                                      |
        +---------------- trace manifest -------+
                                               v
                                  Nebius Files API
                                               |
                                  Fine-tuning Jobs API
                                               |
                                events -> checkpoints
                                               |
                            lm-eval + 7-case tool harness
```

## Current training configuration

As of 2026-07-11, Nebius documents the selected Qwen3 MoE model for LoRA and full-parameter fine-tuning, and the authenticated project exposes its exact ID.

The configuration selects LoRA (`lora: true`, rank 16, alpha 16, dropout 0.05) with batch size 16 and context length 8192. The latter pair satisfies Nebius's 131,072 configured-tokens-per-batch minimum. Model eligibility and the current 1,000-example dataset review must pass before submission. New datasets still require their own review record before submission.

## Optional CRAFT connection

Public CRAFT documentation can be indexed from its official documentation surface. Live tenant connectivity is disabled by default and requires separate current written authorization, deployer-owned credentials/project scope, and the EmergeGPT connector authorization gate. Event endpoints, project identifiers, and tenant snapshots are not distributed with the product.

## Digital Analytics catalog expansion

The public demo uses synthetic catalog fixtures representing mobile and web analytics:

| Included catalog | Why it is in scope |
| --- | --- |
| `synthetic-mobile.MOBILE_ANALYTICS` | Synthetic mobile interaction and performance metadata |
| `synthetic-web.WEB_ANALYTICS` | Synthetic web engagement and conversion metadata |

Fixtures contain no source rows, tenant identifiers, or confidential platform data. Authorized deployments may generate their own private snapshots, which remain ignored and outside release artifacts.

Generate and prepare this batch with:

```bash
python3 scripts/craft_mcp.py digital-analytics --output data/generated/digital-analytics-catalogs.json
python3 scripts/pipeline.py generate --seeds data/seeds/digital-analytics-prompts.jsonl --catalog data/generated/digital-analytics-catalogs.json --output data/generated/digital-analytics-teacher.jsonl
python3 scripts/pipeline.py prepare --input data/generated/digital-analytics-teacher.jsonl --output-dir artifacts/digital-analytics-dataset
```

The expanded demo dataset is rebuilt deterministically and split exactly in half:

```bash
python3 scripts/build_digital_analytics_seeds.py
python3 scripts/pipeline.py prepare --input data/generated/digital-analytics-1000-teacher.jsonl --output-dir artifacts/digital-analytics-1000-dataset
python3 scripts/pipeline.py submit --dataset-dir artifacts/digital-analytics-1000-dataset
python3 scripts/pipeline.py monitor <job-id> --max-seconds 3600
```

The latest run used 500 training and 500 validation examples, context length 8,192, LoRA rank/alpha 16, and a strict one-hour wall-clock guard. Job `ftjob-8ae7abeefe1242b08eaf306b230df120` succeeded in 515 seconds, processed 408,285 tokens, and completed 6/6 steps. Recorded checkpoint train losses were 6.6013, 6.3410, and 6.1220; validation losses were 3.8360, 3.7634, and 3.7764. These losses are training diagnostics, not base-versus-LoRA benchmark results, and the shared templates prevent treating validation as independent generalization.

## EmergeGPT evaluation program

Evaluation definitions are versioned and project-owned. Required families cover dataset integrity, evidence grounding, privacy/permissions, tool use, domain correctness, robustness, matched base-versus-candidate quality, latency, tokens, and cost. Each metric declares direction, thresholds, rationale, sample size, and confidence method. Missing required results block promotion.

## Commands

```bash
# Show tool surfaces
python3 scripts/pipeline.py inventory

# Rebuild and split the current Digital Analytics dataset
python3 scripts/build_digital_analytics_seeds.py
python3 scripts/pipeline.py prepare --input data/generated/digital-analytics-1000-teacher.jsonl --output-dir artifacts/digital-analytics-1000-dataset

# Authenticated, read-only check of the Nebius live model catalog
NEBIUS_API_KEY=... python3 scripts/pipeline.py preflight-nebius

# Upload and train only after review.json is approved
NEBIUS_API_KEY=... python3 scripts/pipeline.py submit --dataset-dir artifacts/digital-analytics-1000-dataset
python3 scripts/pipeline.py monitor <job-id> --max-seconds 3600

# Print the configured evaluation-runner command; add --run only in an approved environment
python3 scripts/pipeline.py eval --model Qwen/Qwen3-30B-A3B-Instruct-2507
```

## Teacher identity

The teacher is pinned to `gpt-5.6-sol`, which is present in this environment's Codex model configuration. `CODEX_TEACHER_MODEL` controls the non-interactive `codex exec` teacher process. Run manifests record the teacher label and model identity.

## Evaluation status

The dashboard contains sanitized historical train/validation diagnostics. It does not yet contain a fair base-versus-tuned result. That comparison requires deploying a candidate, sending identical held-out prompts to both variants with identical settings, and recording quality, policy, latency, token, and cost metrics. Training loss must not be relabeled as task-quality improvement.

## Primary references

- [Qwen3-30B-A3B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)
- [Nebius supported post-training models](https://docs.tokenfactory.nebius.com/post-training/models)
- [Nebius supervised fine-tuning API guide](https://docs.tokenfactory.nebius.com/post-training/how-to-fine-tune)
- [CRAFT solution developer guide](https://docs.emergence.ai/guides/solution-dev/overview)
