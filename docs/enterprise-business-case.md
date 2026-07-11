# EmergeGPT enterprise business case

## Executive summary

EmergeGPT is best positioned as a **governed model-improvement operating layer for repeated enterprise agent work**. It connects CRAFT catalog evidence to reviewed training examples, runs managed LoRA jobs through Nebius Token Factory, preserves immutable dataset and session history, and explains the system through a grounded dashboard assistant.

The commercial value is not “fine-tuning by itself.” Fine-tuning frameworks already exist. The value is making the full loop—evidence selection, trace design, review, reproducibility, training, monitoring, evaluation status, and audit—usable by enterprise data and AI teams.

Current proof points:

- all nine tenant data connections were inventoried and Firebase/GA4 were selected for Digital Analytics;
- a 200-example deterministic dataset was versioned and split 100/100;
- three Nebius LoRA jobs completed successfully;
- the dashboard records datasets, loss, time limits, and session history;
- voice/text Q&A is grounded in a 16-file repository allowlist.

Current limitation: no adapter has been promoted. Identical-prompt base-versus-LoRA evaluation is still pending deployment, so the application must not claim quality improvement or production savings yet.

## How an enterprise would use it

1. **Select a governed domain.** Connect CRAFT to approved catalogs and define the business category, policies, owners, and permitted assets.
2. **Capture reusable decisions.** Convert repeated agent tasks into concise, auditable examples containing evidence references, tool summaries, policy gates, and final decisions—not private chain-of-thought.
3. **Review and version.** Human reviewers approve examples; manifests bind the source, model, seed, and split to a reproducible dataset.
4. **Train economically.** Submit LoRA jobs through Nebius rather than operating a custom GPU stack for each experiment.
5. **Compare and promote.** Run the same held-out prompts against the untouched base and deployed adapter. Promote only when task quality improves without policy regression.
6. **Operate and explain.** Use session history, budgets, status, and grounded Q&A for model owners, auditors, data stewards, and business users.

Likely enterprise use cases include governed conversational analytics, customer-support decision policy, compliance triage, IT operations, data-quality remediation, claims or case routing, and repeated analyst workflows.

## Why enterprises care

