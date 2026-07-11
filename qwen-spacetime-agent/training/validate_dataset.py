from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()

    seen: set[str] = set()
    count = 0
    with args.dataset.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            job_id = row.get("id")
            messages = row.get("messages")
            if not isinstance(job_id, str) or not job_id:
                raise ValueError(f"line {line_number}: missing string id")
            if job_id in seen:
                raise ValueError(f"line {line_number}: duplicate id {job_id}")
            if row.get("status") != "completed":
                raise ValueError(f"line {line_number}: only completed jobs may be trained")
            if not isinstance(messages, list) or len(messages) < 3:
                raise ValueError(f"line {line_number}: messages must contain a full trajectory")
            if messages[-1].get("role") != "assistant" or not messages[-1].get("content"):
                raise ValueError(f"line {line_number}: trajectory needs a non-empty final answer")
            allowed = {"system", "user", "assistant", "tool"}
            if any(message.get("role") not in allowed for message in messages):
                raise ValueError(f"line {line_number}: unsupported message role")
            call_ids: set[str] = set()
            result_ids: set[str] = set()
            for message in messages:
                content = str(message.get("content", "")).lower()
                if "<think>" in content or "chain of thought" in content:
                    raise ValueError(f"line {line_number}: hidden-reasoning marker is not trainable")
                for call in message.get("tool_calls", []):
                    call_id = call.get("id")
                    arguments = call.get("function", {}).get("arguments")
                    if not call_id or not isinstance(arguments, str):
                        raise ValueError(f"line {line_number}: malformed tool call")
                    json.loads(arguments)
                    call_ids.add(call_id)
                if message.get("role") == "tool":
                    if not message.get("tool_call_id"):
                        raise ValueError(f"line {line_number}: tool result missing tool_call_id")
                    result_ids.add(message["tool_call_id"])
            if call_ids != result_ids:
                raise ValueError(f"line {line_number}: tool calls and results do not match")
            seen.add(job_id)
            count += 1

    if not count:
        raise ValueError("dataset contains no completed trajectories")
    print(f"Valid: {count} completed trajectories")


if __name__ == "__main__":
    main()
