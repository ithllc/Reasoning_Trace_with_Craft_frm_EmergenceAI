# Script reference

| Script | Purpose | Live mutation |
| --- | --- | --- |
| `scripts/pipeline.py` | Dataset preparation, provider preflight, approved training, monitoring, checkpoints, and evaluation command generation | Upload/submit/cancel/deploy commands only |
| `scripts/craft_mcp.py` | Legacy authorized tenant-read helper; disabled without explicit authorization environment | No mutation tools implemented |
| `scripts/build_digital_analytics_seeds.py` | Rebuild the 1,000-example synthetic public fixture | No |
| `scripts/update_enterprise_deck.py` | Mechanically update the presentation archive | Local file only |
| `scripts/security_scan.py` | Scan current tree and optionally history for secret/private identifier policy | No |
| `ui/server.py` | EmergeGPT API, dashboard, docs index, analytics, workflow, and MCP Builder | UI mutation endpoints are local/policy-gated |
| `ui/voice_server.py` | Budget-gated, documentation-grounded Q&A | Paid inference when configured |
| `emergegpt_mcp/craft_server.py` | Public docs and authorization readiness MCP gateway | No tenant mutation tools |
| `emergegpt_mcp/nebius_server.py` | Docs/provider-read gateway plus approval-gated cancellation example | Cancellation with exact one-time approval |

Each executable uses environment-backed credentials, emits no hidden chain-of-thought, and must be run from a trusted checkout. Provider uploads, training, deployment, cancellation, schedule activation, and outbound notifications are live mutations and require explicit approval.
