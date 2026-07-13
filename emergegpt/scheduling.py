"""Small durable scheduling primitives."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def validate_timezone(name: str) -> str:
    ZoneInfo(name)
    return name


def fire_key(schedule_id: str, intended_fire_time: datetime, workflow_config_hash: str) -> str:
    material = f"{schedule_id}:{intended_fire_time.isoformat()}:{workflow_config_hash}"
    return hashlib.sha256(material.encode()).hexdigest()


def _matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    if field == "*": return True
    if field.startswith("*/"):
        step = int(field[2:])
        return step > 0 and (value - minimum) % step == 0
    allowed = set()
    for part in field.split(","):
        if "-" in part:
            start, end = map(int, part.split("-", 1)); allowed.update(range(start, end + 1))
        else:
            allowed.add(int(part))
    if any(item < minimum or item > maximum for item in allowed): raise ValueError("cron field out of range")
    return value in allowed


def next_fires(expression: str, timezone_name: str, count: int = 5, start: datetime | None = None) -> list[str]:
    fields = expression.split()
    if len(fields) != 5: raise ValueError("cron expression must contain five fields")
    zone = ZoneInfo(validate_timezone(timezone_name))
    current = (start or datetime.now(zone)).astimezone(zone).replace(second=0, microsecond=0) + timedelta(minutes=1)
    results = []
    for _ in range(60 * 24 * 366 * 2):
        weekday = (current.weekday() + 1) % 7
        if (_matches(fields[0], current.minute, 0, 59) and _matches(fields[1], current.hour, 0, 23)
                and _matches(fields[2], current.day, 1, 31) and _matches(fields[3], current.month, 1, 12)
                and _matches(fields[4], weekday, 0, 6)):
            results.append(current.isoformat())
            if len(results) == count: return results
        current += timedelta(minutes=1)
    raise ValueError("could not find requested cron occurrences")
