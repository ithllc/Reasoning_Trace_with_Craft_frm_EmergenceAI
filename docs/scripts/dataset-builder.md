# `scripts/build_digital_analytics_seeds.py`

Purpose: generate 1,000 deterministic examples from ten policy templates, twenty scenarios, and five analysis windows. All evidence identifiers are explicitly synthetic. The script writes seed and teacher JSONL; `pipeline.py prepare` performs the deterministic 500/500 split. Limitations: shared templates measure consistency, not independent generalization.
