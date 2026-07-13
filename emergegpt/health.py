"""Explainable model-health scoring and recommendations."""

from __future__ import annotations


def severity(observed: float, warning: float, critical: float, higher_is_better: bool) -> float:
    denominator = (warning - critical) if higher_is_better else (critical - warning)
    if denominator <= 0:
        raise ValueError("warning/critical thresholds are inconsistent")
    raw = ((warning - observed) if higher_is_better else (observed - warning)) / denominator
    return max(0.0, min(1.0, raw))


def score(signals: list[dict]) -> dict:
    eligible = [item for item in signals if item.get("sample_count", 0) >= item.get("minimum_samples", 1)]
    weighted = sum(item["weight"] * item["severity"] * item.get("confidence", 1.0) for item in eligible)
    weights = sum(item["weight"] for item in eligible)
    risk = 100 * weighted / weights if weights else 0.0
    band = "healthy" if risk < 25 else "watch" if risk < 50 else "evaluate" if risk < 70 else "fine_tuning_candidate"
    critical = any(item["severity"] >= 1 and item.get("critical_policy") for item in eligible)
    degraded = sum(item["severity"] > 0 for item in eligible)
    recommend = critical or (risk >= 70 and degraded >= 2)
    return {"risk": round(risk, 2), "band": band, "recommend_fine_tuning": recommend, "signals": eligible}


def root_cause_recommendation(context: dict) -> str:
    if context.get("tool_or_connection_failure"):
        return "repair_integration"
    if context.get("stale_evidence"):
        return "refresh_evidence"
    if context.get("prompt_or_config_regression"):
        return "rollback_or_fix_configuration"
    if not context.get("sufficient_approved_examples", False):
        return "collect_and_review_data"
    return "evaluate_fine_tuning_candidate"
