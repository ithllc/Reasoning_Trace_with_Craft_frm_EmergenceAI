# Automated fine-tuning architecture

## Goal

Distill auditable CRAFT-oriented behavior from Sol into `Qwen/Qwen3-30B-A3B-Instruct-2507` with LoRA through Nebius Token Factory, and compare the result with the evaluation recipe published for Qwythos-9B.

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

## Current blocking fact

As of 2026-07-11, Nebius documents the selected Qwen3 MoE model for LoRA and full-parameter fine-tuning, and the authenticated project exposes its exact ID.

The configuration selects LoRA (`lora: true`, rank 16, alpha 16, dropout 0.05) with batch size 16 and context length 8192. The latter pair satisfies Nebius's 131,072 configured-tokens-per-batch minimum. Model eligibility passes, but dataset review remains mandatory before submission.

## Hackathon CRAFT connection

The live tool endpoint is `https://nebius.emergence.ai/mcp`. Every request is scoped with `X-Project-ID: 8c5c41d7-19e0-45ba-8bf6-57fc2706bf1b`. Codex authenticates through PKCE using public client `em-runtime-mcp`; no OAuth client secret is used. Run `codex mcp login craft` once, then verify catalog access with the CRAFT `list_databases` tool.

## Digital Analytics catalog expansion

The follow-up run queried all nine live project connections and their database metadata. An exact `Digital Analytics` metadata search returned zero tagged matches, so the inclusion decision uses the purpose stated in each live database description:

| Included catalog | Why it is in scope |
| --- | --- |
| `firebase-8c5c41d7.FIREBASE` | Mobile-app interaction events, user behavior, device context, and app-performance analysis |
| `ga4-8c5c41d7.GA4` | E-commerce events, sessions, engagement, purchases, and conversion analysis |

Brazilian E-commerce, Crypto, DEPS_DEV_V1, GitHub Repositories, IDC, PanCancer Atlas, and TheLook E-commerce are excluded from this run because their live descriptions do not define them as digital interaction analytics catalogs. The evidence snapshot is `data/generated/digital-analytics-catalogs.json`; it contains catalog/schema metadata only and no sampled source rows.

Generate and prepare this batch with:

```bash
python3 scripts/craft_mcp.py digital-analytics --output data/generated/digital-analytics-catalogs.json
python3 scripts/pipeline.py generate --seeds data/seeds/digital-analytics-prompts.jsonl --catalog data/generated/digital-analytics-catalogs.json --output data/generated/digital-analytics-teacher.jsonl
python3 scripts/pipeline.py prepare --input data/generated/digital-analytics-teacher.jsonl --output-dir artifacts/digital-analytics-dataset
```

The expanded demo dataset is rebuilt deterministically and split exactly in half:

```bash
python3 scripts/build_digital_analytics_seeds.py
python3 scripts/pipeline.py prepare --input data/generated/digital-analytics-200-teacher.jsonl --output-dir artifacts/digital-analytics-200-dataset
python3 scripts/pipeline.py submit --dataset-dir artifacts/digital-analytics-200-dataset
python3 scripts/pipeline.py monitor <job-id> --max-seconds 600
```

The latest run used 100 training and 100 validation examples, context length 8,192, LoRA rank/alpha 16, and a strict ten-minute wall-clock guard. It succeeded in 509 seconds and processed 76,875 tokens. Its three checkpoint train losses were 6.0642, 6.0598, and 6.0544; validation losses were 6.1477, 6.0243, and 5.9859. These losses are training diagnostics, not base-versus-LoRA benchmark results.

## Qwythos evaluation reproduction

The Qwythos model card reports `lm-evaluation-harness` with the Hugging Face backend, chat template enabled, a 100-example limit, and Qwen sampling (`temperature=0.6`, `top_p=0.95`, `top_k=20`). Its published table covers:

- GSM8K flexible and strict exact match
- MMLU accuracy across 57 subjects
- ARC Challenge accuracy and normalized accuracy
- GPQA Diamond, chain-of-thought zero-shot, flexible exact match

It separately reports a seven-prompt tool-use harness using a Python executor and DuckDuckGo web search. The model card says raw result and sample files are available on request, so exact sample-level reproduction is not guaranteed from the published repository alone. Our configuration preserves the public task and sampling recipe and treats the custom tool suite as a separately versioned evaluation.

## Commands

```bash
# Show tool surfaces
python3 scripts/pipeline.py inventory

# Generate structured teacher examples (calls Codex and the CRAFT docs MCP)
python3 scripts/pipeline.py generate

# Validate and split the generated examples
python3 scripts/pipeline.py prepare --input data/generated/teacher.jsonl

# Authenticated, read-only check of the Nebius live model catalog
NEBIUS_API_KEY=... python3 scripts/pipeline.py preflight-nebius

# This remains safely blocked until exact 9B support is verified
NEBIUS_API_KEY=... python3 scripts/pipeline.py submit

# Print the Qwythos-compatible lm-eval command; add --run to execute it
python3 scripts/pipeline.py eval --model Qwen/Qwen3-30B-A3B-Instruct-2507
```

## Teacher identity

The teacher is pinned to `gpt-5.6-sol`, which is present in this environment's Codex model configuration. `CODEX_TEACHER_MODEL` controls the non-interactive `codex exec` teacher process. Run manifests record the teacher label and model identity.

## Primary references

- [Qwythos-9B source model card](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M)
- [Qwythos GGUF model card](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF)
- [Qwythos published tool-test transcript](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M/blob/main/evals/tool_test_outputs.md)
- [Qwen3-30B-A3B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507)
- [Nebius supported post-training models](https://docs.tokenfactory.nebius.com/post-training/models)
- [Nebius supervised fine-tuning API guide](https://docs.tokenfactory.nebius.com/post-training/how-to-fine-tune)
- [CRAFT solution developer guide](https://docs.emergence.ai/guides/solution-dev/overview)
