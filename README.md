# Emergence CRAFT Reasoning Trace Workspace

This workspace designs auditable **Digital Analytics** reasoning traces with Codex teacher **Sol** (`gpt-5.6-sol`), the live Emergence.ai CRAFT hackathon MCP server, and Nebius Token Factory. It uses the CRAFT Firebase and GA4 catalogs and trains `Qwen/Qwen3-30B-A3B-Instruct-2507` with LoRA.

Model decision: the original `Qwen/Qwen3.5-9B` is unavailable. The active student is `Qwen/Qwen3-30B-A3B-Instruct-2507`: it is visible to this API key and officially supports LoRA and full-parameter training. This project uses LoRA.

It now also contains a gated automation pipeline for distilling those traces into the selected Qwen3 MoE model and fine-tuning through Nebius Token Factory. Start with [the automation guide](docs/automation.md) and [tool inventory](docs/tool-inventory.md).

## Where everything lives

| Item | Location | Purpose |
| --- | --- | --- |
| Codex project configuration | `.codex/config.toml` | Connects this workspace to the CRAFT MCP server |
| Codex user configuration | `/root/.codex/config.toml` | Makes the same MCP server available across local workspaces |
| Sol's standing instructions | `AGENTS.md` | Tells Codex how to work in this repository |
| Architecture and vocabulary | `docs/architecture.md` | Explains the design in beginner-friendly language |
| Trace contract | `schemas/reasoning-trace.schema.json` | Defines the shared auditable trace format |
| Domain designs | `designs/<domain>/design.yaml` | Captures each catalog or registry design |
| Worked traces | `examples/` | Holds example trace instances as they are created |
| Fine-tuning configuration | `config/pipeline.json` | Pins teacher, student, CRAFT, Nebius, and eval settings |
| Automation CLI | `scripts/pipeline.py` | Generates, validates, submits, monitors, and evaluates |
| Local credentials | `.env` | Git-ignored, mode `0600`; never commit this file |
| LLM evaluation suite | `evals/` | Qwythos-compatible benchmarks, CRAFT gates, and results |
| Digital Analytics evidence | `data/generated/digital-analytics-catalogs.json` | Read-only Firebase/GA4 metadata snapshot |
| Current teacher dataset | `data/generated/digital-analytics-200-teacher.jsonl` | 200 deterministic auditable examples |
| Current split | `artifacts/digital-analytics-200-dataset/` | 100 training, 100 validation, manifest, and review |
| Dashboard and voice UI | `ui/` | Session charts, dataset view, grounded Q&A, STT, and TTS |

The server is also registered in `/root/.codex/config.toml` under the name `emergence-craft`, so it is available outside this workspace too. That user file is managed by `codex mcp` commands; the project copy is the version-controlled declaration for this workspace.

## Start here

1. Change into this directory:

   ```bash
   cd /llm_models_python_code_src/emergence-craft-reasoning
   ```

2. Confirm the server is registered:

   ```bash
   codex mcp list
   ```

3. Authenticate the live CRAFT MCP once. This opens the Keycloak PKCE login; use the Google or Microsoft identity registered for the hackathon:

   ```bash
   codex mcp login craft
   ```

4. Start a fresh Codex session from this directory. Project `.codex/config.toml` settings are loaded when the repository is trusted.

5. Ask Sol to test the live project catalog:

   > Sol, query all CRAFT data connections read-only and explain why Firebase and GA4 match the Digital Analytics category.

6. Begin with one domain, preferably the Data Catalog:

   > Sol, use the CRAFT docs and `schemas/reasoning-trace.schema.json` to draft the first Data Catalog trace in `examples/`. Clearly label assumptions and unresolved CRAFT API mappings.

## Connection details

- Live server: `craft`
- Live endpoint: `https://nebius.emergence.ai/mcp`
- CRAFT project: `8c5c41d7-19e0-45ba-8bf6-57fc2706bf1b`
- Scope header: `X-Project-ID`
- Authentication: Keycloak PKCE, public client `em-runtime-mcp`
- Documentation server: `emergence-craft` at `https://docs.emergence.ai/mcp`
- Nebius project: `aiproject-e00g1a833vjes1bvhv`
- Nebius API: `https://api.tokenfactory.nebius.com/v1/`
- Active category: Digital Analytics
- Active catalogs: `firebase-8c5c41d7.FIREBASE` and `ga4-8c5c41d7.GA4`
- Legacy first-demo catalog: `github-repos-8c5c41d7.GITHUB_REPOS`

The live CRAFT server is the hackathon's supported interface for project-scoped catalog, workflow, SQL, and agent tools. The separate documentation MCP is retained for public product documentation.

## Fine-tuning workflow

Create `.env` from the safe template and insert credentials locally:

```bash
cp .env.example .env
chmod 600 .env
```

Then run:

```bash
python3 scripts/craft_mcp.py tools
python3 scripts/craft_mcp.py digital-analytics --output data/generated/digital-analytics-catalogs.json
python3 scripts/pipeline.py preflight-nebius
python3 scripts/pipeline.py student-smoke
python3 scripts/build_digital_analytics_seeds.py
python3 scripts/pipeline.py prepare --input data/generated/digital-analytics-200-teacher.jsonl --output-dir artifacts/digital-analytics-200-dataset
python3 scripts/pipeline.py submit --dataset-dir artifacts/digital-analytics-200-dataset
python3 scripts/pipeline.py monitor <job-id> --max-seconds 600
python3 scripts/pipeline.py eval --model Qwen/Qwen3-30B-A3B-Instruct-2507
```

Nebius model eligibility and the current dataset review pass. Each future dataset must still receive its own review record before upload.

