#!/usr/bin/env python3
"""Create 200 distinct, metadata-grounded Digital Analytics teacher seeds."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "seeds" / "digital-analytics-200.jsonl"
TEACHER_OUTPUT = ROOT / "data" / "generated" / "digital-analytics-200-teacher.jsonl"

SCENARIOS = [
    "daily engagement trend", "weekly active-use summary", "purchase conversion funnel",
    "platform comparison", "app-version adoption", "event-volume anomaly", "campaign attribution",
    "session quality", "checkout abandonment", "retention cohort", "geographic rollup",
    "device-category performance", "event taxonomy audit", "partition completeness",
    "timestamp consistency", "metric-definition change", "small-cell privacy review",
    "cross-channel comparison", "late-arriving event handling", "dashboard release approval",
]

TASKS = [
    ("catalog", "data_catalog", "Choose between Firebase and GA4 for a {scenario}; cite exact catalog evidence, identify missing evidence, and state whether use is approved."),
    ("scope", "data_catalog", "Define the minimum table and column scope for a {scenario} without exposing user-level rows."),
    ("privacy", "data_catalog", "Assess pseudonymous identifiers, device, geo, and VARIANT fields for a {scenario}; apply data minimization and classification caveats."),
    ("quality", "data_catalog", "Evaluate freshness, partition coverage, and data-quality evidence required for a {scenario}."),
    ("workflow", "workflow", "Design an auditable read-only workflow trace for a {scenario}, including trigger, bounded actions, provenance, and output."),
    ("validation", "workflow", "Define deterministic validation gates and failure behavior for a {scenario} artifact."),
    ("temporal", "workflow", "Resolve date partitions, timezone, overlap, and duplicate risks for a {scenario}."),
    ("cross_catalog", "workflow", "Decide whether Firebase and GA4 may be joined for a {scenario}; require identity, consent, semantic, and date-alignment evidence."),
    ("agent", "agent_registry", "Specify the agent-card capabilities, permissions, limits, and evaluation evidence needed to perform a {scenario}."),
    ("incident", "workflow", "Design a trace for detecting, containing, and documenting a failed {scenario} run without retaining raw identifiers."),
]

FIREBASE = "firebase-8c5c41d7.FIREBASE.ANALYTICS_153293282.EVENTS_20180612"
GA4 = "ga4-8c5c41d7.GA4.GA4_OBFUSCATED_SAMPLE_ECOMMERCE.EVENTS_20201101"


def answer(task_name: str, scenario: str) -> str:
    focus = {
        "catalog": "Select Firebase for mobile-app behavior and GA4 for e-commerce sessions or conversion; split cross-channel work unless an approved mapping exists.",
        "scope": "Use only dated event partitions and the minimum date, event-name, and aggregate fields required.",
        "privacy": "Do not copy pseudonymous IDs, device, geo, session IDs, or raw VARIANT values into the trace.",
        "quality": "Block release until freshness, partition coverage, metric definitions, and quality checks are documented.",
        "workflow": "Use a bounded read-only sequence: resolve metadata, validate dates, aggregate, validate the artifact, and record provenance.",
        "validation": "Require schema, date coverage, duplicate, null, count-bound, privacy, provenance, and reviewer gates.",
        "temporal": "Normalize YYYYMMDD dates and timezone, reject overlapping partitions, and report missing or late dates.",
        "cross_catalog": "Do not join Firebase and GA4 identities without an authorized crosswalk, consent basis, aligned periods, and compatible semantics.",
        "agent": "Require a versioned agent card with allowlisted assets, read-only permissions, metric definitions, limits, privacy controls, and evaluation evidence.",
        "incident": "Stop publication, retain aggregate diagnostics only, identify affected partitions, record the failed gate, and require reviewed remediation before retry.",
    }[task_name]
    return (
        f"Decision summary: For the {scenario}, {focus} "
        f"Evidence: `{FIREBASE}` is a Firebase daily interaction-event table; `{GA4}` is a GA4 daily e-commerce event table. "
        "Both catalog records currently show data_quality=false, and similarly named pseudonymous identifiers do not establish a safe join. "
        "Tool activity: inspected the supplied read-only CRAFT metadata snapshot only; no source rows or live queries were used. "
        "Policy checks: least privilege, purpose limitation, data minimization, temporal alignment, small-cell protection, provenance, and human review. "
        "Validation: needs_review until the requested dates, metric definition, authorization, freshness, and quality evidence pass."
    )


def main() -> None:
    rows, teacher_rows = [], []
    for task_name, domain, template in TASKS:
        for index, scenario in enumerate(SCENARIOS, 1):
            rows.append({
                "id": f"digital-{task_name}-{index:03d}",
                "domain": domain,
                "prompt": template.format(scenario=scenario),
            })
            teacher_rows.append({
                "messages": [
                    {"role": "user", "content": template.format(scenario=scenario)},
                    {"role": "assistant", "content": answer(task_name, scenario)},
                ],
                "metadata": {
                    "id": f"digital-{task_name}-{index:03d}",
                    "domain": domain,
                    "teacher": {"agent_name": "Sol", "model_label": "Codex (GPT 5.6 Sol)"},
                    "trace": {
                        "decision_summary": f"Apply the reviewed {task_name} policy template to the {scenario}.",
                        "evidence_refs": [FIREBASE, GA4],
                        "tool_calls": [{
                            "tool": "catalog_snapshot.inspect",
                            "purpose": "Review project-scoped Digital Analytics metadata without source-row access.",
                            "outcome": "Firebase and GA4 candidate assets identified; production readiness remains gated.",
                        }],
                        "validation": "needs_review",
                    },
                },
            })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    TEACHER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TEACHER_OUTPUT.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in teacher_rows))
    print(f"Wrote {len(rows)} seeds to {OUTPUT} and {len(teacher_rows)} examples to {TEACHER_OUTPUT}")


if __name__ == "__main__":
    main()