- **Governance:** CRAFT is designed around enterprise data, policies, permissions, proofs, and deployment control. It supports project isolation, authorization, secrets, catalog assets, workflows, and observability. [CRAFT introduction](https://docs.emergence.ai/getting-started/introduction)
- **Reproducibility:** Nebius Data Lab describes centralized, versioned datasets as a way to make experiments consistent, comparable, and safer to iterate. [Nebius Data Lab fine-tuning](https://docs.tokenfactory.nebius.com/data-lab/fine-tuning)
- **Lower operating complexity:** Nebius exposes dataset upload, LoRA training, checkpoints, and custom adapter deployment through managed APIs. [Nebius supervised fine-tuning](https://docs.tokenfactory.nebius.com/post-training/how-to-fine-tune), [custom LoRA deployment](https://docs.tokenfactory.nebius.com/fine-tuning/deploy-custom-model)
- **Potential economics:** a smaller or specialized model can reduce prompt complexity, latency, and inference cost for repeated tasks, but those savings must be proven with base-versus-adapter evaluation and production traffic.
- **Auditability:** immutable inputs, evidence references, review state, time limits, and run history make model changes easier to explain than ad hoc notebooks and one-off API calls.

## Commercial packaging and pricing

The following bands are **recommended EmergeGPT service pricing**, not published market averages or vendor quotes. Cloud/model consumption is billed separately.

| Offer | Suggested price | Typical scope |
| --- | ---: | --- |
| Governed pilot | **$50,000–$125,000** fixed | 6–10 weeks, one category, 1–2 catalogs, one dataset, evaluation design, executive readout |
| Production platform | **$150,000–$500,000 per year** | Multiple teams, SSO/RBAC integration, recurring datasets and training, approval workflow, support, audit reporting |
| Regulated or multi-domain rollout | **$500,000–$1.5 million first year** | Several domains, custom controls, private networking, deployment integration, evaluation operations, change management, SLA/support |

Why service pricing is much higher than a training API call: enterprise buyers pay for integration, data and policy design, evaluation, security review, repeatability, support, and accountability—not only GPU minutes.

Public comparators reinforce the distinction:

- Unsloth offers an open-source/free version; Pro and Enterprise are contact-sales offerings. [Unsloth pricing and features](https://unsloth.ai/)
- AWS SageMaker is pay-as-you-go across training, hosting, storage, processing, and MLOps; its examples show that raw compute can be inexpensive while human evaluation and lifecycle work add separate cost. [AWS SageMaker pricing](https://aws.amazon.com/sagemaker/ai/pricing/)
- Nebius Token Factory prices model consumption separately and supports managed post-training and per-token adapter serving. [Nebius pricing](https://nebius.com/token-factory/prices), [Nebius post-training overview](https://docs.tokenfactory.nebius.com/post-training/overview)

### Pricing guardrails

- Quote implementation separately from Nebius/CRAFT consumption.
- Put catalog count, example volume, evaluation cases, environments, integrations, and support hours in the statement of work.
- Make production pricing contingent on a measured base-versus-adapter business result.
- Do not price from token savings alone; include analyst time, audit preparation, incident reduction, and reuse across teams.

## Is this easier than Unsloth?

**For enterprise governance and orchestration: potentially yes. For local training performance: no.** They solve different layers.

| Capability | EmergeGPT | Unsloth |
| --- | --- | --- |
| Primary job | Govern evidence-to-dataset-to-managed-training operations | Make local/model training and inference faster and more memory-efficient |
| Catalog grounding | CRAFT Firebase/GA4 metadata and project-scoped evidence | Users provide or create datasets |
| Review/audit | Manifests, review records, immutable completed runs, session history | Training observability and dataset tooling; enterprise governance is not the core claim |
| Compute | Nebius-managed LoRA API | Local/cloud hardware chosen and operated by the user |
| Model coverage/export | Current workflow targets one verified Qwen model; deployment pending | 500+ models, GGUF/safetensors export, local APIs, model arena |
| Training optimization | Relies on Nebius | Strong differentiator: optimized kernels, lower VRAM, local and multi-GPU options |
| Best fit | Data/AI governance teams needing repeatable operating controls | ML engineers optimizing local training, inference, export, or hardware use |

Unsloth officially describes local training/inference, broad model support, GGUF export, model comparison, observability, and substantial speed/VRAM optimizations. [Unsloth documentation](https://unsloth.ai/docs)

The honest product strategy is complementary: EmergeGPT can remain the governed control plane and add Unsloth as an optional local execution/export backend. It should not claim to outperform Unsloth’s kernels or model support.

## Enterprise architecture

```text
Enterprise data metadata
        |
        v
Emergence CRAFT ── catalog, policy, identity, evidence
        |
        v
EmergeGPT ── trace templates, review, manifests, budgets, session history
        |
        v
Nebius Token Factory ── model catalog, files, LoRA jobs, checkpoints, inference
        |
        v
Evaluation gate ── same prompts, base vs adapter, task + policy scores
        |
        v
Approved deployment (pending in the current demo)
```

CRAFT can deploy on customer-controlled infrastructure and provides enterprise platform services such as OIDC/PKCE, authorization, secrets, assets, workflows, and observability. [CRAFT introduction](https://docs.emergence.ai/getting-started/introduction)

## Buyer and ROI model

Economic buyer: Chief Data Officer, CIO, VP AI/ML, or business-unit technology leader. Operational owners: AI platform, data governance, analytics engineering, model risk, and security.

A pilot is justified when:

- a repeated task has meaningful volume and a stable decision policy;
- evidence and reviewer ownership are available;
- current large-model cost, latency, or inconsistency is measurable;
- held-out success and policy regression can be scored.

Use this decision formula:

```text
annual value = avoided model cost
             + analyst/engineer hours saved
             + avoided audit and incident effort
             + value of faster decisions
             - platform, integration, inference, and support cost
```

Do not advance from pilot to production without an adapter deployment, identical-prompt base comparison, security review, rollback plan, and production monitoring.

## Recommended roadmap

1. Deploy the latest LoRA checkpoint.
2. Build an independent held-out set that does not share the ten training templates.
3. Score base and adapter on identical prompts for task correctness, grounding, policy compliance, latency, and cost.
4. Add enterprise identity, reviewer roles, approval records, and signed promotion state.
5. Add deployment/rollback and production drift monitoring.
6. Pilot one high-volume Digital Analytics workflow and publish measured ROI.

## Presentation guidance

The companion six-slide deck intentionally stays simple. It presents the enterprise problem, governed architecture, current proof, proposed commercial packaging, and differentiation. Detailed qualifications and sources belong in this document and slide notes.