Run limits are explicit per session: the first demo used 15 minutes, the 8-example Digital Analytics run allowed 30 minutes, and the current 200-example run used a strict 10-minute limit. `monitor --max-seconds` cancels any job still active at its configured boundary.

The verified CRAFT GitHub snapshot currently contains one schema, six tables, and 30 columns. The first Sol batch contains catalog, workflow, and agent-registry examples. Examples without live CRAFT evidence are labeled `needs_review` and are not approved for training automatically. The hackathon MCP currently exposes catalog/schema, SQL generation and execution, result retrieval, terminology, chart, and sampling tools; it does not expose workflow or agent-registry tools.

The second run inventories all nine project data connections and uses the two catalogs whose descriptions directly match Digital Analytics: `firebase-8c5c41d7.FIREBASE` for mobile-app interaction events and app-performance analysis, and `ga4-8c5c41d7.GA4` for e-commerce events, sessions, engagement, purchases, and conversions. The exact phrase search returned no tag-level matches, so selection is based on the catalogs' live database descriptions. The remaining seven catalogs are excluded because their stated purposes are commerce operations, blockchain, software dependencies, repositories, or medical research rather than digital interaction analytics.

The current reproducible dataset contains 200 deterministic, catalog-grounded trace variations across ten policy/workflow templates and twenty scenarios. It is split exactly 100/100 between training and validation in `artifacts/digital-analytics-200-dataset/`. This large validation share checks template consistency; because both halves share templates, it must not be presented as an independent generalization benchmark.

## Team dataset review

The current teacher batch and grounding evidence are committed so collaborators can inspect them in GitHub:

- `data/generated/digital-analytics-catalogs.json` — Firebase and GA4 catalog/schema evidence
- `data/generated/digital-analytics-200-teacher.jsonl` — 200 generated trace examples
- `artifacts/digital-analytics-200-dataset/train.jsonl` — 100-example training split
- `artifacts/digital-analytics-200-dataset/validation.jsonl` — 100-example validation split
- `artifacts/digital-analytics-200-dataset/manifest.json` — source hash, model, seed, and counts
- `artifacts/digital-analytics-200-dataset/review.json` — approval and known limitations

Reviewers should verify correctness, evidence references, policy decisions, tool outcomes, privacy, and absence of invented APIs before changing an example from `needs_review` to `passed`.

The evaluation suite is documented in `evals/README.md`. The dashboard shows only methods actually used: dataset integrity, CRAFT evidence grounding, privacy/secret checks, bounded execution, and checkpoint train/validation loss. `evals/qwythos-suite.json` remains an unexecuted historical reference.

The displayed Qwythos values are references, not this project's results. A fair base-versus-LoRA comparison is still pending deployment of a checkpoint and identical held-out prompts/settings against both the base and adapter.

## Local management UI

Run the local-only dashboard:

```bash
python3 ui/server.py
```

Open `http://127.0.0.1:8765`. The UI shows the current 200-example dataset, live Nebius jobs, LoRA settings, immutable training-session history, per-session loss charts, cross-session final-loss comparison, and LLM evaluations. Completed dataset records are read-only in the UI, preventing approval-button experiments from changing historical training inputs. It binds only to localhost and never returns API keys or OAuth tokens.

For dashboard-grounded voice Q&A, start a second subprocess:

```bash
python3 ui/voice_server.py
```

The dashboard uses the browser Web Speech API for speech-to-text and text-to-speech when supported; typed questions remain available everywhere. The subprocess retrieves fresh `/api/dashboard` data and sends it to the configured Nebius inference model with the question. Live inference was verified with `Qwen/Qwen3-30B-A3B-Instruct-2507` at `$0.10` per million input tokens and `$0.30` per million output tokens. Missing prices disable inference, the ledger is stored at `runs/voice-budget.json`, and the voice ceiling is `$50`; the remaining `$25` of the user's `$75` project budget is reserved for fine-tuning and evaluation. The voice service enforces its allocation locally, while the 30-minute training watchdog limits training duration because the available Nebius API does not expose an account-wide dollar stop.

Voice capabilities initialize during dashboard load. Separate indicators show whether Q&A inference, microphone/STT, and speaker/TTS are ready. Pressing **Ask by voice** starts the pre-initialized recognizer, and every successful answer is read aloud automatically; **Read answer** replays it.

Architecture, catalog, and platform-feature questions use a whitelisted repository knowledge bundle containing the README, project guides, pipeline configuration, evaluation results, and dataset manifests/reviews. Answers cite repository paths and label features as used, available, or pending; credentials, raw datasets, and arbitrary files are excluded.

The first bounded LoRA pipeline-validation job, `ftjob-a16a0aa96695477593c126598b12f88b`, completed successfully in 3 steps and 1,437 trained tokens. It is not promoted until checkpoint evaluations pass; see `evals/results/`.

Three sessions are recorded: the initial 3-example validation run, an 8-example Digital Analytics run, and the current 200-example run. The latest job `ftjob-4bfaa9ef51994ed5bd1924f58d686c2e` trained on 100 examples, validated on 100, processed 76,875 tokens, and succeeded in 509 seconds under its 600-second limit.

## Useful commands

```bash
codex mcp get emergence-craft
codex mcp get craft
codex mcp login craft
codex mcp list
codex mcp remove emergence-craft
```

## License

Licensed under the [GNU Affero General Public License v3.0 only](LICENSE). Network users of a modified version must be offered its corresponding source code under the same license.

## Safety rule

Store concise decision summaries and evidence references, never private chain-of-thought, passwords, access tokens, raw secrets, or sensitive source records.
