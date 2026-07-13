"""Token and quality-adjusted cost formulas."""

from __future__ import annotations


def inference_cost(input_tokens: int, output_tokens: int, input_per_million: float, output_per_million: float) -> float:
    if min(input_tokens, output_tokens, input_per_million, output_per_million) < 0:
        raise ValueError("usage and prices must be nonnegative")
    return (input_tokens * input_per_million + output_tokens * output_per_million) / 1_000_000


def comparison(*, base_tokens: int, tuned_tokens: int, base_cost: float, tuned_cost: float,
               training_cost: float, evaluation_cost: float, deployment_setup_cost: float,
               expected_requests: int, base_successes: int, tuned_successes: int) -> dict:
    if min(base_tokens, tuned_tokens, base_cost, tuned_cost, training_cost, evaluation_cost,
           deployment_setup_cost, expected_requests, base_successes, tuned_successes) < 0:
        raise ValueError("comparison values must be nonnegative")
    one_time = training_cost + evaluation_cost + deployment_setup_cost
    amortized = one_time / expected_requests if expected_requests else None
    tuned_total = tuned_cost + (amortized or 0)
    per_request_savings = base_cost - tuned_cost
    return {
        "token_savings_pct": 100 * (base_tokens - tuned_tokens) / base_tokens if base_tokens else None,
        "cost_savings_pct": 100 * (base_cost - tuned_total) / base_cost if base_cost else None,
        "base_cost_per_success": base_cost / base_successes if base_successes else None,
        "tuned_cost_per_success": tuned_total / tuned_successes if tuned_successes else None,
        "incremental_cost_per_added_success": ((tuned_total - base_cost) / (tuned_successes - base_successes)
                                                if tuned_successes != base_successes else None),
        "amortized_training_cost": amortized,
        "break_even_requests": one_time / per_request_savings if per_request_savings > 0 else None,
    }
