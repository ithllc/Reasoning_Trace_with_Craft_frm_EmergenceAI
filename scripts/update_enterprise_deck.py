#!/usr/bin/env python3
"""Retarget the six-slide EmergeGPT deck for a simple enterprise business story."""

from __future__ import annotations

import html
import re
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "docs" / "EmergeGPT_Deck_Updated.pptx"

SLIDES = {
    1: {
        "Turn CRAFT catalog evidence into reviewed datasets, managed LoRA runs, and auditable decisions.": "Turn authorized evidence into reviewed datasets, governed training runs, and auditable decisions.",
        "Distilling Grounded MCP Behavior into a Small, Locally-Served Model": "Governed Agent Learning for Enterprise Teams",
        "A Craft MCP pipeline that fine-tunes a small model on real tool-use traces and serves it locally with llama.cpp.": "Turn authorized evidence into reviewed datasets, governed training runs, and auditable decisions.",
        "Teacher": "Catalog",
        "Traces": "Review",
        "Dataset": "LoRA",
        "Student": "Govern",
    },
    2: {
        "Agents Generate Valuable Experience—": "Enterprise AI Learns—",
        "and Then Forget It": "Without a Control Plane",
        "Agentic systems repeatedly solve similar tasks.": "Agents repeat high-value work across teams and data domains.",
        "Each run produces tool calls, decisions, responses, and outcomes.": "Evidence, approvals, datasets, and model runs become fragmented.",
        "Most execution traces are stored only as logs — or discarded entirely.": "Leaders cannot easily reproduce, compare, or audit model changes.",
        "General-purpose models can be expensive and unnecessarily large for repeated, domain-specific work.": "General models may add avoidable cost, latency, and inconsistency.",
        "Existing agent pipelines often lack a practical way to learn from completed jobs.": "The missing layer is a governed path from enterprise evidence to improvement.",
        "unused logs": "ungoverned learning",
        "“Every completed agent job contains potential training data.”": "“Model improvement should be reviewable, repeatable, and reversible.”",
    },
    3: {
        "CRAFT Catalog Evidence": "Authorized Evidence",
        "From Teacher Traces to a Small, Local Model": "A Governed Path from Evidence to Model",
        "Teacher + Craft MCP": "Authorized Evidence",
        "gpt-5.6-sol": "Synthetic mobile + web",
        "Firebase + GA4": "Synthetic mobile + web",
        "Record Trace": "Design Decision Traces",
        "calls, results, answer": "evidence, policy, answer",
        "Review & Split": "Review & Version",
        "chat-template data": "manifests + 100/100 split",
        "LoRA Fine-Tune": "Managed LoRA",
        "Qwen3 A3B · Nebius": "Qwen3 A3B · Nebius",
        "Export & Serve": "Operate & Explain",
        "GGUF → llama.cpp": "history, budgets, voice Q&A",
        "Evaluate vs. Teacher": "Deploy & Compare",
        "held-out tasks": "pending: base vs. adapter",
        "MCP stays connected at runtime — fine-tuning captures tool-use behavior, not live Emergence data.": "Current: training complete. Next: deploy the adapter and prove improvement.",
    },
    4: {
        "Firebase + GA4 evidence for engagement, conversion, retention, and data-policy decisions.": "Synthetic mobile + web evidence for engagement, conversion, retention, and policy decisions.",
        "What We Built": "Enterprise Control Plane — Working Today",
        "Digital-catalog policy review — e.g. engagement trend, checkout abandonment, retention cohort, geographic rollup.": "Synthetic mobile + web evidence for engagement, conversion, retention, and policy decisions.",
        "TASK DOMAIN": "DIGITAL ANALYTICS",
        "INFRASTRUCTURE": "CURRENT PROOF",
        "3 Nebius fine-tuning jobs — all succeeded (3/3 steps)": "3 Nebius LoRA jobs — all succeeded",
        "Every example is reviewed and approved before training": "200 versioned examples · immutable run history",
        "Dataset view is immutable once a run completes": "Voice Q&A cites 16 approved project sources",
        "“Grounded in real Craft MCP tool calls — not synthetic traces.”": "“Evidence-linked, reviewable, and budget-gated.”",
    },
    5: {
        "04 · REAL RESULTS": "04 · COMMERCIAL MODEL",
        "Two Runs, One Repeatable Process": "Pilot Fast. Scale Only After Proof.",
        "Run 2 (scaled) · Digital Analytics dataset · 200 examples · 76,875 tokens": "Recommended service pricing · cloud and model use billed separately",
        "RUN 1 · INITIAL VALIDATION": "GOVERNED PILOT",
        "DATASET": ("DURATION", "SUBSCRIPTION"),
        "3 examples · 3 domains": "6–10 weeks",
        "TOKENS": ("SCOPE", "SCALE"),
        "1,437": "1 category · 1–2 catalogs",
        "FINAL LOSS": ("PRICE", "CONTROLS"),
        "4.30 train · 4.08 val": "$50K–$125K",
        "STATUS": ("OUTCOME", "COMPLEX ROLLOUT"),
        "succeeded": ("measured business case", "$500K–$1.5M first year"),
        "RUN 2 · SCALED (chart at left)": "PRODUCTION PLATFORM",
        "Digital Analytics · 200 ex.": "$150K–$500K / year",
        "76,875": "multi-team · recurring runs",
        "6.05 train · 5.99 val": "SSO · approvals · audit",
        "Loss isn’t comparable across runs with different data — GSM8K, MMLU, ARC, GPQA, and CRAFT evaluation is still pending adapter deployment.": "Indicative packaging—final price follows scope, risk, and integrations.",
        "The asset is the process: the same reviewable, versioned LoRA pipeline, validated at 3 examples and scaled cleanly to 200.": "Enterprises buy integration, governance, evaluation, and accountability—not GPU minutes alone.",
    },
    6: {
        "CRAFT data and policy context": "Provider-neutral data and policy context",
        "05 · WHAT'S NEXT": "05 · WHY IT WINS",
        "What's Next": "Easier Governance—Not “Faster Kernels”",
        "DEPLOY & EVALUATE": "ENTERPRISE VALUE",
        "Deploy the trained adapter": "Provider-neutral data and policy context",
        "Run GSM8K, MMLU, ARC, GPQA, and CRAFT benchmarks": "Immutable reviews and run history",
        "Score teacher vs. student on held-out MCP tasks": "Managed Nebius training and budgets",
        "SCALE DELIBERATELY": "COMPLEMENTS UNSLOTH",
        "Expand beyond the current task family": "Unsloth excels at local speed, VRAM, and export",
        "Grow the dataset only once error analysis shows data volume is the real bottleneck": "EmergeGPT adds catalogs, policy, review, and operations",
        "Keep manual review gates for safety and quality": "Use either—or integrate Unsloth as a local backend",
        "“EmergeGPT distills real MCP tool-use behavior into a small model that runs anywhere.”": "“Use EmergeGPT when governed learning matters as much as training.”",
    },
}

