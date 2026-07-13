# UI and Model-Harness Collaboration

EmergeGPT uses a hybrid control model: the user and application define **what is
allowed and bounded**; a selected model harness may advise **how to carry it
out**. Harness output is always a proposal, never an implicit authorization.

## Authority boundary

| Concern | Deterministic owner | Harness role |
|---|---|---|
| Model, dataset, tenant/project, budget, schedule, and requested operation | User intent contract and EmergeGPT policy | Explain trade-offs; cannot alter the contract |
| Evaluation selection and parameters | Versioned registry plus user acceptance | Recommend from domain evidence and explain confidence |
| Notification delivery and minimum severity | Topic policy and user subscriptions | Add context or raise severity; cannot lower a policy floor |
| Live CRAFT or Nebius mutation | Explicit scoped approval and provider capability check | Select a compatible command sequence within the approved scope |
| Completion and promotion | Verifiable provider state and required evaluation gates | Summarize results; cannot declare an absent gate passed |

## Contract sequence

1. The UI creates an immutable intent with actor, objective, assets, operation
   classes, budget, and approval policy.
2. A harness returns structured recommendations, confidence, rationale,
   evidence citations, and assumptions tied to the intent hash.
3. EmergeGPT evaluates allowlists, entitlements, budgets, and approval rules.
4. Accepting advice creates a new intent; it never silently edits the original.
5. Execution emits durable status events. Users can monitor the run and receive
   subscribed email, Slack, or Telegram notifications.
6. Provider evidence and evaluation results determine completion and promotion.

## Evaluation experience

The **Quality & Cost** workspace offers a versioned registry, MMLU,
ARC-Challenge, ARC-AGI, project-domain suites, checked JSON imports, safe runner
plans, and model-to-model comparison. Evaluations apply to base, LoRA, and
full-fine-tuned models. Training-mode advice is separate: bounded behavior
changes prefer reversible LoRA, while full tuning is suggested only for an
exact model that supports it and a foundation-wide change.

## Notification experience

Users choose topics, minimum severity, and a delivery profile. Topics include
pipeline status, approvals, schedules, evaluation regressions, model health,
fine-tuning recommendations, budgets, providers, CRAFT authorization, model
deprecation, and security. Policy severity is a floor. Duplicate conditions
produce one alert, delivery retries are recorded, and alerts can be
acknowledged or resolved in the UI.

## Failure behavior

Unknown runners, tools, models, operations, or tenant capabilities fail closed.
Missing harnesses still allow a safe plan to be inspected, but no command is
represented as executed. EmergeGPT never treats public CRAFT documentation as
tenant data access and never stores provider credentials in these contracts.
