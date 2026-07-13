# `scripts/pipeline.py`

Purpose: compatibility CLI for synthetic dataset preparation and authorized Nebius lifecycle operations. Inputs are JSON/JSONL and `config/pipeline.json`; outputs are manifests, ignored run records, or provider resources. `inventory`, `prepare`, preflight, list, and checkpoint retrieval are read-only/local. `submit`, monitor timeout cancellation, and deploy mutate live provider state. Use exact model IDs, reviewed datasets, budgets, and wall-clock limits. Credentials come from environment variables and must never be committed.
