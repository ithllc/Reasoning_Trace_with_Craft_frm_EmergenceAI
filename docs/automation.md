# Automated fine-tuning architecture

## Goal

Distill auditable CRAFT-oriented behavior from Sol (the Codex teacher) into `Qwen/Qwen3.5-9B`, fine-tune through Nebius Token Factory, and compare the result with the evaluation recipe published for Qwythos-9B.

The training examples contain final answers plus concise evidence, action, policy, and validation summaries. They do not collect hidden chain-of-thought.

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

As of 2026-07-11, Nebius's official post-training model list documents `Qwen/Qwen3.5-27B` for full-parameter fine-tuning, but not `Qwen/Qwen3.5-9B`. The requested 9B model is real and is the base used by Qwythos, but it cannot currently be submitted as a supported Token Factory fine-tuning base based on public documentation.

The target remains 9B. `pipeline.py submit` intentionally fails before uploads or spend while the support gate is false. Recheck both the official supported-model page and the authenticated live model catalog before changing that gate.

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
python3 scripts/pipeline.py eval --model Qwen/Qwen3.5-9B
```

## Teacher identity

“Codex (GPT 5.6 Sol)” is stored as the requested teacher label. It is not hard-coded as a model slug because public Codex documentation does not establish that exact slug. By default, `codex exec` uses the authenticated Codex model configured for the environment. Set `CODEX_TEACHER_MODEL` only to a model ID that the installed Codex client actually supports. Run manifests must record both the label and effective model when that information is available.

## Primary references

- [Qwythos-9B source model card](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M)
- [Qwythos GGUF model card](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF)
- [Qwythos published tool-test transcript](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M/blob/main/evals/tool_test_outputs.md)
- [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Nebius supported post-training models](https://docs.tokenfactory.nebius.com/post-training/models)
- [Nebius supervised fine-tuning API guide](https://docs.tokenfactory.nebius.com/post-training/how-to-fine-tune)
- [CRAFT solution developer guide](https://docs.emergence.ai/guides/solution-dev/overview)