NOTES = {
    1: "EmergeGPT is a vendor-neutral governed operating layer for model improvement. It links authorized evidence to reviewed datasets, provider-backed training, immutable history, and explainable operations. Deployment and measured quality lift remain gated.",
    2: "Enterprise buyers care because model changes are otherwise scattered across logs, notebooks, datasets, and cloud jobs. The business risk is not only model cost: it is unreproducible decisions, weak approval evidence, and no safe promotion path.",
    3: "The public demo uses synthetic mobile/web metadata. EmergeGPT turns reviewed policy templates into versioned data, submits capability-gated training through an authorized provider, and records results. It does not bundle tenant rows or third-party platform rights. Deployment and identical-prompt evaluation are the next gate.",
    4: "The current proof is operational, not a model-quality claim: four historical jobs succeeded; the public dataset has 1,000 synthetic deterministic examples split 500/500; the UI shows diagnostics and immutable session history; Q&A uses an approved dynamic documentation index.",
    5: "These are proposed EmergeGPT service bands, not vendor quotes or observed market averages. Pilot: $50K–$125K. Production platform: $150K–$500K annually. Complex regulated rollout: $500K–$1.5M first year. Consumption is separate. Buyers pay for integration, policy design, evaluation, security, support, and accountability. Sources: nebius.com/token-factory/prices; aws.amazon.com/sagemaker/ai/pricing; unsloth.ai.",
    6: "Unsloth is excellent at efficient local training, inference, broad model support, GGUF export, and lower VRAM. EmergeGPT addresses a different layer: authorized evidence, review, provider-backed jobs, history, budgets, evaluations, and enterprise explanation. The products can be complementary. Source: unsloth.ai/docs.",
}

TEXT_RE = re.compile(rb"(<a:t>)(.*?)(</a:t>)", re.DOTALL)


def replace_text(xml: bytes, replacements: dict[str, str | tuple[str, ...]]) -> tuple[bytes, set[str]]:
    matched: set[str] = set()
    occurrences: dict[str, int] = {}

    def substitute(match: re.Match[bytes]) -> bytes:
        value = html.unescape(match.group(2).decode("utf-8"))
        if value not in replacements:
            return match.group(0)
        matched.add(value)
        replacement = replacements[value]
        if isinstance(replacement, tuple):
            index = occurrences.get(value, 0)
            replacement = replacement[min(index, len(replacement) - 1)]
            occurrences[value] = index + 1
        escaped = html.escape(replacement, quote=False).encode("utf-8")
        return match.group(1) + escaped + match.group(3)

    return TEXT_RE.sub(substitute, xml), matched


def replace_note(xml: bytes, note: str) -> bytes:
    replaced = False

    def substitute(match: re.Match[bytes]) -> bytes:
        nonlocal replaced
        value = html.unescape(match.group(2).decode("utf-8"))
        if replaced or not value.strip() or value.strip().isdigit():
            return match.group(0)
        replaced = True
        return match.group(1) + html.escape(note, quote=False).encode("utf-8") + match.group(3)

    return TEXT_RE.sub(substitute, xml)


def main() -> None:
    if not DECK.exists():
        raise SystemExit(f"missing deck: {DECK}")
    with tempfile.NamedTemporaryFile(dir=DECK.parent, suffix=".pptx", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with zipfile.ZipFile(DECK, "r") as source, zipfile.ZipFile(temporary, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                slide_match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", info.filename)
                note_match = re.fullmatch(r"ppt/notesSlides/notesSlide(\d+)\.xml", info.filename)
                if slide_match:
                    number = int(slide_match.group(1))
                    data, matched = replace_text(data, SLIDES.get(number, {}))
                    missing = set(SLIDES.get(number, {})) - matched
                    current = {
                        html.unescape(match.group(1).decode("utf-8"))
                        for match in re.finditer(rb"<a:t>(.*?)</a:t>", data, re.DOTALL)
                    }
                    unresolved = []
                    for key in missing:
                        desired = SLIDES[number][key]
                        desired_values = desired if isinstance(desired, tuple) else (desired,)
                        if not all(value in current for value in desired_values):
                            unresolved.append(key)
                    if unresolved:
                        raise RuntimeError(f"slide {number} missing text: {sorted(unresolved)}")
                elif note_match:
                    number = int(note_match.group(1))
                    if number in NOTES:
                        data = replace_note(data, NOTES[number])
                target.writestr(info, data)
        temporary.replace(DECK)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Updated {DECK} while preserving {len(SLIDES)} slides")


if __name__ == "__main__":
    main()
