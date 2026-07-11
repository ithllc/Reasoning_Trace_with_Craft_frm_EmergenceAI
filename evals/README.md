# LLM evaluations

The evaluation program combines the published Qwythos recipe with CRAFT-specific quality gates.

## Published benchmark suite

The reproducible public portion uses EleutherAI `lm-evaluation-harness`, the Hugging Face backend, chat templating, a 100-example limit, and sampling values `temperature=0.6`, `top_p=0.95`, and `top_k=20`.

| Task | Metric | Qwythos reference |
| --- | --- | ---: |
| GSM8K | flexible exact match | 0.860 |
| GSM8K | strict exact match | 0.810 |
| MMLU | accuracy | 0.575 |
| ARC Challenge | accuracy | 0.490 |
| ARC Challenge | normalized accuracy | 0.410 |
| GPQA Diamond CoT, zero-shot | flexible exact match | 0.580 |

These values are references, not claims about the current student. Base and LoRA checkpoints must be evaluated with identical settings.

Print the exact command:

```bash
python3 scripts/pipeline.py eval --model Qwen/Qwen3-30B-A3B-Instruct-2507
```

Execute it in an environment with `lm_eval`, the model weights, and sufficient GPU capacity:

```bash
python3 scripts/pipeline.py eval --model Qwen/Qwen3-30B-A3B-Instruct-2507 --run
```

## Tool-use evaluation

Qwythos separately reports seven tool-use cases using Python execution and web search. We score tool selection, JSON argument validity, grounding in returned results, and final-answer correctness. Public source transcripts do not include a complete standalone runner, so this is tracked separately from the reproducible `lm_eval` tasks.

## CRAFT evaluation

Every candidate checkpoint must pass all held-out CRAFT cases:

- evidence FQNs exist in the committed GitHub catalog snapshot;
- missing freshness, quality, permission, or provenance blocks customer-facing use;
- no tool or API is invented;
- no private chain-of-thought is requested or emitted;
- final answers are grounded in supplied tool results;
- training and evaluation example IDs are disjoint.

Results belong in `evals/results/` and should include the base-model result, LoRA result, configuration hash, dataset manifest hash, and promotion decision.

The first LoRA pipeline-validation run succeeded as job `ftjob-a16a0aa96695477593c126598b12f88b` in 3 steps and 1,437 trained tokens. Its benchmark status remains pending and its promotion decision is `not_promoted` until the base and adapter complete the full suite.

## Sources

- [Qwythos source model card](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M)
- [Qwythos tool-test transcript](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M/blob/main/evals/tool_test_outputs.md)
- [Machine-readable suite](qwythos-suite.json)
