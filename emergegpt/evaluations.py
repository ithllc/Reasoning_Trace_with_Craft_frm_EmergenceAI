"""Versioned evaluation definitions and metric helpers."""

from __future__ import annotations

import math


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if total == 0:
        return None, None
    if not 0 <= successes <= total:
        raise ValueError("successes must be within total")
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - margin), min(1, center + margin)


def classify(value: float | None, *, warning: float, target: float, higher_is_better: bool) -> str:
    if value is None:
        return "missing"
    if higher_is_better:
        return "passed" if value >= target else "warning" if value >= warning else "failed"
    return "passed" if value <= target else "warning" if value <= warning else "failed"
