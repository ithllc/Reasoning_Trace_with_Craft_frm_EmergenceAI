# EmergeGPT evaluation program

EmergeGPT uses project-owned, versioned evaluations. Training and validation loss are optimization diagnostics, not proof of task quality. Promotion requires matched base-versus-candidate prompts plus required safety, privacy, permission, grounding, tool-use, robustness, latency, and cost checks.

## Required evaluation families

| Family | Example metrics | Default promotion interpretation |
| --- | --- | --- |
| Dataset integrity | schema validity, unique IDs, split disjointness, source hash | 100% required |
| Evidence grounding | valid fixture/source references, citation support | 100% required references |
| Safety and privacy | secret leakage, regulated rows, permission violations | zero tolerance |
| Tool use | selection accuracy, argument schema validity, result grounding | versioned workspace target |
| Domain task quality | independently authored held-out success rate | must meet target and not regress |
| Robustness | injection resistance, refusal, malformed input handling | all required cases pass |
| Efficiency | latency, input/output tokens, provider cost, cost per success | report with quality; never trade for safety |

Every metric includes direction, warning/target/critical thresholds, rationale, sample count, and confidence interval. Binary rates use Wilson intervals; paired comparisons use paired bootstrap or another preregistered paired method. LLM judges pin the judge model, prompt, version, order randomization, and human-audited calibration sample.

## Current historical diagnostics

The repository contains sanitized summaries of four proof-of-concept LoRA sessions. They remain `not_promoted` until an adapter is deployed and evaluated on identical held-out prompts. The latest 1,000-example run processed 408,285 tokens and completed under its wall-clock limit; its shared deterministic templates make validation loss a consistency signal rather than an independent generalization result.

New evaluation definitions belong in `evals/definitions/` and must validate against the evaluation schema before execution.
